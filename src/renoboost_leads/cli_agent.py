"""CLI agent — `renoboost-leads agent run "..."` et `renoboost-leads agent chat`.

Branché sur `cli.py` via `cli.add_command(agent_group)`.
"""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group(name="agent")
def agent_group() -> None:
    """Pilotage de la prospection par l'agent Copilote."""


@agent_group.command(name="run")
@click.argument("instruction", nargs=-1, required=True)
def agent_run(instruction: tuple[str, ...]) -> None:
    """Exécute UN cycle de l'agent avec l'instruction donnée puis sort.

    Exemple :
        renoboost-leads agent run "diagnostique la dernière session"
    """
    from .agent.runner import run_cycle

    instr = " ".join(instruction)
    try:
        result = run_cycle(instr)
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]✗ {type(e).__name__} : {e}[/red]")
        sys.exit(1)

    _afficher_resultat(result)


@agent_group.command(name="chat")
def agent_chat() -> None:
    """REPL interactif : tape ton instruction, l'agent répond, recommence.

    Tape 'quit', 'exit' ou Ctrl-D pour sortir.
    """
    from .agent.runner import run_cycle

    console.print(
        Panel.fit(
            "[bold cyan]Copilote RénoBoost[/bold cyan]\n"
            "Tape ton instruction (quit/exit pour sortir).",
            border_style="cyan",
        )
    )
    while True:
        try:
            instr = console.input("[bold green]>>> [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye.[/dim]")
            return
        if not instr:
            continue
        if instr.lower() in {"quit", "exit", "q"}:
            return
        try:
            result = run_cycle(instr)
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]✗ {type(e).__name__} : {e}[/red]")
            continue
        _afficher_resultat(result)


@agent_group.command(name="journal")
@click.option("-n", "--limit", default=10, type=int, help="Nombre d'entrées récentes.")
def agent_journal(limit: int) -> None:
    """Affiche les dernières entrées du journal de l'agent."""
    from .agent.config import load_agent_config
    from .agent.journal import Journal

    cfg = load_agent_config()
    j = Journal(path=cfg.journal_path_abs())
    entries = j.read_recent(n=limit)
    if not entries:
        console.print("[dim]Journal vide.[/dim]")
        return
    for e in entries:
        console.print(e)
        console.print()


@agent_group.command(name="budget")
def agent_budget() -> None:
    """Affiche l'état budget €/jour de l'agent."""
    from .agent.budget import BudgetGuard
    from .agent.config import load_agent_config

    cfg = load_agent_config()
    b = BudgetGuard(cap_eur_par_jour=cfg.budget_eur_par_jour, path=cfg.budget_path_abs())
    console.print(
        Panel.fit(
            f"[bold]Budget agent[/bold]\n"
            f"Cap          : {b.cap:.2f} €/jour\n"
            f"Consommé     : {b.cumul_eur:.4f} €\n"
            f"Reste        : {b.reste_eur:.4f} €",
            border_style="yellow",
        )
    )


@agent_group.command(name="metrics")
def agent_metrics() -> None:
    """Affiche les métriques cumulées de l'agent (cycles, coût, par outil)."""
    from rich.table import Table

    from .agent.metrics import MetricsStore

    m = MetricsStore().load()
    console.print(
        Panel.fit(
            f"[bold]Métriques agent (cumul)[/bold]\n"
            f"Cycles      : {m.cycles_total}\n"
            f"Outils      : {m.outils_total}\n"
            f"Coût total  : {m.cout_total_eur:.4f} €",
            border_style="cyan",
        )
    )
    if not m.par_outil:
        console.print("[dim]Aucun outil appelé.[/dim]")
        return
    t = Table(title="Par outil", show_lines=False)
    t.add_column("Outil")
    t.add_column("Appels", justify="right")
    t.add_column("Erreurs", justify="right")
    t.add_column("Temps total (s)", justify="right")
    t.add_column("Moy (ms)", justify="right")
    for name in sorted(m.par_outil, key=lambda n: -m.par_outil[n].count):
        tm = m.par_outil[name]
        moy_ms = (tm.duration_total_s / tm.count * 1000) if tm.count else 0.0
        t.add_row(
            name,
            str(tm.count),
            str(tm.erreurs),
            f"{tm.duration_total_s:.3f}",
            f"{moy_ms:.1f}",
        )
    console.print(t)


def _afficher_resultat(result) -> None:
    console.print()
    if result.outils_appeles:
        noms = " → ".join(o["name"] for o in result.outils_appeles)
        console.print(f"[dim]Outils : {noms}[/dim]")
    console.print(
        Panel(result.texte_final or "(rien)", title="Copilote", border_style="cyan")
    )
    console.print(
        f"[dim]tours={result.tours}  coût={result.cout_eur:.4f}€  "
        f"in={result.tokens_input}  out={result.tokens_output}  "
        f"stop={result.stop_reason}[/dim]"
    )
    if result.erreur:
        console.print(f"[red]⚠ {result.erreur}[/red]")
