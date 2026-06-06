"use client";

import { useEffect, useState } from "react";

// Message d'accueil contextuel sur le poste de pilotage :
//   • première connexion de la journée → « Bienvenue sur Leads »
//   • reconnexions → messages rotatifs personnalisés (« De retour, Henry ? »)
//   • variantes selon l'heure (tard le soir → « 23h, tu es sûr ? »)
//   • clins d'œil si l'on revient plusieurs fois (« Oublié quelque chose ? »,
//     « Haut les cœurs, on y retourne ! »)
// Le comptage des passages est purement LOCAL (localStorage, par jour) — aucune
// donnée serveur, aucun migration. Rendu initial neutre pour éviter tout
// décalage d'hydratation ; le message contextuel s'affiche au montage client.

function pick(list: string[], seed: number): string {
  return list[seed % list.length];
}

// Petites pépites de culture générale (philo, grands inventeurs, grandes figures
// françaises…) — affichées en petit à partir du 3ᵉ passage du jour, pour détendre.
const SAVAIS_TU: string[] = [
  "Blaise Pascal a inventé la première machine à calculer à seulement 19 ans, pour aider son père.",
  "Pour Descartes, douter de tout était la première étape pour bâtir un savoir solide.",
  "Louis Pasteur a mis au point le vaccin contre la rage en 1885 — la microbiologie moderne lui doit beaucoup.",
  "Marie Curie est la seule personne primée d'un Nobel dans deux sciences différentes : physique puis chimie.",
  "Les frères Lumière ont projeté le tout premier film public à Paris en 1895.",
  "Montesquieu a théorisé la séparation des pouvoirs, socle de nos démocraties modernes.",
  "Gustave Eiffel a aussi conçu la structure interne de la Statue de la Liberté.",
  "Pour Montaigne, « la plus grande chose du monde, c'est de savoir être à soi ».",
  "Voltaire défendait la tolérance : « Je ne suis pas d'accord avec vous, mais je me battrai pour que vous puissiez le dire. »",
  "Ada Lovelace a écrit le premier algorithme destiné à une machine, dès 1843.",
  "Antoine Lavoisier a posé la loi de conservation de la matière : « Rien ne se perd, rien ne se crée, tout se transforme. »",
  "Victor Hugo écrivait debout, face à la mer, depuis son exil à Guernesey.",
  "Aristote distinguait déjà le savoir-faire (technè) de la sagesse pratique (phronèsis).",
  "Le système métrique, né de la Révolution française, équipe aujourd'hui presque toute la planète.",
];

export function WelcomeGreeting({ prenom }: { prenom: string }) {
  const [message, setMessage] = useState<string>(`Bonjour ${prenom} 👋`);
  const [savaisTu, setSavaisTu] = useState<string | null>(null);

  useEffect(() => {
    const now = new Date();
    const hour = now.getHours();
    const dayKey = now.toISOString().slice(0, 10);
    const storeKey = `leads_visits_${dayKey}`;

    let visits = 0;
    try {
      visits = Number(localStorage.getItem(storeKey) ?? "0");
      visits += 1;
      localStorage.setItem(storeKey, String(visits));
      // Purge des compteurs des jours précédents (pas d'accumulation).
      for (let i = localStorage.length - 1; i >= 0; i--) {
        const k = localStorage.key(i);
        if (k && k.startsWith("leads_visits_") && k !== storeKey) {
          localStorage.removeItem(k);
        }
      }
    } catch {
      // localStorage indisponible : on retombe sur le message par défaut.
      return;
    }

    const seed = visits + hour;

    // À partir du 3ᵉ passage de la journée : une pépite de culture générale.
    if (visits >= 3) {
      setSavaisTu(pick(SAVAIS_TU, seed));
    }

    // 1) Tard le soir / nuit : prioritaire, ça détend.
    if (hour >= 22 || hour < 6) {
      setMessage(
        pick(
          [
            `${hour}h, tu es sûr ${prenom} ? 🌙`,
            `Il est ${hour}h… la nuit porte conseil, ${prenom}.`,
            `Couche-toi pas trop tard, ${prenom} 🌙`,
            `${hour}h et toujours là ? Respect, ${prenom}.`,
          ],
          seed,
        ),
      );
      return;
    }

    // 2) Première connexion de la journée → bienvenue.
    if (visits <= 1) {
      setMessage(`Bienvenue sur Leads, ${prenom} 👋`);
      return;
    }

    // 3) On revient (beaucoup) : petits clins d'œil.
    if (visits >= 4) {
      setMessage(
        pick(
          [
            `Oublié quelque chose, ${prenom} ? 😄`,
            `Encore toi ? Haut les cœurs, on y retourne ! 💪`,
            `${visits}ᵉ passage aujourd'hui… l'assiduité paie 👏`,
            `Rebelote, ${prenom} — on remet ça !`,
          ],
          seed,
        ),
      );
      return;
    }

    // 4) Retour « normal » (2ᵉ–3ᵉ passage) : messages rotatifs.
    setMessage(
      pick(
        [
          `De retour, ${prenom} ? 👋`,
          `Rebonjour ${prenom} 👋`,
          `On reprend, ${prenom} ?`,
          `Te revoilà, ${prenom} !`,
        ],
        seed,
      ),
    );
  }, [prenom]);

  return (
    <>
      <h1 className="text-2xl font-bold">{message}</h1>
      {savaisTu && (
        <p className="mt-1 text-xs italic text-[var(--muted)]">
          💡 Le savais-tu ? {savaisTu}
        </p>
      )}
    </>
  );
}
