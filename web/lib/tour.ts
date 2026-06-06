// PA — Tuto interactif de prise en main de « Leads ».
// Source unique des étapes de la visite guidée + détection de l'intention
// « remontre-moi comment marche Leads » (déclenchement par commande à l'agent).

export type TourStep = {
  icon: string;
  titre: string;
  href: string; // route à ouvrir depuis l'étape (« Aller voir »)
  texte: string;
};

// La visite couvre l'outil écran par écran, dans l'ordre du flux de travail.
export const TOUR_STEPS: TourStep[] = [
  {
    icon: "🧭",
    titre: "Accueil — ton poste de pilotage",
    href: "/accueil",
    texte:
      "Le point de départ : Magellan te rappelle l'objectif, ce qu'il y a à faire, et te pointe LA prochaine action prioritaire. Tu peux lui parler directement depuis la barre de commande.",
  },
  {
    icon: "🎯",
    titre: "Cibles — qui tu veux toucher",
    href: "/cibles",
    texte:
      "Tu définis tes verticales (type d'activité + critères). C'est le préalable à toute recherche : c'est là qu'on décide QUI on prospecte.",
  },
  {
    icon: "🔎",
    titre: "Recherches — remplir le pipeline",
    href: "/recherche",
    texte:
      "Tu lances une recherche (par département ou autour d'une adresse + rayon). Le moteur déroule le pipeline en arrière-plan et fait remonter des prospects qualifiés.",
  },
  {
    icon: "👥",
    titre: "Prospects — la liste à traiter",
    href: "/inbox",
    texte:
      "Tous tes leads : recherche, filtres (score, email, ☀️ potentiel), tri et actions groupées (valider / écarter). Le cœur du tri quotidien.",
  },
  {
    icon: "✉️",
    titre: "Campagnes — piloter les envois",
    href: "/campagnes",
    texte:
      "Tu regroupes des leads en campagnes et tu suis l'entonnoir (envoyés → ouverts → répondus). Tu peux affecter chaque campagne à un client : les mails sont alors signés à son nom.",
  },
  {
    icon: "📊",
    titre: "Suivi — le pipeline actionnable",
    href: "/suivi",
    texte:
      "Un Kanban où tu fais avancer chaque lead : envoyer, marquer répondu, relancer, écarter — directement sur les cartes.",
  },
  {
    icon: "🔌",
    titre: "Bornes & Veille — signaux d'intention",
    href: "/bornes",
    texte:
      "Les signaux détectés (flotte VE, ombrières, électrification) à transformer en leads. L'agent peut les convertir automatiquement sous tes garde-fous.",
  },
  {
    icon: "☀️",
    titre: "Solaire — le potentiel terrain",
    href: "/solaire",
    texte:
      "L'analyse satellite (toiture, parking, ombrières) qui personnalise l'accroche commerciale avec des ordres de grandeur prudents.",
  },
  {
    icon: "🤖",
    titre: "Agent — l'autonomie sous garde-fous",
    href: "/agent",
    texte:
      "Le mandat de Magellan : périmètre, budget/jour, cadence, analyse satellite auto + journal des actions. Tu décides jusqu'où il va seul.",
  },
  {
    icon: "🚗",
    titre: "Mode déplacement — mains-libres",
    href: "/accueil",
    texte:
      "En voiture ou en déplacement : le badge « Mode déplacement » sur l'accueil ouvre une vue vocale plein écran. Tu parles, Magellan te répond à voix haute, sans rien toucher.",
  },
];

// Phrases qui déclenchent (re)la visite guidée quand on les dit/écrit à l'agent.
// Tolérant aux accents/variantes.
export function isTourRequest(text: string): boolean {
  const t = text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  const parleDeLeads =
    t.includes("leads") || t.includes("l'outil") || t.includes("loutil") || t.includes("l outil");
  const visite =
    /\bvisite guidee\b/.test(t) ||
    /\b(re)?montre[ -]?moi\b/.test(t) ||
    /\bprise en main\b/.test(t) ||
    /\bcomment (ca |ça |cela )?(marche|fonctionne)\b/.test(t) ||
    /\bdidacticiel\b/.test(t) ||
    /\btuto(riel)?\b/.test(t);
  if (/\bvisite guidee\b/.test(t)) return true;
  return visite && parleDeLeads;
}

// Phrases qui déclenchent l'ouverture de la landing d'analyse satellite
// (« M, analyse cette zone », « analyse satellite », « analyse cette capture »…).
export function isAnalyseRequest(text: string): boolean {
  const t = text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  return (
    /\banalyse\b.*\b(zone|carte|capture|satellite|image|vue)\b/.test(t) ||
    /\b(zone|carte|capture|satellite|image|vue)\b.*\banalyse\b/.test(t) ||
    /\b(reconnait|lis|decris)\b.*\b(image|capture|photo|satellite)\b/.test(t)
  );
}

// Phrases qui déclenchent le mode déplacement (« je suis en voiture », etc.).
export function isDriveRequest(text: string): boolean {
  const t = text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
  return (
    /\bmode (deplacement|voiture|conduite|mains[ -]?libres)\b/.test(t) ||
    /\bje (suis|conduis) (en voiture|en deplacement|sur la route)\b/.test(t) ||
    /\bje pars en\b.*\b(voiture|rdv|deplacement)\b/.test(t)
  );
}
