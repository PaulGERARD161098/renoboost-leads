// Exemples de références chantiers (preuve sociale) pour amorcer la brique quand
// elle est vide — chargeables en un clic depuis /cibles. Données réalistes
// Hauts-de-France, réversibles (chaque référence reste supprimable). Module pur :
// aucune dépendance serveur, donc testable.

export type ReferenceExemple = {
  nom: string;
  ville: string;
  axe: "solaire" | "ombrieres" | "bornes";
  description: string;
};

export const REFERENCES_EXEMPLES: ReferenceExemple[] = [
  {
    nom: "Brasserie du Pavé",
    ville: "Lille",
    axe: "solaire",
    description: "Centrale PV 380 kWc en autoconsommation sur toiture industrielle, 2024",
  },
  {
    nom: "Hyper Roncq",
    ville: "Roncq",
    axe: "ombrieres",
    description: "Ombrières de parking 140 places + 6 bornes IRVE, 2023",
  },
  {
    nom: "Transports Vandamme",
    ville: "Lens",
    axe: "bornes",
    description: "12 points de charge 22 kW pour flotte utilitaire, 2024",
  },
  {
    nom: "Clinique du Hainaut",
    ville: "Valenciennes",
    axe: "bornes",
    description: "8 bornes visiteurs + 2 rapides 50 kW, 2025",
  },
];
