// Catalogue d'« intentions d'achat » d'une Cible et compilation vers les filtres
// de découverte existants (NAF + effectif + signaux).
//
// Pourquoi : la découverte (étages 0-2 du moteur) se fait par **NAF + effectif**.
// Le commercial, lui, raisonne par **intention** : « je veux des boîtes qui
// veulent électrifier leur flotte / piloter leur conso / réduire leur fiscalité ».
// SIRENE/Places n'ont pas de champ « intention » → on traduit chaque intention en
// son **meilleur proxy sectoriel** (NAF) + des **signaux** (mots-clés qui colorent
// le scoring L4 et le mail). C'est un proxy honnête, pas une vérité terrain :
// l'utilisateur garde la main sur les champs après application.
//
// Les ids cochés sont persistés dans `config.intentions` (clé JSONB) pour que la
// future interconnexion Veille (porte d) puisse cibler les mêmes intentions.

export type IntentionId = "flotte_ve" | "conso_elec" | "fiscal";

export interface Intention {
  id: IntentionId;
  label: string;
  /** Pitch court montré sous la puce. */
  description: string;
  /** Préfixes NAF servant de proxy de découverte (additifs, dédupliqués). */
  secteursNaf: string[];
  /** Effectif minimal suggéré (n'écrase pas une saisie existante). */
  effectifMinSuggere: number;
  /** Mots-clés injectés dans « signaux recherchés » (scoring L4 + mail). */
  signaux: string[];
}

// NB cartographie NAF = jugement métier v1, à ajuster (un seul endroit).
export const INTENTIONS: Intention[] = [
  {
    id: "flotte_ve",
    label: "Électrifier sa flotte",
    description:
      "Entreprises à flotte de véhicules (transport, BTP, logistique, services) → bornes IRVE.",
    // Transport, logistique, poste, BTP, services bâtiment, déchets, location auto.
    secteursNaf: ["49", "52", "53", "41", "42", "43", "81", "38", "77.11"],
    effectifMinSuggere: 20,
    signaux: [
      "flotte de véhicules",
      "immatriculations VE récentes",
      "véhicules de société",
      "besoin de bornes de recharge",
    ],
  },
  {
    id: "conso_elec",
    label: "Piloter sa conso élec",
    description:
      "Sites énergivores avec toiture/parking exploitables → ombrières + autoconsommation.",
    // Industries manufacturières, entreposage (dont froid), data centers.
    secteursNaf: [
      "10",
      "20",
      "22",
      "23",
      "24",
      "25",
      "26",
      "27",
      "28",
      "29",
      "30",
      "31",
      "32",
      "33",
      "52",
      "63.11",
    ],
    effectifMinSuggere: 20,
    signaux: [
      "grande toiture",
      "site énergivore",
      "parking exploitable",
      "autoconsommation photovoltaïque",
      "facture électricité élevée",
    ],
  },
  {
    id: "fiscal",
    label: "Réduire sa facture fiscale",
    description:
      "Profil investisseur en équipement productif/vert → levier suramortissement.",
    // Actifs lourds éligibles au suramortissement : industrie, transport, BTP, agriculture.
    secteursNaf: ["10", "20", "25", "28", "29", "49", "41", "42", "43", "01"],
    effectifMinSuggere: 20,
    signaux: [
      "suramortissement",
      "investissement équipement",
      "amortissement accéléré",
      "rentabilité solide",
    ],
  },
];

export function intentionParId(id: string): Intention | undefined {
  return INTENTIONS.find((i) => i.id === id);
}

/** Intentions d'une Cible lues depuis sa `config.intentions` (JSONB), filtrées/typées. */
export function intentionsDeConfig(
  config: Record<string, unknown> | null | undefined,
): Intention[] {
  const raw = config?.intentions;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((v): v is string => typeof v === "string")
    .map((id) => intentionParId(id))
    .filter((i): i is Intention => i !== undefined);
}

// ── Pont Intentions ⟶ Veille ─────────────────────────────────────────────
// Chaque intention d'achat se traduit (quand c'est possible) en types de signaux
// de veille « réels » — ceux qui prouvent l'intention sur le terrain (vs le proxy
// sectoriel NAF). `fiscal` n'a pas de signal direct : c'est un profil financier,
// pas un événement détectable en veille.
export const SIGNAL_TYPES_PAR_INTENTION: Record<IntentionId, string[]> = {
  flotte_ve: ["ve_flotte", "irve", "electrification"],
  conso_elec: ["ombrieres", "electrification"],
  fiscal: [],
};

/** Union dédupliquée des types de signaux veille couverts par des intentions. */
export function signalTypesPourIntentions(ids: string[]): string[] {
  const out: string[] = [];
  for (const id of ids) {
    for (const t of SIGNAL_TYPES_PAR_INTENTION[id as IntentionId] ?? []) {
      if (!out.includes(t)) out.push(t);
    }
  }
  return out;
}

/** Intentions concernées par un type de signal veille (réciproque, pour le tri). */
export function intentionsConcernantSignal(type: string | null): IntentionId[] {
  if (!type) return [];
  return (Object.keys(SIGNAL_TYPES_PAR_INTENTION) as IntentionId[]).filter((id) =>
    SIGNAL_TYPES_PAR_INTENTION[id].includes(type),
  );
}

/** Champs de la Cible impactés par les intentions (forme « brouillon » du formulaire). */
export interface ChampsCible {
  secteursNaf: string[];
  signaux: string[];
  /** Effectif min courant ; `null` = non saisi. */
  effectifMin: number | null;
}

function fusionnerUnique(base: string[], ajouts: string[]): string[] {
  const vus = new Set(base.map((s) => s.trim().toLowerCase()).filter(Boolean));
  const out = [...base];
  for (const a of ajouts) {
    const cle = a.trim().toLowerCase();
    if (cle && !vus.has(cle)) {
      vus.add(cle);
      out.push(a);
    }
  }
  return out;
}

/**
 * Compile la sélection d'intentions sur les champs courants, de façon **additive**
 * et **idempotente** : on n'enlève jamais ce que l'utilisateur a saisi, on déduplique
 * (insensible à la casse/espaces), et on ne suggère un effectif min que s'il est vide.
 */
export function appliquerIntentions(
  ids: IntentionId[],
  current: ChampsCible,
): ChampsCible {
  const choisies = ids
    .map((id) => intentionParId(id))
    .filter((i): i is Intention => i !== undefined);

  let secteursNaf = current.secteursNaf;
  let signaux = current.signaux;
  for (const intention of choisies) {
    secteursNaf = fusionnerUnique(secteursNaf, intention.secteursNaf);
    signaux = fusionnerUnique(signaux, intention.signaux);
  }

  // Effectif : suggère le plancher le plus prudent (max des suggestions) si vide.
  let effectifMin = current.effectifMin;
  if (effectifMin == null && choisies.length > 0) {
    effectifMin = Math.max(...choisies.map((i) => i.effectifMinSuggere));
  }

  return { secteursNaf, signaux, effectifMin };
}
