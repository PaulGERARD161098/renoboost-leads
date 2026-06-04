"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

// Définition / changement du mot de passe (compte connecté). Une fois défini,
// la connexion quotidienne se fait au mot de passe — fini le lien par email.
export function SetPasswordForm() {
  const router = useRouter();
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (pw.length < 8) {
      setError("Au moins 8 caractères.");
      return;
    }
    if (pw !== pw2) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.updateUser({ password: pw });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    setDone(true);
    setPw("");
    setPw2("");
    router.refresh();
  }

  if (done) {
    return (
      <div className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800">
        ✅ Mot de passe enregistré. Tu pourras désormais te connecter directement
        avec ton email et ce mot de passe.
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className="mb-1 block text-sm font-medium" htmlFor="pw">
          Nouveau mot de passe
        </label>
        <input
          id="pw"
          type="password"
          required
          autoComplete="new-password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          placeholder="••••••••"
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium" htmlFor="pw2">
          Confirme le mot de passe
        </label>
        <input
          id="pw2"
          type="password"
          required
          autoComplete="new-password"
          value={pw2}
          onChange={(e) => setPw2(e.target.value)}
          placeholder="••••••••"
          className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={loading}
        className="rounded-lg bg-[var(--brand)] px-5 py-2 text-sm font-semibold text-white transition hover:bg-[var(--brand-dark)] disabled:opacity-50"
      >
        {loading ? "Enregistrement…" : "Enregistrer le mot de passe"}
      </button>
    </form>
  );
}
