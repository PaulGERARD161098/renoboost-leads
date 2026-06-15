-- Boucle d'apprentissage — A/B « appris vs terrain ».
-- On persiste la SOURCE de l'angle retenu à la génération du brouillon :
--   • 'terrain' : l'angle vient de l'analyse du site (vision satellite) ;
--   • 'appris'  : le terrain était muet → angle qui convertit le mieux sur la cible.
-- Sans cette colonne on ne pouvait que SUPPOSER que le terrain prime ; on peut
-- désormais le MESURER (taux de réponse par source). Nullable, rétro-compatible :
-- les anciens leads restent à null (hors A/B), le code dégrade proprement.
alter table leads
  add column if not exists mail_angle_source text
    check (mail_angle_source in ('terrain', 'appris'));

comment on column leads.mail_angle_source is
  'Source de l''angle du mail : terrain (analyse site) ou appris (reco cible). Pour l''A/B.';
