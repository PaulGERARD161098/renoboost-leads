"""Runner Claude tool-use — boucle agent Copilote.

Une seule fonction `run_cycle(instruction, ...)` qui :
1. Vérifie le budget restant
2. Charge le prompt système + le journal récent
3. Boucle Claude tool-use :
   - appel API avec messages + tools
   - exécute chaque tool_use
   - re-soumet les résultats
   - s'arrête quand stop_reason == "end_turn" ou max_outils atteint
4. Décompte le coût réel (usage.input_tokens / output_tokens)
5. Journalise l'instruction + la décision finale (texte) + le résultat

Le runner ne fait PAS de streaming : on attend le tour complet pour
simplifier le décompte budget et la journalisation. Le SDK Anthropic
gère les retries réseau automatiquement.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..settings import PROJECT_ROOT, get_settings
from .budget import BudgetGuard
from .config import AgentConfig, load_agent_config
from .journal import Journal, JournalEntry
from .tools import all_dispatch, all_schemas

if TYPE_CHECKING:
    from anthropic import Anthropic


SYSTEM_PROMPT_PATH = PROJECT_ROOT / "src" / "renoboost_leads" / "agent" / "prompts" / "system.md"


@dataclass
class CycleResult:
    cycle_id: str
    texte_final: str
    outils_appeles: list[dict] = field(default_factory=list)
    tours: int = 0
    cout_eur: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_cache_creation: int = 0
    tokens_cache_read: int = 0
    stop_reason: str = ""
    erreur: str | None = None

    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "texte_final": self.texte_final,
            "outils_appeles": self.outils_appeles,
            "tours": self.tours,
            "cout_eur": self.cout_eur,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "tokens_cache_creation": self.tokens_cache_creation,
            "tokens_cache_read": self.tokens_cache_read,
            "stop_reason": self.stop_reason,
            "erreur": self.erreur,
        }


def _system_blocks(journal: Journal) -> list[dict]:
    """Renvoie le prompt système en blocs avec cache_control sur le base.

    Le contenu base (rôle + règles) est stable d'un cycle à l'autre →
    cache ephemeral (5 min). Le journal récent change → bloc séparé,
    non-caché.
    """
    base = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    ctx = journal.context_pour_agent(n=5)
    return [
        {
            "type": "text",
            "text": base,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"\n\n## Journal récent\n\n{ctx}",
        },
    ]


def _tools_with_cache(schemas: list[dict]) -> list[dict]:
    """Ajoute cache_control sur le dernier outil pour cacher tout le tableau.

    Les outils ne changent pas d'un cycle à l'autre — gros gain de tokens.
    """
    if not schemas:
        return schemas
    out = [dict(s) for s in schemas]
    out[-1] = {**out[-1], "cache_control": {"type": "ephemeral"}}
    return out


def _execute_tool(name: str, args: dict, dispatch: dict) -> Any:
    fn = dispatch.get(name)
    if fn is None:
        return {"error": f"outil inconnu : '{name}'"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"arguments invalides pour '{name}' : {e}"}
    except Exception as e:  # noqa: BLE001 — on relaie l'erreur au LLM
        return {"error": f"exception {type(e).__name__} : {e}"}


def _build_client() -> Anthropic:
    from anthropic import Anthropic

    settings = get_settings()
    if not settings.has_anthropic():
        raise RuntimeError(
            "ANTHROPIC_API_KEY manquante — configure-la dans .env pour utiliser l'agent."
        )
    return Anthropic(api_key=settings.anthropic_api_key.get_secret_value())


def run_cycle(
    instruction: str,
    *,
    config: AgentConfig | None = None,
    journal: Journal | None = None,
    budget: BudgetGuard | None = None,
    client: Anthropic | None = None,
) -> CycleResult:
    """Exécute un cycle agent complet : instruction → décision → résultat."""
    cfg = config or load_agent_config()
    j = journal or Journal(path=cfg.journal_path_abs())
    b = budget or BudgetGuard(
        cap_eur_par_jour=cfg.budget_eur_par_jour, path=cfg.budget_path_abs()
    )
    b.verifier()

    cli = client or _build_client()
    cycle_id = uuid.uuid4().hex[:6]
    result = CycleResult(cycle_id=cycle_id, texte_final="")

    system = _system_blocks(j)
    schemas = _tools_with_cache(all_schemas())
    dispatch = all_dispatch()

    messages: list[dict] = [{"role": "user", "content": instruction}]
    modele = cfg.modele_principal

    for tour in range(cfg.max_outils_par_cycle + 1):
        result.tours = tour + 1
        response = cli.messages.create(
            model=modele,
            max_tokens=2048,
            system=system,
            tools=schemas,
            messages=messages,
        )
        usage = response.usage
        result.tokens_input += usage.input_tokens
        result.tokens_output += usage.output_tokens
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        result.tokens_cache_creation += cache_creation
        result.tokens_cache_read += cache_read
        cout = BudgetGuard.estimer_cout_eur(
            modele,
            usage.input_tokens,
            usage.output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
        )
        result.cout_eur = round(result.cout_eur + cout, 6)
        b.consommer(cout)

        result.stop_reason = response.stop_reason or ""

        # Concatène le texte renvoyé par l'assistant pour ce tour
        texte_tour = []
        tool_uses = []
        for bloc in response.content:
            if bloc.type == "text":
                texte_tour.append(bloc.text)
            elif bloc.type == "tool_use":
                tool_uses.append(bloc)

        if texte_tour:
            result.texte_final = "\n\n".join(texte_tour)

        if response.stop_reason != "tool_use" or not tool_uses:
            break

        # Sinon, exécute les outils et re-soumet
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tu in tool_uses:
            args = tu.input if isinstance(tu.input, dict) else {}
            payload = _execute_tool(tu.name, args, dispatch)
            result.outils_appeles.append({"name": tu.name, "args": args})
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(payload, ensure_ascii=False, default=str),
                }
            )
        messages.append({"role": "user", "content": tool_results})

        # garde-fou budget en cours de cycle
        try:
            b.verifier()
        except Exception as e:  # noqa: BLE001
            result.erreur = str(e)
            break

    j.append(
        JournalEntry(
            cycle_id=cycle_id,
            instruction=instruction,
            decision=_resume_outils(result.outils_appeles)
            or "(aucun outil appelé)",
            resultat=result.texte_final[:500] or "(texte vide)",
            suite=f"tours={result.tours}, coût={result.cout_eur:.4f}€",
        )
    )
    return result


def _resume_outils(outils: list[dict]) -> str:
    if not outils:
        return ""
    parts = [o["name"] for o in outils]
    return " → ".join(parts)
