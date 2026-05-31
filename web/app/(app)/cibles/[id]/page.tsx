import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { Verticale } from "@/lib/database.types";
import { VerticaleForm } from "@/components/verticale-form";

export const dynamic = "force-dynamic";

export default async function CibleEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();
  const { data } = await supabase
    .from("verticales")
    .select("*")
    .eq("id", id)
    .single();

  if (!data) notFound();
  const verticale = data as Verticale;

  return (
    <div>
      <Link href="/cibles" className="text-sm text-[var(--muted)] hover:underline">
        ← Retour aux cibles
      </Link>
      <h1 className="mt-3 mb-1 text-2xl font-bold">{verticale.nom}</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Modifier le profil de cette cible.
      </p>
      <VerticaleForm verticale={verticale} />
    </div>
  );
}
