import { createClient } from "@supabase/supabase-js";

/**
 * Client Supabase "service role" — bypasse la RLS. À n'utiliser QUE côté
 * serveur, sans session utilisateur (ex. webhooks entrants). Retourne null
 * si la clé service role n'est pas configurée.
 */
export function createAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
