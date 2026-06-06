// Boucle de retours V1 — détection d'intention côté client.
//   • « fin du retour » → Henry clôt sa session de retours (le pop-up disparaît).
//   • notes d'amélioration adressées à Magellan (Paul) → rangées dans `retours`,
//     remontées à Paul + Claude, jamais appliquées sans validation (CLAUDE.md).
// Volontairement conservateur : on ne capte que des intentions « produit »
// claires, pour ne JAMAIS détourner une demande de navigation/donnée normale.

function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .trim();
}

// Henry tape « fin du retour » (et variantes proches) pour clore sa session.
export function isFeedbackEnd(text: string): boolean {
  const t = normalize(text);
  return (
    /\bfin du retour\b/.test(t) ||
    /\bfin des retours\b/.test(t) ||
    /\bfin de retour\b/.test(t) ||
    /\bj'?ai fini (mon |mes )?retours?\b/.test(t) ||
    /\bterminer? (le |les )?retours?\b/.test(t)
  );
}

// Préfixes explicites (« amélioration: … », « retour: … », « note pour Paul: … »).
const PREFIX_RE =
  /^\s*(amelioration|ameliorations|retour|retours|idee|idees|suggestion|suggestions|bug|feedback|note(?: (?:pour|a) (?:paul|claude))?)\s*[:\-–]\s*/i;

// Tournures « produit » claires : on parle de faire évoluer l'outil, pas d'agir
// sur la donnée. Conservateur pour éviter les faux positifs.
const PHRASE_RES: RegExp[] = [
  /\bil faudrait que (l'?outil|leads|on|tu|magellan)\b/,
  /\bce serait (bien|mieux|cool|top|pratique) (de|si|que|d'?)\b/,
  /\b(l'?outil|leads|magellan) (devrait|pourrait|ne devrait pas)\b/,
  /\btu devrais pouvoir\b/,
  /\bil (manque|manquerait)\b/,
  /\b(note|remonte|consigne)( ca| ça| ceci| cela)? (a |pour )?(paul|claude)\b/,
  /\bj'?ai (un |une )?(retour|amelioration|idee|suggestion|remarque)\b/,
];

// Repère une note d'amélioration adressée à Magellan. Renvoie le texte « nettoyé »
// du préfixe éventuel, ou null si ce n'est pas une note produit.
export function parseImprovementNote(text: string): string | null {
  const raw = text.trim();
  if (!raw) return null;

  const withPrefix = PREFIX_RE.exec(raw);
  if (withPrefix) {
    const rest = raw.slice(withPrefix[0].length).trim();
    return rest || raw.trim();
  }

  const t = normalize(raw);
  if (PHRASE_RES.some((re) => re.test(t))) return raw;
  return null;
}
