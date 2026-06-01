"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/confirm`,
      },
    });
    setLoading(false);
    if (error) setError(error.message);
    else setSent(true);
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-2xl border border-[var(--border)] bg-white p-8 shadow-sm">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-[var(--brand)]">ReSign CRM</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Connexion à l&apos;espace commercial
          </p>
        </div>

        {sent ? (
          <div className="rounded-lg bg-emerald-50 p-4 text-center text-sm text-emerald-800">
            Lien de connexion envoyé à <strong>{email}</strong>.<br />
            Ouvre ton email pour te connecter.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="email">
                Email professionnel
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="prenom@resign.fr"
                className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-[var(--brand)] py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--brand-dark)] disabled:opacity-50"
            >
              {loading ? "Envoi…" : "Recevoir le lien de connexion"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
