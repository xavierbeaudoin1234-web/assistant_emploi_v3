# Assistant Emploi — Drummondville (prototype v3)

## Ce que fait cette version
- Interface web légère et gratuite à héberger sur GitHub Pages.
- Recherche par catégories et raccourcis vers Indeed, Jobillico et les pages carrière.
- File locale d'offres, score de correspondance et brouillons de candidature.
- Collecte quotidienne facultative à partir de flux RSS Google Alerts configurés par l'utilisateur.
- Aucune candidature n'est envoyée automatiquement : chaque offre doit être vérifiée et approuvée par la personne.

## Important
Un fichier HTML local ne tourne pas quand il est fermé. Pour que les nouvelles offres apparaissent à ton retour, il faut héberger ce projet et activer GitHub Actions. Le collecteur n'explore pas directement Indeed ou Jobillico; il lit les flux RSS des alertes de recherche. Les résultats Google Alerts sont des pistes, pas une garantie d'emploi encore ouvert. Le salaire et la distance doivent être vérifiés sur l'annonce originale.

Indeed indique que les outils automatisés tiers ne doivent pas être utilisés pour postuler : https://support.indeed.com/hc/en-ca/articles/360028540531-Indeed-Job-Seeker-Guidelines
Jobillico interdit les robots qui parcourent son site pour collecter et télécharger du contenu : https://www.jobillico.com/termes-conditions

## Installation gratuite (ordinateur)
1. Crée un compte GitHub si nécessaire, puis crée un dépôt public nommé `assistant-emploi`.
2. Téléverse tous les fichiers de ce dossier dans le dépôt, en gardant les dossiers `.github/workflows` et `scripts`.
3. Dans GitHub, ouvre **Settings → Secrets and variables → Actions → New repository secret**.
4. Nom du secret : `JOB_ALERT_FEEDS`.
5. Valeur du secret : les URL de flux RSS Google Alerts, une par ligne.
6. Dans **Actions**, active les workflows et lance **Actualiser les offres d'emploi → Run workflow** pour tester.
7. Dans **Settings → Pages**, publie depuis la branche principale (`main`) et le dossier `/ (root)`.
8. Ouvre l'adresse GitHub Pages donnée par GitHub. Chaque jour vers 7 h (heure de l'Est pendant l'heure avancée; l'heure peut varier en hiver), GitHub Actions essaiera d'actualiser `jobs.json`.

## Créer les alertes Google
Ouvre https://www.google.com/alerts et crée plusieurs alertes. Dans **Afficher les options**, choisis la langue français ou anglais, la région Canada et la livraison **Flux RSS** si cette option est disponible. Exemples de requêtes à tester :
- `Drummondville (commis entrepôt OR inventaire OR réception) emploi`
- `Drummondville (commis de plancher OR conseiller vente OR commerce) emploi`
- `Drummondville (informatique OR électronique OR support technique) emploi`
- `Drummondville (service à la clientèle OR accueil OR conseiller) emploi`

Copie chaque URL RSS et colle-les dans le secret `JOB_ALERT_FEEDS`, une URL par ligne. Google Alerts peut manquer des offres; garde aussi les alertes natives des plateformes si elles sont disponibles.

## Limites de la collecte
- Le workflow ne contourne pas de connexion, CAPTCHA ou protection d'un site.
- Le filtre de localisation utilise des mentions de villes/secteurs; il ne calcule pas précisément 20 km. Vérifie la distance réelle.
- Le salaire peut être absent ou mal interprété; une offre avec salaire inconnu n'est pas confirmée comme respectant 18 $/h.
- Le nom de l'employeur peut ne pas être disponible dans le résultat RSS; vérifie l'annonce originale.
- Le brouillon est une base de départ, à personnaliser selon les exigences exactes.
- Les données locales du navigateur ne sont pas synchronisées entre appareils. La liste de nouvelles offres publiée dans `jobs.json` est commune, mais tes statuts et brouillons restent locaux au navigateur.

## Structure
- `index.html`: application web.
- `jobs.json`: offres candidates les plus récentes, générées par le workflow.
- `scripts/update_jobs.py`: lecteur RSS, classification et déduplication.
- `.github/workflows/daily-search.yml`: exécution quotidienne planifiée.
