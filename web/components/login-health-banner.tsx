"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import type { SystemSeverite } from "@/lib/database.types";

/**
 * Bandeau d'avertissement sur la page de connexion (non authentifiée) en cas de
 * problème majeur : hors-ligne, base indisponible, ou incident déclaré. Lit
 * system_status via la clé anon (RLS : lecture publique).
 */
export function LoginHealthBanner() {
  const [severite, setSeverite] = useState<SystemSeverite>("ok");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      if (!navigator.onLine) {
        if (!cancelled) {
          setSeverite("critical");
          setMessage("Hors-ligne — vérifie ta connexion internet.");
        }
        return;
      }
      try {
        const supabase = createClient();
        const { data, error } = await supabase
          .from("system_status")
          .select("severite, message")
          .eq("id", "main")
          .maybeSingle();
        if (cancelled) return;
        if (error) {
          setSeverite("critical");
          setMessage("Service momentanément indisponible (connexion à la base).");
          return;
        }
        const s = (data?.severite as SystemSeverite | undefined) ?? "ok";
        setSeverite(s);
        setMessage(s !== "ok" ? (data?.message ?? "Incident en cours.") : null);
      } catch {
        if (!cancelled) {
          setSeverite("critical");
          setMessage("Service momentanément indisponible.");
        }
      }
    }
    void check();
    window.addEventListener("online", check);
    window.addEventListener("offline", check);
    return () => {
      cancelled = true;
      window.removeEventListener("online", check);
      window.removeEventListener("offline", check);
    };
  }, []);

  if (severite === "ok") return null;
  const critical = severite === "critical";
  return (
    <div
      role="alert"
      className={`mb-4 rounded-lg border px-3 py-2 text-sm ${
        critical
          ? "border-red-200 bg-red-50 text-red-800"
          : "border-amber-200 bg-amber-50 text-amber-800"
      }`}
    >
      ⚠️ {message}
    </div>
  );
}
