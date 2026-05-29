"""Module « parkings loi APER ».

Ingère un inventaire de parcs de stationnement extérieurs (export OSM / IGN /
fichier client), filtre ceux soumis à l'obligation de solarisation (art. 40 de
la loi APER : parkings > 1 500 m²), les enrichit via le pipeline RénoBoost
existant (L2 SIREN + L3 contacts + L4 scoring Claude), et produit une liste de
prospects *contraints et datés* pour l'installation d'ombrières PV + bornes VE.

Indépendant du module `veille_immatriculations` : les deux peuvent tourner
séparément. Voir PARKINGS_APER.md.
"""
