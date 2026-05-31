import Link from "next/link";
import { VerticaleForm } from "@/components/verticale-form";

export default function NouvelleCiblePage() {
  return (
    <div>
      <Link href="/cibles" className="text-sm text-[var(--muted)] hover:underline">
        ← Retour aux cibles
      </Link>
      <h1 className="mt-3 mb-1 text-2xl font-bold">Nouvelle cible</h1>
      <p className="mb-5 text-sm text-[var(--muted)]">
        Décris le profil d&apos;entreprises à prospecter.
      </p>
      <VerticaleForm />
    </div>
  );
}
