# OPERATIONS — Procédures de sécurité et de récupération

Ce document décrit les **standards opérationnels** à respecter avant, pendant
et après chaque run important du projet RénoBoost Leads.

---

## 🎯 Principes fondateurs

1. **Aucune action critique sans pré-check.** Mieux vaut perdre 2 minutes en
   vérifications qu'une heure en récupération de données.
2. **Toujours créer une redondance avant action longue.** Backup, snapshot, ou
   commit Git avant tout run > 5 minutes.
3. **Précision > volume.** L'outil ne doit jamais générer de données fausses
   ou inventées. Les champs vides sont préférables aux suppositions.
4. **Promesse = livraison.** Le rendu doit toujours pouvoir être défendu selon
   les conditions initiales : si l'outil promet A, on obtient A.

---

## 🛡️ Pré-checks AVANT un run

### Pré-check #1 — OneDrive / Cloud sync (CRITIQUE)

⚠️ Si le projet est dans un dossier synchronisé (OneDrive, Google Drive, Dropbox),
la sync peut corrompre les CSV en cours d'écriture (race condition observée
en production le 1er mai 2026).

**Action obligatoire avant tout run > 5 minutes** :

1. Localiser l'icône cloud (barre des tâches Windows, en bas à droite)
2. Clic droit → ⚙️ ou "Aide et paramètres"
3. "Pause synchronisation" → "2 heures"
4. Vérifier que l'icône change visuellement

**Mieux (long terme)** : déplacer le projet vers un dossier hors cloud
(ex: `C:\dev\renoboost-leads`).

### Pré-check #2 — Espace disque

```powershell
Get-PSDrive C | Select-Object Used, Free
```

→ Vérifier au moins 500 Mo libres.

### Pré-check #3 — venv actif

Vérifier `(.venv)` au début du prompt PowerShell. Sinon :

```powershell
.\.venv\Scripts\Activate.ps1
```

### Pré-check #4 — Connexions APIs

```powershell
python -m renoboost_leads.cli check-connections
```

→ Toutes les APIs nécessaires au run doivent être ✓.

### Pré-check #5 — Backup avant action longue

Pour tout run > 5 minutes, créer un backup manuel avant :

```powershell
$tag = Get-Date -Format 'yyyy-MM-dd_HHmm'
robocopy "data\output" "$HOME\Documents\renoboost-backups\$tag" /E /COPY:DAT
```

Ou backup d'une session spécifique :

```powershell
$session = "data\output\<NOM_SESSION>"
$tag = Get-Date -Format 'yyyy-MM-dd_HHmm'
Copy-Item -Path $session -Destination "$HOME\Desktop\backup-$tag" -Recurse -Force
```

### Pré-check #6 — Estimation budgétaire (si étage 1 ou 4)

```powershell
python -m renoboost_leads.cli estimate --config config\<fichier>.yaml
```

→ Vérifier que le coût estimé est sous le plafond souhaité.

### Pré-check #7 — Étage 4 (si activé)

Si `--stages 4` est demandé :

