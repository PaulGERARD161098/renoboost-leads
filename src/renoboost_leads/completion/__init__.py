"""Étage de complétion (3.7) — enrichit l'existant ET repêche les trous.

Étage générique branchable sur toute génération de leads. Pour chaque lead, il :
1. **enrichit** : ajoute la firmographie/contacts manquants (NAF, effectif, CA,
   dirigeant, LinkedIn…) ;
2. **repêche** : va chercher via une source externe ce que le pipeline classique
   (L1→L3.5) n'a pas trouvé (SIREN, dirigeant, email).

Remplissage *fill-if-empty* : on ne réécrit jamais une valeur déjà trouvée par le
pipeline ; on ne comble que les trous, et on trace la provenance
(`completion_champs_remplis` + `completion_provider`). Flag-not-drop : aucun lead
n'est supprimé.

Provider swappable (`ProviderCompletion`). 1er provider = Societeinfo.
"""

from .etage import EtageCompletion
from .livrable import (
    COLONNES_COMPLETION,
    export_completion_csv,
    generer_annexe_completion,
)
from .models import LeadComplete
from .provider import (
    ProviderCompletion,
    ResultatCompletion,
    SocieteinfoProvider,
    construire_provider_societeinfo,
)

__all__ = [
    "EtageCompletion",
    "LeadComplete",
    "ProviderCompletion",
    "ResultatCompletion",
    "SocieteinfoProvider",
    "construire_provider_societeinfo",
    "COLONNES_COMPLETION",
    "export_completion_csv",
    "generer_annexe_completion",
]
