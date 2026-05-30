"""Module d'enrichissement firmographique via l'API Societeinfo.

Societeinfo s'appuie sur les registres officiels FR (INSEE / BODACC / INPI) et
offre un meilleur taux de match SIREN + firmographie que le L2 gratuit
(data.gouv). Ce module est **indépendant** : il s'utilise soit en alternative,
soit en complément ciblé du L2, via la commande CLI `enrich-societeinfo` sur un
CSV de leads existant. Voir SOCIETEINFO.md.

Tant qu'aucune clé API n'est configurée (ou en `--dry-run`), le client renvoie
des données simulées : tout le câblage est testable sans abonnement actif.
"""