1. `ANTHROPIC_API_KEY` présente dans `.env` (`check-connections` doit l'afficher ✓).
2. Modèle choisi dans `config/<client>.yaml` :
   - `claude-haiku-4-5` (~0.005 €/lead) → run de masse, validation rapide
   - `claude-sonnet-4-6` (~0.02 €/lead) → qualité supérieure, runs ciblés
3. Le **cache L4** (`cache_l4.sqlite`) est indépendant du cache L1/L2/L3.
   - Une seconde exécution avec **mêmes paramètres** (modèle, contexte, `inclure_pitch`)
     est gratuite (cache hit).
   - Tout changement de l'un de ces paramètres invalide automatiquement le cache.
4. `seuil_top_lead` : 70 par défaut. À ajuster par client (50-80 selon strictness).

---

## 🔄 Pendant un run

- ✅ **Ne pas fermer PowerShell.** Tu peux ouvrir une 2ème fenêtre pour autres tâches.
- ❌ **Ne pas lancer d'autre commande** dans le terminal du run.
- 📊 **Surveiller les logs.** Warnings répétés → prendre une capture pour debug ultérieur.
- 🛑 **Pour interrompre proprement** : `Ctrl + C` (les sauvegardes incrémentales
  garantissent qu'aucune donnée n'est perdue).

---

## ✅ Post-checks APRÈS un run

### Post-check #1 — Vérification CSV finaux

```powershell
$session = (Get-ChildItem data\output\ -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
dir $session
```

→ Tu dois voir les CSV attendus (étage1, étage2, étage3, étage4 selon le run) à la
racine du dossier, **PAS uniquement dans `backups/`**.

Pour L4 spécifiquement, vérifier dans `etage4_prospection.csv` :
- Distribution des `score_interet` : pas tous à la même valeur (modèle figé = erreur).
- Colonne `scoring_erreur` : devrait être vide ou très marginale (< 5%).
- Au moins ~10-30% de leads marqués `top_lead=VRAI` (ajuste `seuil_top_lead` sinon).

### Post-check #2 — Si CSV manquants à la racine mais présents dans `backups/`

Bug OneDrive probable. Restauration depuis backups :

```powershell
$session = "<chemin du dossier>"
Copy-Item "$session\backups\etage1_decouverte_*.csv" "$session\etage1_decouverte.csv" -Force
Copy-Item "$session\backups\etage2_entreprises_*.csv" "$session\etage2_entreprises.csv" -Force
Copy-Item "$session\backups\etage3_contacts_*.csv" "$session\etage3_contacts.csv" -Force
```

### Post-check #3 — Validation qualité visuelle

Ouvrir le CSV final dans Google Sheets :

```powershell
Start-Process "https://sheets.google.com/create" ; explorer $session
```

Vérifier visuellement :
- 5 lignes au hasard pour chaque catégorie (`match_incertain=VRAI`, `flag_chaine=VRAI`, lignes "or")
- Les emails L3 ont l'air légitimes
- Aucune valeur aberrante (téléphones bidons, dates futures, etc.)

### Post-check #4 — Backup post-run

```powershell
$tag = Get-Date -Format 'yyyy-MM-dd_HHmm'
robocopy "data\output" "$HOME\Documents\renoboost-backups\$tag" /E /COPY:DAT
```

### Post-check #5 — Commit Git si livrable

Si le run produit un livrable client, marquer la version :

```powershell
git tag -a "v0.X.0-runYYYYMMDD" -m "Run client X — N leads"
git push origin --tags
```

---

## 🚨 Procédure de récupération en cas de crash

### Scénario 1 — Le run a crashé en cours

1. Ne pas paniquer : la sauvegarde incrémentale a tourné toutes les 20 leads.
2. Vérifier le dernier CSV dans `data/output/<dernier_run>/` ou `<dernier_run>/backups/`.
3. Reprendre avec :

```powershell
python -m renoboost_leads.cli resume --session-id <NOM_DOSSIER> `
  --stages <ETAGE_INTERROMPU> --config <fichier.yaml>
```

### Scénario 2 — Les CSV "courants" ont disparu

Causes probables : OneDrive a corrompu, antivirus en quarantaine, suppression accidentelle.

**Ordre de recherche** :

1. `data/output/<dossier>/backups/` (toujours horodatés — créés automatiquement)
2. `$HOME\Documents\renoboost-backups\<date>` (si pré-check #5 fait)
3. `$HOME\Desktop\backup-*` (si backup manuel fait)
4. Corbeille Windows
5. En dernier recours : le `cache.sqlite` contient toutes les données API → relance L2 sur cache (gratuit, ~1 min). L3 peut aussi se relancer (les pages sont en cache).

### Scénario 3 — Cache SQLite corrompu

Symptôme : erreur `database disk image is malformed`.

1. Supprimer le fichier `cache.sqlite` du dossier de session.
2. Le run repaiera les API (vérifier le budget !).

### Scénario 4 — Crash conversation Claude pendant un long run

Le run continue indépendamment sur le PC. Une fois fini :

1. Vérifier `dir <session>` pour voir tous les fichiers générés.
2. Lire `stats_run.json` pour les stats finales.
3. Reprendre une nouvelle conversation Claude avec le prompt de reprise standard.

---

## 📊 Checklist de mise en production (livraison client)

Avant de transmettre un CSV à un client :

- [ ] Tous les pré-checks passés
- [ ] Tous les post-checks passés
- [ ] Validation visuelle 10 lignes random dans Google Sheets
- [ ] Vérification que les flags `match_incertain` et `flag_chaine` sont visibles dans le CSV
- [ ] Si emails (L3) : vérification batch via NeverBounce/ZeroBounce avant envoi
- [ ] `registre_rgpd.md` à jour
- [ ] Backup post-run effectué
- [ ] Commit Git + tag de version

---

## 🤝 Engagement qualité au client

Toute donnée livrée respecte les principes suivants :

- Aucune information inventée ou supposée
- Champs vides plutôt que valeurs incertaines
- Flags de confiance visibles dans le CSV (`match_incertain`, `flag_chaine`,
  `source_globale`)
- Sources documentées dans `registre_rgpd.md`
- Conformité RGPD article 6.1.f (intérêt légitime B2B)
- Durée de conservation recommandée : 3 ans après dernier contact

---

## 📝 Évolutions futures de ce document

- Coder pré-checks dans la CLI (`run --pre-checks`) pour automatisation
- Auto-détection projet dans dossier cloud → warning au lancement
- Atomic write sur écriture CSV pour blinder vs OneDrive
- Self-test régulier de la cohérence des CSV
