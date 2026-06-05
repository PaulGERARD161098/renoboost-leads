-- Incrément B — tunnel jusqu'au RDV.
-- Nouvel état de fin de funnel : le prospect a pris rendez-vous (capté via le
-- webhook Calendly ou marqué à la main). Sort le lead des relances et permet de
-- mesurer le taux de conversion (rdv_pris / envoyés).
alter type public.lead_status add value if not exists 'rdv_pris';
