-- Hardening sécurité — réponse aux advisors Supabase (audit 2026-07-02, constat S1).
-- ⚠️ DÉPOSÉE, NON APPLIQUÉE EN PROD sans validation Paul (contrainte cadrage : touche RLS/données).
-- Deux parties :
--   A. Non-cassant, prêt à appliquer  : search_path des fonctions d'agrégation bornes.
--   B. Scoping RLS (le vrai S1)        : COMMENTÉ — nécessite une décision de modèle de tenance.

-- ============================================================================
-- A. Function Search Path Mutable (advisor 0011) — non cassant.
--    Les 2 fonctions qualifient déjà public.bornes_recharge → search_path='' est sûr.
-- ============================================================================
alter function public.bornes_stats_departements() set search_path = '';
alter function public.bornes_stats_operateurs() set search_path = '';

-- ============================================================================
-- B. RLS Policy Always True (advisor 0024) — LE constat S1 (cross-client exposé).
--    Toutes les policies `*_all_auth` sont `FOR ALL USING (true) WITH CHECK (true)` :
--    tout compte authentifié lit/écrit TOUTES les lignes, tous clients confondus.
--    CADRAGE.md : « commercial lit/écrit les leads de SON périmètre ».
--
--    ⏸ DÉCISION REQUISE (Paul) avant d'activer ce bloc :
--       Modèle de tenance = par-commercial (created_by) OU équipe-partagée (statu quo) ?
--       Si équipe-partagée assumée → garder USING(true) mais restreindre au moins
--       DELETE aux admins. Si par-commercial → activer le scoping ci-dessous table par table.
--
--    Gabarit (exemple pour `leads` ; à répliquer sur les tables à created_by :
--    verticales, runs, campaigns, zones_cibles, references_chantiers, retours…) :
--
--    drop policy if exists leads_all_auth on public.leads;
--    create policy leads_select_scope on public.leads for select to authenticated
--      using (created_by = auth.uid() or public.is_admin());
--    create policy leads_write_scope on public.leads for all to authenticated
--      using (created_by = auth.uid() or public.is_admin())
--      with check (created_by = auth.uid() or public.is_admin());
--
--    ⚠️ Les tables SANS colonne created_by (lead_contacts, lead_events, lead_messages,
--       lead_reply_suggestions, phone_numbers, voicemails, veille_signaux,
--       suggestion_clicks, agent_config, agent_journal, app_context) doivent être
--       scopées via jointure sur leur lead/run parent — à concevoir avec Paul.

-- ============================================================================
-- C. is_admin() SECURITY DEFINER exécutable par authenticated (advisor 0029).
--    ⏸ PAR DESIGN : les policies RLS (rôle authenticated) appellent is_admin().
--    Le migration 0001 révoque déjà EXECUTE de anon/public. Ne PAS révoquer de
--    authenticated sans casser les policies. Aucun changement ici — documenté.
-- ============================================================================

-- ============================================================================
-- D. Leaked Password Protection (advisor auth) — NON gérable par migration.
--    À activer dans le dashboard Supabase : Auth > Policies > "Leaked password
--    protection" (vérification HaveIBeenPwned). Action manuelle Paul.
-- ============================================================================
