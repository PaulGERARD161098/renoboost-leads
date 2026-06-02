export const metadata = {
  title: "Mode d'emploi — ReSign CRM",
};

const ETAGES = [
  { num: "1", titre: "Découverte", fait: "Établissements (nom, adresse, tél, site) sur une zone + un type d'activité.", source: "Google Places", cout: "~0,05 €/lead" },
  { num: "2", titre: "Entreprises", fait: "SIREN, code NAF, effectif, forme juridique, dirigeant.", source: "data.gouv.fr", cout: "gratuit" },
  { num: "3", titre: "Contacts", fait: "Emails (mentions légales + reconstruction par patterns).", source: "Scraping web", cout: "gratuit" },
  { num: "4", titre: "Prospection", fait: "Score d'intérêt 0-100 + raison + pitch e-mail proposé.", source: "Claude (Anthropic)", cout: "~0,005 €/lead" },
];

const ONGLETS = [
  { nom: "Prospects", desc: "La liste à traiter. Recherche, filtres (score, email, ☀️ potentiel), tri, sélection multiple + actions groupées (valider/écarter)." },
  { nom: "Suivi", desc: "Le pipeline en Kanban actionnable : Envoyer · Marquer répondu · Relancer · Écarter directement sur les cartes." },
  { nom: "Veille", desc: "Signaux d'intention détectés sur le web (flotte VE, ombrières, électrification) ; à transformer en leads." },
  { nom: "Recherches", desc: "Lancer une recherche (par département OU autour d'une adresse + rayon) et voir le détail/résultats de chaque run." },
  { nom: "Cibles", desc: "Définir les verticales (type d'activité + critères) — préalable à toute recherche." },
  { nom: "Tableau de bord", desc: "Vue d'ensemble : KPIs, à traiter en priorité, distribution des scores, funnel, meilleurs départements, relances dues, potentiels solaires." },
  { nom: "Agent", desc: "Le mandat de Magellan : autonomie, périmètre, budget/jour, cadence, analyse satellite auto + journal des actions." },
  { nom: "Mode d'emploi", desc: "Cette page." },
];

const SERVICES = [
  { nom: "Google Places", role: "découverte des établissements (étage 1)." },
  { nom: "data.gouv.fr", role: "identité légale des entreprises (étage 2, gratuit)." },
  { nom: "Scraping web", role: "emails de contact (étage 3, gratuit)." },
  { nom: "Anthropic (Claude)", role: "scoring, pitch, Magellan, vision satellite." },
  { nom: "IGN Géoplateforme", role: "vues aériennes (orthophotos) pour le potentiel solaire." },
  { nom: "BAN (adresse.data.gouv)", role: "géocodage des adresses (gratuit)." },
  { nom: "Supabase", role: "base de données + authentification (liens de connexion)." },
  { nom: "Resend", role: "envoi des e-mails (connexion + cold mailing si activé)." },
  { nom: "Instantly", role: "cold mailing + remontée des ouvertures/réponses/rebonds (si activé)." },
  { nom: "Vercel", role: "hébergement du site + cron de l'agent autonome." },
  { nom: "Railway", role: "worker qui exécute les recherches (le vrai pipeline)." },
];

const COUTS = [
  { volume: "200 leads", pipeline: "~11 € (Haiku) → ~80 € (sources payantes)" },
  { volume: "500 leads", pipeline: "~200 € (pipeline complet payant)" },
  { volume: "1000 leads", pipeline: "~400 € (pipeline complet payant)" },
];

