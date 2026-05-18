"""Chargement des templates de séquences cold mail par secteur.

Format markdown avec front-matter YAML :

    ---
    secteur: compta
    nom_lisible: "Cabinet comptable"
    sujet_step_1: "..."
    delai_step_2_jours: 4
    sujet_step_2: "..."
    delai_step_3_jours: 7
    sujet_step_3: "..."
    ---

    # Step 1 — ...
    Corps texte avec {{variables}}

    ---

    # Step 2 — ...
    ...

Variables disponibles : {{civilite}}, {{prenom}}, {{nom_dirigeant}},
{{nom_entreprise}}, {{telephone_paul}}, {{lien_calendly}}.

Rendu : substitution simple (str.replace), pas de Jinja pour rester
prévisible et faciliter la review humaine des emails staged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..settings import PROJECT_ROOT

TEMPLATES_DIR = PROJECT_ROOT / "templates" / "sequences"


@dataclass
class SequenceStep:
    numero: int  # 1, 2, 3
    sujet: str
    corps: str
    delai_jours: int = 0  # 0 pour le 1er step


@dataclass
class Sequence:
    secteur: str
    nom_lisible: str
    steps: list[SequenceStep]

    def render_step(self, numero: int, variables: dict[str, str]) -> SequenceStep:
        """Renvoie un nouveau step avec sujet+corps substitués."""
        step = self.get_step(numero)
        return SequenceStep(
            numero=step.numero,
            sujet=_render(step.sujet, variables),
            corps=_render(step.corps, variables),
            delai_jours=step.delai_jours,
        )

    def get_step(self, numero: int) -> SequenceStep:
        for s in self.steps:
            if s.numero == numero:
                return s
        raise ValueError(f"step {numero} absent de la séquence {self.secteur}")


def _render(template: str, variables: dict[str, str]) -> str:
    out = template
    for k, v in variables.items():
        out = out.replace("{{" + k + "}}", str(v))
    # Strip variables non-renseignées pour éviter de spammer des {{x}}
    out = re.sub(r"\{\{[a-z_]+\}\}", "", out)
    return out


def _split_front_matter(contenu: str) -> tuple[dict, str]:
    """Sépare le front-matter YAML du corps markdown.

    Format attendu : commence par `---\\n`, contenu YAML jusqu'à un
    `\\n---\\n` isolé, puis le corps markdown (qui peut contenir
    d'autres `---` comme séparateurs de steps).
    """
    if not contenu.startswith("---"):
        raise ValueError("template sans front-matter `---`")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", contenu, re.DOTALL)
    if not m:
        raise ValueError("front-matter mal terminé")
    front = yaml.safe_load(m.group(1)) or {}
    if not isinstance(front, dict):
        raise ValueError("front-matter doit être un mapping YAML")
    return front, m.group(2)


def _split_steps(body: str) -> list[str]:
    """Découpe le corps en blocs de step (séparés par '---' ou '# Step N')."""
    # On split sur les lignes '---' isolées
    blocs = re.split(r"\n\s*---\s*\n", body.strip())
    # Garde uniquement ceux qui commencent par '# Step'
    return [b.strip() for b in blocs if b.strip().lower().startswith("# step")]


def _extract_corps(bloc_step: str) -> str:
    """Retire l'entête `# Step N — ...` et renvoie juste le corps."""
    lignes = bloc_step.splitlines()
    if lignes and lignes[0].lstrip().startswith("#"):
        lignes = lignes[1:]
    return "\n".join(lignes).strip()


def load_sequence(secteur: str, dir_path: Path | None = None) -> Sequence:
    """Charge la séquence d'un secteur (ex 'compta' → compta.md)."""
    d = dir_path or TEMPLATES_DIR
    p = d / f"{secteur}.md"
    if not p.exists():
        raise FileNotFoundError(f"template absent : {p}")
    front, body = _split_front_matter(p.read_text(encoding="utf-8"))
    blocs = _split_steps(body)
    if not blocs:
        raise ValueError(f"aucun step trouvé dans {p}")
    steps = []
    for i, bloc in enumerate(blocs, start=1):
        sujet = str(front.get(f"sujet_step_{i}") or "")
        delai = int(front.get(f"delai_step_{i}_jours") or 0) if i > 1 else 0
        steps.append(
            SequenceStep(
                numero=i,
                sujet=sujet,
                corps=_extract_corps(bloc),
                delai_jours=delai,
            )
        )
    return Sequence(
        secteur=str(front.get("secteur") or secteur),
        nom_lisible=str(front.get("nom_lisible") or secteur),
        steps=steps,
    )


def list_secteurs(dir_path: Path | None = None) -> list[str]:
    d = dir_path or TEMPLATES_DIR
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.md"))
