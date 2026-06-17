"use client";

import { useState } from "react";
import { COUT_DROPCONTACT_PAR_LEAD } from "@/lib/costs";

type Contact = {
  contact_nom: string | null;
  contact_email: string | null;
  contact_tel: string | null;
  contact_linkedin: string | null;
  entreprise_linkedin: string | null;
  site_web: string | null;
};

type Echec = { message: string; action: string; retry: boolean };

// Coût indicatif d'un clic « Enrichir » (1 lead Dropcontact), affiché à l'avance.
const COUT_ENRICH = COUT_DROPCONTACT_PAR_LEAD.toLocaleString("fr-FR", {
  style: "currency",
  currency: "EUR",
});

// Carte « Décideur » de la fiche prospect : coordonnées + liens LinkedIn, avec
// un bouton d'enrichissement on-demand (Dropcontact → email / tél / LinkedIn).
export function ContactCard({
  leadId,
  siren,
  initial,
}: {
  leadId: string;
  siren?: string | null;
  initial: Contact;
}) {
  const [contact, setContact] = useState<Contact>(initial);
  const [loading, setLoading] = useState(false);
  const [echec, setEchec] = useState<Echec | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function enrichir() {
    setLoading(true);
    setEchec(null);
    setInfo(null);
    try {
      const res = await fetch("/api/lead/enrich-contact", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ leadId }),
      });
      const data = await res.json();
      if (data.error) {
        setEchec({
          message: data.error,
          action: data.action ?? "Réessayer.",
          retry: data.retry ?? true,
        });
      } else {
        const r = data.result as Partial<Contact>;
        setContact((c) => ({
          ...c,
          contact_email: r.contact_email ?? c.contact_email,
          contact_tel: r.contact_tel ?? c.contact_tel,
          contact_linkedin: r.contact_linkedin ?? c.contact_linkedin,
          entreprise_linkedin: r.entreprise_linkedin ?? c.entreprise_linkedin,
        }));
        setInfo(
          data.trouve
            ? "Coordonnées mises à jour."
            : "Aucune nouvelle coordonnée trouvée pour ce profil.",
        );
      }
    } catch {
      setEchec({
        message: "Connexion au serveur impossible.",
        action: "Vérifier la connexion, puis réessayer.",
        retry: true,
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-white p-5">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
          Décideur
        </h2>
        <button
          onClick={enrichir}
          disabled={loading}
          title="Interroge Dropcontact pour retrouver l'email, le téléphone et le LinkedIn du décideur."
          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-slate-50 disabled:opacity-40"
        >
          {loading ? "Recherche en cours…" : `Trouver plus d'infos · ${COUT_ENRICH}`}
        </button>
      </div>
      <p className="mb-3 text-xs text-[var(--muted)]">
        Cherche email, téléphone & LinkedIn du décideur via Dropcontact ({COUT_ENRICH} par
        recherche). {siren ? "Sinon, ouvre la fiche Pappers ci-dessous." : ""}
      </p>

      <dl className="space-y-2 text-sm">
        <Field label="Nom" value={contact.contact_nom} />
        <Field label="Email" value={contact.contact_email} />
        <Field label="Téléphone" value={contact.contact_tel} />
        <Field
          label="LinkedIn"
          value={contact.contact_linkedin ? "Profil du décideur" : null}
          href={contact.contact_linkedin ?? undefined}
        />
        <Field
          label="LinkedIn entreprise"
          value={contact.entreprise_linkedin ? "Page entreprise" : null}
          href={contact.entreprise_linkedin ?? undefined}
        />
        <Field label="Site" value={contact.site_web} href={contact.site_web ?? undefined} />
      </dl>

      {siren && (
        <a
          href={`https://www.pappers.fr/entreprise/${siren}`}
          target="_blank"
          rel="noreferrer"
          className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-[var(--brand)] hover:underline"
        >
          Voir les dirigeants sur Pappers ↗
        </a>
      )}

      {info && <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-[var(--muted)]">{info}</p>}

      {echec && (
        <div className="mt-3 rounded-lg bg-amber-50 p-3 text-xs">
          <p className="font-medium text-amber-900">{echec.message}</p>
          <p className="mt-1 text-amber-700">→ {echec.action}</p>
          {echec.retry && (
            <button
              onClick={enrichir}
              className="mt-2 rounded-md border border-amber-300 bg-white px-2.5 py-1 font-medium text-amber-900 hover:bg-amber-100"
            >
              Réessayer
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  value,
  href,
}: {
  label: string;
  value: string | null;
  href?: string;
}) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-[var(--muted)]">{label}</dt>
      <dd className="text-right font-medium">
        {value ? (
          href ? (
            <a
              href={href.startsWith("http") ? href : `https://${href}`}
              target="_blank"
              rel="noreferrer"
              className="text-[var(--brand)] hover:underline"
            >
              {value}
            </a>
          ) : (
            value
          )
        ) : (
          "—"
        )}
      </dd>
    </div>
  );
}
