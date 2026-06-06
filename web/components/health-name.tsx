"use client";

import { useEffect, useState } from "react";
import type { SystemSeverite } from "@/lib/database.types";

const COLOR: Record<SystemSeverite, string> = {
  ok: "text-[var(--brand)]",
  warning: "text-amber-600",
  critical: "text-red-600",
};

/**
 * Le nom du CRM coloré en voyant de santé : 🟢 vert (OK), 🟠 ambre (dégradé),
 * 🔴 rouge (problème majeur). La sévérité serveur (Supabase/incident/worker) est
 * fusionnée avec l'état réseau du navigateur : hors-ligne → rouge immédiat.
 */
export function HealthName({
  name,
  severite,
  className = "",
}: {
  name: string;
  severite: SystemSeverite;
  className?: string;
}) {
  // On part « en ligne » pour aligner SSR et premier rendu client (pas de
  // navigator côté serveur), puis on synchronise dans l'effet.
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const sync = () => setOnline(navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  const effective: SystemSeverite = online ? severite : "critical";
  const tip =
    effective === "critical"
      ? online
        ? "Problème majeur en cours."
        : "Hors-ligne — vérifie ta connexion internet."
      : effective === "warning"
        ? "Service dégradé."
        : "Tout fonctionne normalement.";

  return (
    <span className={`${COLOR[effective]} ${className}`} title={tip}>
      {name}
    </span>
  );
}
