// Enrichissement on-demand d'UN lead via Dropcontact (email + téléphone +
// LinkedIn). Synchrone : POST d'un batch d'1 lead puis polling borné (sous la
// limite de durée de la fonction Vercel). Best-effort : toute panne renvoie une
// erreur structurée { error, action, retry }, jamais une exception.
//
// Le run worker enrichit déjà au moment de la recherche ; cette route permet de
// (re)lancer l'enrichissement à la demande depuis la fiche prospect.

import type { SupabaseClient } from "@supabase/supabase-js";

const DROPCONTACT_BASE = "https://api.dropcontact.com";
const POLL_INITIAL_MS = 8_000;
const POLL_INTERVAL_MS = 6_000;
// Budget de polling : on reste sous le maxDuration (60 s) de la route.
const POLL_BUDGET_MS = 48_000;

export type EnrichResult = {
  contact_email: string | null;
  contact_tel: string | null;
  contact_linkedin: string | null;
  entreprise_linkedin: string | null;
};

export type EnrichOk = { result: EnrichResult; trouve: boolean };
export type EnrichErr = { error: string; action: string; retry: boolean };

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

// Découpe « Prénom Nom » en (first_name, last_name). Best-effort : le premier
// jeton est le prénom, le reste le nom. Dropcontact fonctionne aussi sans nom
// (company + website + siren), donc on tolère l'absence.
function splitNom(nom: string | null): { first?: string; last?: string } {
  const parts = (nom ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return {};
  if (parts.length === 1) return { last: parts[0] };
  return { first: parts[0], last: parts.slice(1).join(" ") };
}

// Extrait le meilleur email du champ Dropcontact (liste d'objets qualifiés).
function extraireEmail(item: Record<string, unknown>): string | null {
  const emails = item.email;
  if (!Array.isArray(emails) || emails.length === 0) return null;
  const correct = emails.find(
    (e) => e && typeof e === "object" && (e as Record<string, unknown>).qualification === "correct",
  );
  const cible = (correct ?? emails[0]) as Record<string, unknown> | undefined;
  return cible && typeof cible.email === "string" ? cible.email : null;
}

function strOuNull(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

export async function enrichContact(
  supabase: SupabaseClient,
  leadId: string,
): Promise<EnrichOk | EnrichErr> {
  const apiKey = process.env.DROPCONTACT_API_KEY;
  if (!apiKey) {
    return {
      error: "Enrichissement non activé (clé DROPCONTACT_API_KEY absente).",
      action: "Ajoute la clé Dropcontact dans la configuration, puis réessaie.",
      retry: false,
    };
  }

  const { data: lead } = await supabase
    .from("leads")
    .select("entreprise, siren, contact_nom, site_web")
    .eq("id", leadId)
    .maybeSingle();
  if (!lead) {
    return { error: "Lead introuvable.", action: "Recharge la page.", retry: false };
  }
  const ld = lead as {
    entreprise: string;
    siren: string | null;
    contact_nom: string | null;
    site_web: string | null;
  };

  const { first, last } = splitNom(ld.contact_nom);
  const payload: Record<string, unknown> = { company: ld.entreprise };
  if (first) payload.first_name = first;
  if (last) payload.last_name = last;
  if (ld.site_web) payload.website = ld.site_web;
  if (ld.siren) payload.siren = ld.siren;

  const headers = { "Content-Type": "application/json", "X-Access-Token": apiKey };

  let requestId: string | null = null;
  try {
    const res = await fetch(`${DROPCONTACT_BASE}/v1/enrich/all`, {
      method: "POST",
      headers,
      body: JSON.stringify({ data: [payload], siren: true, language: "fr" }),
    });
    if (!res.ok) {
      console.error("enrich-contact POST error", res.status, await res.text());
      return {
        error: "Service d'enrichissement indisponible.",
        action: "Réessaie dans un instant.",
        retry: true,
      };
    }
    const data = await res.json();
    requestId = typeof data?.request_id === "string" ? data.request_id : null;
  } catch (e) {
    console.error("enrich-contact POST exception", e);
    return { error: "Connexion à Dropcontact impossible.", action: "Réessaie.", retry: true };
  }
  if (!requestId) {
    return { error: "Réponse Dropcontact inattendue.", action: "Réessaie.", retry: true };
  }

  // Polling borné.
  await sleep(POLL_INITIAL_MS);
  let elapsed = POLL_INITIAL_MS;
  let item: Record<string, unknown> | null = null;
  while (elapsed <= POLL_BUDGET_MS) {
    try {
      const res = await fetch(`${DROPCONTACT_BASE}/v1/enrich/all/${requestId}`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data?.success === true && Array.isArray(data.data) && data.data.length > 0) {
          item = data.data[0] as Record<string, unknown>;
          break;
        }
      }
    } catch (e) {
      console.error("enrich-contact poll exception", e);
    }
    await sleep(POLL_INTERVAL_MS);
    elapsed += POLL_INTERVAL_MS;
  }

  if (item === null) {
    return {
      error: "Enrichissement plus long que prévu.",
      action: "Réessaie dans un instant (le résultat se met en cache côté Dropcontact).",
      retry: true,
    };
  }

  const result: EnrichResult = {
    contact_email: extraireEmail(item),
    contact_tel: strOuNull(item.phone),
    contact_linkedin: strOuNull(item.linkedin),
    entreprise_linkedin: strOuNull(item.company_linkedin),
  };

  // On ne met à jour QUE les champs trouvés (jamais écraser par null).
  const patch: Record<string, string> = {};
  for (const [k, v] of Object.entries(result)) {
    if (v) patch[k] = v;
  }
  const trouve = Object.keys(patch).length > 0;
  if (trouve) {
    const { error: upErr } = await supabase.from("leads").update(patch).eq("id", leadId);
    if (upErr) {
      console.error("enrich-contact update error", upErr);
      return { error: "Échec d'enregistrement des coordonnées.", action: "Réessaie.", retry: true };
    }
  }

  return { result, trouve };
}
