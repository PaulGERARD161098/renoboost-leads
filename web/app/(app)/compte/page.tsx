import { createClient } from "@/lib/supabase/server";
import { SetPasswordForm } from "@/components/set-password-form";

export const dynamic = "force-dynamic";

export default async function ComptePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const { data: profile } = await supabase
    .from("profiles")
    .select("nom")
    .eq("id", user?.id ?? "")
    .maybeSingle();

  return (
    <div className="max-w-lg">
      <h1 className="mb-1 text-2xl font-bold">Mon compte</h1>
      <p className="mb-6 text-sm text-[var(--muted)]">
        Définis ton mot de passe pour te connecter sans lien email.
      </p>

      <div className="mb-6 rounded-xl border border-[var(--border)] bg-white p-4 text-sm">
        <div className="flex justify-between py-1">
          <span className="text-[var(--muted)]">Nom</span>
          <span className="font-medium">{profile?.nom ?? "—"}</span>
        </div>
        <div className="flex justify-between py-1">
          <span className="text-[var(--muted)]">Email</span>
          <span className="font-medium">{user?.email ?? "—"}</span>
        </div>
      </div>

      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
        🔒 Mot de passe
      </h2>
      <div className="rounded-xl border border-[var(--border)] bg-white p-5">
        <SetPasswordForm />
      </div>
    </div>
  );
}