export default function ModeEmploiPage() {
  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Mode d&apos;emploi</h1>
        <p className="text-sm text-[var(--muted)]">
          Comment fonctionne l&apos;outil, écran par écran — description factuelle.
        </p>
      </div>

      <Card emoji="🎯" titre="À quoi sert l'outil">
        <p>
          RénoBoost construit des listes de <strong>prospects B2B qualifiés</strong> à
          partir d&apos;une zone et d&apos;un type d&apos;activité, puis aide à les
          travailler. Ce site (CRM « ReSign ») est l&apos;interface de pilotage ;
          <strong> Magellan</strong> est l&apos;assistant IA intégré.
        </p>
      </Card>

      <Card emoji="⚙️" titre="Le pipeline (4 étages)">
        <p className="mb-3">
          Une recherche déroule 4 étages, exécutés en tâche de fond par le worker.
        </p>
        <div className="space-y-2">
          {ETAGES.map((e) => (
            <div key={e.num} className="rounded-lg border border-[var(--border)] p-3">
              <div className="mb-1 flex items-center justify-between">
                <span className="font-semibold">Étage {e.num} — {e.titre}</span>
                <span className={`rounded px-2 py-0.5 text-xs font-semibold ${e.cout === "gratuit" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"}`}>{e.cout}</span>
              </div>
              <p className="text-sm text-[var(--muted)]">{e.fait}</p>
              <p className="mt-1 text-xs text-[var(--muted)]">Source : {e.source}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card emoji="🧭" titre="Les onglets du CRM">
        <ul className="space-y-2 text-sm">
          {ONGLETS.map((o) => (
            <li key={o.nom}>
              <span className="font-semibold">{o.nom}</span> — {o.desc}
            </li>
          ))}
        </ul>
      </Card>

      <Card emoji="📍" titre="Cibler une zone">
        <p>
          Dans <strong>Recherches</strong>, deux modes : <strong>Par département</strong>{" "}
          (ex. 59) ou <strong>Autour d&apos;une adresse</strong> (saisis l&apos;adresse
          d&apos;une zone d&apos;activité + un rayon en km — idéal pour viser une bonne
          zone précise). Tu peux <strong>enregistrer des zones</strong> réutilisables et
          les relancer en un clic.
        </p>
      </Card>

      <Card emoji="📊" titre="Le scoring & le score global">
        <ul className="space-y-1.5 text-sm">
          <li><strong>Score commercial</strong> (0-100) : intérêt du prospect, calculé par l&apos;IA (étage 4). ≥75 = top lead.</li>
          <li><strong>Score foncier</strong> (0-100) : potentiel solaire estimé sur la vue satellite (voir ci-dessous).</li>
          <li><strong>Score global</strong> : combine les deux (60 % commercial / 40 % foncier). C&apos;est lui qui classe les leads « à traiter en priorité ».</li>
          <li>Chaque fiche affiche <strong>« Pourquoi ce score »</strong> (la justification).</li>
        </ul>
      </Card>

      <Card emoji="🛰️" titre="Potentiel solaire (vue satellite IGN)">
        <p>
          Sur une fiche, le bouton <strong>Analyser</strong> récupère la vue aérienne
          IGN du site et fait évaluer par l&apos;IA le potentiel <strong>toiture</strong> et{" "}
          <strong>parking/ombrières</strong> (présence, surface estimée, score). Les
          leads à fort potentiel sont marqués <strong>☀️</strong> et filtrables dans
          Prospects. Peut aussi tourner en automatique (voir Agent).
        </p>
      </Card>

      <Card emoji="💬" titre="Magellan — l'assistant">
        <p className="mb-2">
          Bulle en bas à droite, sur toutes les pages. Il peut :
        </p>
        <ul className="space-y-1.5 text-sm">
          <li>répondre à tes questions sur l&apos;outil et la marche à suivre ;</li>
          <li>analyser tes données (meilleurs leads, recherches, départements, taux, rebonds) ;</li>
          <li>suggérer où prospecter et <strong>lancer une recherche</strong> (après ta confirmation) ;</li>
          <li>rédiger des exemples de <strong>cold mail</strong> ;</li>
          <li><strong>analyser le potentiel solaire</strong> d&apos;un lead ;</li>
          <li>livrer un résultat propre (leads cliquables vers leur fiche).</li>
        </ul>
      </Card>

      <Card emoji="🔔" titre="Veille d'intentions">
        <p>
          Chaque jour, l&apos;agent cherche sur le web des <strong>signaux d&apos;achat</strong>{" "}
          sur le périmètre des cibles (PME du Nord qui électrifient leur flotte,
          projettent des ombrières, etc.). Chaque signal a un <strong>déclencheur daté</strong>,
          une <strong>source</strong>, des scores intention/fit et un <strong>angle</strong>{" "}
          de prise de contact. Tu les retrouves dans l&apos;onglet <strong>Veille</strong>{" "}
          (et un badge à la connexion) ; un clic « En faire un lead » les bascule dans
          le pipeline.
        </p>
      </Card>

      <Card emoji="🤖" titre="L'agent autonome">
        <p>
          Dans l&apos;onglet <strong>Agent</strong>, tu définis un <strong>mandat</strong>{" "}
          (cibles, départements, budget/jour, cadence, max/jour). Si l&apos;<strong>autonomie</strong>{" "}
          est activée, Magellan <strong>lance des recherches tout seul</strong> dans ces
          limites — même quand tu n&apos;es pas connecté. Option <strong>analyse satellite
          automatique</strong> pour qualifier le foncier en continu. Un journal trace
          toutes ses actions. Garde-fou : plafond budget/jour bloquant.
        </p>
      </Card>

      <Card emoji="📨" titre="Suivi, relances & notes">
        <ul className="space-y-1.5 text-sm">
          <li><strong>Suivi</strong> : fais avancer chaque lead (Validé → Envoyé → Ouvert → Répondu → À relancer) depuis les cartes.</li>
          <li><strong>Relance datée</strong> : planifie une date sur la fiche ; les relances dues remontent au tableau de bord.</li>
          <li><strong>Notes</strong> : consigne tes appels/échanges sur la fiche (historique horodaté).</li>
        </ul>
      </Card>

      <Card emoji="🔌" titre="Connexions & services">
        <ul className="space-y-1.5 text-sm">
          {SERVICES.map((s) => (
            <li key={s.nom}><span className="font-semibold">{s.nom}</span> — {s.role}</li>
          ))}
        </ul>
      </Card>

      <Card emoji="💰" titre="Coûts de fonctionnement">
        <p className="mb-3">
          Pipeline complet (modèle Haiku) ≈ <strong>0,055 €/lead</strong>. Repères :
        </p>
        <div className="overflow-hidden rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm">
            <tbody>
              {COUTS.map((c) => (
                <tr key={c.volume} className="border-t border-[var(--border)] first:border-0">
                  <td className="px-3 py-2 font-medium">{c.volume}</td>
                  <td className="px-3 py-2 text-[var(--muted)]">{c.pipeline}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm text-[var(--muted)]">
          Garde-fous : budget plafond par recherche, plafond budget/jour de l&apos;agent,
          analyse satellite plafonnée. Le scoring est mis en cache (re-run identique = 0 €).
        </p>
      </Card>

      <Card emoji="⚖️" titre="Conformité RGPD">
        <p>
          Base légale : intérêt légitime B2B. Registre RGPD par recherche, effacement
          d&apos;un lead (bouton « Oublier » sur la fiche) et purge des données anciennes.
        </p>
      </Card>

      <Card emoji="⚠️" titre="Limites honnêtes">
        <ul className="space-y-1.5 text-sm">
          <li>Match SIREN : 70-85 % en gratuit, 92-95 % en payant.</li>
          <li>Emails trouvés : 50-65 % en gratuit — <strong>toujours vérifier avant un envoi de masse</strong> (rebond &gt;15 % grille le domaine).</li>
          <li>Rebonds (bounces) : suivis seulement quand l&apos;envoi Instantly est actif.</li>
          <li>Précision satellite : optimale sur les leads issus de recherches réelles (coordonnées exactes).</li>
        </ul>
      </Card>
    </div>
  );
}

function Card({
  emoji,
  titre,
  children,
}: {
  emoji: string;
  titre: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-white p-5">
      <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
        <span>{emoji}</span> {titre}
      </h2>
      <div className="text-sm leading-relaxed text-slate-700">{children}</div>
    </section>
  );
}
