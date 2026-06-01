export const metadata = {
  title: "Mode d'emploi — ReSign CRM",
};

const ETAGES: {
  num: string;
  titre: string;
  fait: string;
  source: string;
  cout: string;
}[] = [
  {
    num: "1",
    titre: "Découverte",
    fait: "Trouve des établissements (nom, adresse, téléphone, site web) sur une zone géographique et un mot-clé donnés.",
    source: "Google Places API",
    cout: "~0,05 €/lead",
  },
  {
    num: "2",
    titre: "Entreprises",
    fait: "Rattache chaque établissement à son entreprise : SIREN, code NAF, tranche d'effectif, forme juridique, dirigeant.",
    source: "API data.gouv.fr (registres officiels)",
    cout: "gratuit",
  },
  {
    num: "3",
    titre: "Contacts",
    fait: "Recherche les emails de contact (scraping des mentions légales + reconstruction par patterns).",
    source: "Scraping web public",
    cout: "gratuit",
  },
  {
    num: "4",
    titre: "Prospection",
    fait: "Attribue à chaque lead un score d'intérêt (0-100), la raison du score et un pitch proposé.",
    source: "Claude API (Anthropic)",
    cout: "~0,005 €/lead (Haiku)",
  },
];

const SERVICES: { nom: string; role: string }[] = [
  { nom: "Google Places", role: "découverte des établissements (étage 1)." },
  { nom: "data.gouv.fr", role: "identité légale des entreprises — SIREN, NAF, dirigeant (étage 2)." },
  { nom: "Scraping web", role: "recherche des emails de contact (étage 3)." },
  { nom: "Anthropic (Claude)", role: "scoring d'intérêt et pitch par lead (étage 4)." },
  { nom: "Supabase", role: "base de données des leads + authentification (liens de connexion)." },
  { nom: "Resend", role: "envoi des emails (liens de connexion, et cold mailing si activé)." },
  { nom: "Vercel", role: "hébergement de ce site (ReSign CRM)." },
];

const COUTS: { volume: string; pipeline: string; abos: string }[] = [
  { volume: "200 leads", pipeline: "~11 € (Haiku) à ~80 € (complet payant)", abos: "+ ~95 €/mois si abos payants" },
  { volume: "500 leads", pipeline: "~200 € (pipeline complet payant)", abos: "+ ~95 €/mois" },
  { volume: "1000 leads", pipeline: "~400 € (pipeline complet payant)", abos: "+ ~95 €/mois" },
];

