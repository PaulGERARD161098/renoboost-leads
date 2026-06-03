"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Rafraîchit le rendu serveur à intervalle régulier tant que `enabled` est vrai.
 * Sert à faire vivre la progression d'une recherche en cours sans Realtime :
 * la page est `force-dynamic`, donc `router.refresh()` recharge les données.
 */
export function AutoRefresh({
  enabled,
  intervalMs = 4000,
}: {
  enabled: boolean;
  intervalMs?: number;
}) {
  const router = useRouter();
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(id);
  }, [enabled, intervalMs, router]);
  return null;
}
