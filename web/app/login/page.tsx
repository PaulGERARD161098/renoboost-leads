"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

type Mode = "password" | "reset";

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function loginPassword(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      setLoading(false);
      setError("Email ou mot de passe incorrect.");
      return;
    }
    // Rechargement complet : le cookie de session est transmis au middleware.
    window.location.assign("/inbox");
  }

  async function sendResetLink(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        shouldCreateUser: false,
        emailRedirectTo: `${window.location.origin}/auth/confirm?next=/compte`,
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
          <h1 className="text-2xl font-bold text-[var(--brand)]">Leads</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Connexion à l&apos;espace commercial
          </p>
        </div>

        {mode === "password" ? (
          <form onSubmit={loginPassword} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="prenom@renoboostia.fr"
                className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="password">
                Mot de passe
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-[var(--brand)] py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--brand-dark)] disabled:opacity-50"
            >
              {loading ? "Connexion…" : "Se connecter"}
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("reset");
                setError(null);
                setSent(false);
              }}
              className="block w-full text-center text-xs text-[var(--muted)] underline hover:text-[var(--brand)]"
            >
              Première connexion ou mot de passe oublié ?
            </button>
          </form>
        ) : sent ? (
          <div className="space-y-4">
            <div className="rounded-lg bg-emerald-50 p-4 text-center text-sm text-emerald-800">
              Lien envoyé à <strong>{email}</strong>.<br />
              Ouvre-le pour te connecter, puis choisis ton mot de passe sur la
              page <strong>Compte</strong>.
            </div>
            <button
              type="button"
              onClick={() => {
                setMode("password");
                setSent(false);
              }}
              className="block w-full text-center text-xs text-[var(--muted)] underline hover:text-[var(--brand)]"
            >
              ← Retour à la connexion
            </button>
          </div>
        ) : (
          <form onSubmit={sendResetLink} className="space-y-4">
            <p className="text-sm text-[var(--muted)]">
              Reçois un lien à usage unique pour te connecter, puis définis ton
              mot de passe une bonne fois.
            </p>
            <div>
              <label className="mb-1 block text-sm font-medium" htmlFor="reset-email">
                Email
              </label>
              <input
                id="reset-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="prenom@renoboostia.fr"
                className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--brand)]"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-[var(--brand)] py-2.5 text-sm font-semibold text-white transition hover:bg-[var(--brand-dark)] disabled:opacity-50"
            >
              {loading ? "Envoi…" : "Recevoir le lien"}
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("password");
                setError(null);
              }}
              className="block w-full text-center text-xs text-[var(--muted)] underline hover:text-[var(--brand)]"
            >
              ← Retour à la connexion
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