export default function ModeEmploiPage() {
  return (
    <div className="max-w-3xl">
      <h1 className="mb-1 text-2xl font-bold">Mode d&apos;emploi</h1>
      <p className="mb-6 text-sm text-[var(--muted)]">
        Ce que fait l&apos;outil, avec quelles connexions, et combien ça coûte —
        description factuelle.
      </p>

      {/* À quoi ça sert */}
      <Section titre="À quoi sert l'outil">
        <p>
          RénoBoost Leads est une chaîne de prospection B2B qui construit des
          listes de prospects qualifiés. À partir d&apos;une zone géographique et
          d&apos;un type d&apos;activité, elle découvre des établissements, les
          rattache à leur entreprise, cherche leurs contacts et évalue leur
          intérêt commercial. Ce site (ReSign CRM) est l&apos;interface qui
          permet de consulter, suivre et travailler ces leads.
        </p>
      </Section>

      {/* Les 4 étages */}
      <Section titre="Les 4 étages du pipeline">
        <p className="mb-4">
          Le traitement se fait en quatre étapes indépendantes. On peut
          n&apos;en lancer qu&apos;une partie ; les étages 2 et 3 sont gratuits.
        </p>
        <div className="space-y-3">
          {ETAGES.map((e) => (
            <div
              key={e.num}
              className="rounded-xl border border-[var(--border)] bg-white p-4"
            >
              <div className="mb-1 flex items-center justify-between">
                <h3 className="font-semibold">
                  Étage {e.num} — {e.titre}
                </h3>
                <span
                  className={`rounded px-2 py-0.5 text-xs font-semibold ${
                    e.cout === "gratuit"
                      ? "bg-green-100 text-green-700"
                      : "bg-slate-100 text-slate-600"
                  }`}
                >
                  {e.cout}
                </span>
              </div>
              <p className="text-sm text-[var(--muted)]">{e.fait}</p>
              <p className="mt-1 text-xs text-[var(--muted)]">
                Source : {e.source}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* Connexions */}
      <Section titre="Connexions & services">
        <p className="mb-3">
          L&apos;outil s&apos;appuie sur des services externes. Chacun a un rôle
          précis :
        </p>
        <ul className="space-y-1.5 text-sm">
          {SERVICES.map((s) => (
            <li key={s.nom}>
              <span className="font-semibold">{s.nom}</span> — {s.role}
            </li>
          ))}
        </ul>
      </Section>

      {/* Coûts */}
      <Section titre="Coûts de fonctionnement">
        <p className="mb-3">
          Avec le modèle par défaut (Claude Haiku), le pipeline complet coûte
          environ <strong>0,055 €/lead</strong>, soit <strong>~11 € pour
          200 leads</strong>. Les coûts montent si l&apos;on active des sources
          payantes (Pappers, Dropcontact, Societeinfo) à la place des sources
          gratuites.
        </p>
        <div className="overflow-hidden rounded-xl border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs text-[var(--muted)]">
              <tr>
                <th className="px-3 py-2 font-medium">Volume</th>
                <th className="px-3 py-2 font-medium">Coût du run</th>
                <th className="px-3 py-2 font-medium">Abonnements fixes</th>
              </tr>
            </thead>
            <tbody>
              {COUTS.map((c) => (
                <tr key={c.volume} className="border-t border-[var(--border)]">
                  <td className="px-3 py-2 font-medium">{c.volume}</td>
                  <td className="px-3 py-2 text-[var(--muted)]">{c.pipeline}</td>
                  <td className="px-3 py-2 text-[var(--muted)]">{c.abos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm text-[var(--muted)]">
          Garde-fous : le moteur refuse de démarrer si l&apos;estimation dépasse
          le budget configuré (30 € par run par défaut), avec aussi un plafond de
          leads et une limite de débit. Le scoring Claude est mis en cache : un
          re-run à paramètres identiques coûte 0 €.
        </p>
      </Section>

      {/* RGPD */}
      <Section titre="Conformité RGPD">
        <p>
          La base légale est l&apos;intérêt légitime en contexte B2B. Chaque run
          génère un registre RGPD. L&apos;outil dispose d&apos;une commande
          d&apos;effacement (par email, SIREN ou identifiant d&apos;établissement)
          et d&apos;une purge automatique des données anciennes.
        </p>
      </Section>

      {/* Limites */}
      <Section titre="Limites honnêtes">
        <ul className="space-y-1.5 text-sm">
          <li>
            <span className="font-semibold">Match SIREN (étage 2)</span> : 70-85 %
            avec la source gratuite, 92-95 % avec une source payante.
          </li>
          <li>
            <span className="font-semibold">Emails trouvés (étage 3)</span> :
            50-65 % en gratuit, 80-90 % en payant — et non vérifiés par défaut.
          </li>
          <li className="text-[var(--brand)]">
            ⚠️ Ne jamais envoyer de cold email sans vérification préalable des
            adresses (un taux de rebond &gt; 15 % grille le domaine).
          </li>
        </ul>
      </Section>
    </div>
  );
}

function Section({
  titre,
  children,
}: {
  titre: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <h2 className="mb-2 text-lg font-semibold">{titre}</h2>
      <div className="text-sm leading-relaxed text-slate-700">{children}</div>
    </section>
  );
}
