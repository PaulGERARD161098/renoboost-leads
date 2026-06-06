// Lancement V1 — contenu de la cinématique de bienvenue d'Henry.
// Une « vidéo » scriptée : suite de cartes auto-déroulées (~20 s au total),
// skippable, jouée une seule fois (cf. profiles.welcomed_v1_at).

// Henry est identifié par son adresse @renoboostia.fr (cf. migration 0020).
export function isHenry(email: string | null | undefined): boolean {
  return (email ?? "").trim().toLowerCase() === "henry.huvey@renoboostia.fr";
}

export const WELCOME_V1_TITLE =
  "Bienvenue sur LEADS, Henry ! Voilà à quoi a servi ton argent !";

export type WelcomeSlide = {
  icon: string;
  texte: string;
  // Texte lu à voix haute (synthèse navigateur) — sans emoji, phrasé naturel.
  voix: string;
  // Durée d'affichage (ms). Le total ≈ 20 s.
  duree: number;
};

export const WELCOME_V1_SLIDES: WelcomeSlide[] = [
  {
    icon: "🚀",
    texte:
      "Bienvenue sur **Leads, V1** — ton couteau suisse pour chercher des contacts B2B. On sait que tu en étais impatient…",
    voix: "Bienvenue sur Leads, version 1 : ton couteau suisse pour chercher des contacts B2B. On sait que tu en étais impatient.",
    duree: 4500,
  },
  {
    icon: "🎯",
    texte:
      "**Cibles & Recherches** — tu définis qui tu veux toucher, tu lances une recherche, le moteur déroule le pipeline et fait remonter des prospects qualifiés.",
    voix: "Tu définis qui tu veux toucher, tu lances une recherche, et le moteur fait remonter des prospects qualifiés.",
    duree: 4000,
  },
  {
    icon: "👥",
    texte:
      "**Prospects, Suivi & Campagnes** — tu tries, tu valides, tu fais avancer chaque lead, et tu pilotes tes envois jusqu'à la réponse.",
    voix: "Tu tries tes prospects, tu fais avancer chaque lead, et tu pilotes tes campagnes jusqu'à la réponse.",
    duree: 4000,
  },
  {
    icon: "🔌",
    texte:
      "**Veille, Bornes & Solaire** — des signaux d'intention (flotte VE, ombrières, électrification) et l'analyse satellite pour personnaliser l'accroche.",
    voix: "Une veille sur les signaux d'intention, et l'analyse satellite pour personnaliser ton accroche commerciale.",
    duree: 4000,
  },
  {
    icon: "🧭",
    texte:
      "**Magellan, ton copilote** — il te fait le point au login, te propose la prochaine action, et peut même bosser tout seul sous tes garde-fous.",
    voix: "Et Magellan, ton copilote : il te fait le point, te propose la prochaine action, et peut bosser tout seul sous garde-fous.",
    duree: 4000,
  },
  {
    icon: "🪜",
    texte:
      "Ça valait le coup de **pousser Paul dans l'escalier**… Teste tout, et fais un retour complet ! 😏",
    voix: "Ça valait le coup de pousser Paul dans l'escalier. Teste tout, et fais un retour complet !",
    duree: 4500,
  },
];

export const WELCOME_V1_TOTAL_MS = WELCOME_V1_SLIDES.reduce(
  (s, x) => s + x.duree,
  0,
);
