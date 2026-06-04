import { createClient } from "@/lib/supabase/server";

const SOURCE_LABEL: Record<string, string> = {
  inbox: "Onglet Prospects",
  suivi: "Onglet Suivi",
  campagnes: "Onglet Campagnes",
  reprise_banner: "Bandeau Reprise",
  welcome_modal: "Modale d'accueil",
};

// Valeur des suggestions (charte point 7 : « une suggestion utile = une
// suggestion suivie »). Agrège les clics tracés sur les actions recommandées,
// pour visualiser la boucle d'apprentissage.
export async function SuggestionValue() {
  const supabase = await createClient();
  const since = new Date(Date.now() - 30 * 86_400_000).toISOString();
  const { data } = await supabase
    .from("suggestion_clicks")
    .select("source, action")
    .gt("at", since)
    .limit(5000);
  const rows = (data as { source: string; action: string }[] | null) ?? [];

  const parSource: Record<string, number> = {};
  const parAction: Record<string, number> = {};
  for (const r of rows) {
    parSource[r.source] = (parSource[r.source] ?? 0) + 1;
    parAction[r.action] = (parAction[r.action] ?? 0) + 1;
  }
  const topActions = Object.entries(parAction)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const sources = Object.entries(parSource).sort((a, b) => b[1] - a[1]);

  return (
    <div className="mt-8">
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        📈 Valeur des suggestions (30 derniers jours)
      </h2>
      <p className="mb-2 text-xs text-[var(--muted)]">
        Boucle fermée : les actions les plus suivies remontent en tête des bandes
        « Où on en est » (★ = la plus suivie de l&apos;onglet).
      </p>
      <div className="rounded-xl border border-[var(--border)] bg-white p-5">
        {rows.length === 0 ? (
          <p className="text-sm text-[var(--muted)]">
            Aucune suggestion suivie pour l&apos;instant. Les clics sur les actions
            recommandées (bandeaux, modale d&apos;accueil) s&apos;afficheront ici —
            de quoi mesurer ce qui aide vraiment.
          </p>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2">
            <div>
              <div className="mb-1 text-3xl font-bold">{rows.length}</div>
              <div className="mb-3 text-sm text-[var(--muted)]">
                suggestions suivies
              </div>
              <div className="space-y-1.5">
                {sources.map(([s, n]) => (
                  <div key={s} className="flex items-center justify-between text-sm">
                    <span className="text-[var(--muted)]">{SOURCE_LABEL[s] ?? s}</span>
                    <span className="font-medium">{n}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                Actions les plus suivies
              </div>
              <ul className="space-y-1.5">
                {topActions.map(([action, n]) => (
                  <li key={action} className="flex items-center justify-between gap-2 text-sm">
                    <span className="truncate">{action}</span>
                    <span className="shrink-0 rounded-full bg-[var(--brand)]/10 px-2 py-0.5 text-xs font-semibold text-[var(--brand)]">
                      {n}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
