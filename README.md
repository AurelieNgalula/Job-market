# Job-market

Un projet Python pour récupérer les offres d'emploi via l'API France Travail et les exporter en JSON ou CSV.

## Vue d'ensemble

Ce projet scrape les offres d'emploi depuis l'API publique de [France Travail](https://www.francetravail.fr/). Les offres sont récupérées par fenêtres temporelles, paginées et sauvegardées en JSON. 


### Fonctionnalités principales
- **Récupération par fenêtres temporelles** : divise la période de recherche en petites fenêtres (ex: 12h) pour gérer les limites de pagination de l'API
- **Gestion de token OAuth2** : rafraîchissement automatique du token en cas d'expiration (401)
- **Gestion des erreurs réseau** : retry avec backoff exponentiel
- **Sauvegarde en JSON** : l'API retourne du JSON, sauvegardé directement dans `out/offres_emploi_{typeContrat}.json`

## Architecture

```
Job-market/
├── script/
│   ├── offers_fetcher.py    # Script principal : récupère les offres via API France Travail
│   ├── requete.py           # Script alternatif avec gestion de réauthentification
│   ├── utils.py             # Utilitaires : authentification OAuth2
│   ├── requirements.txt      # Dépendances Python
│   └── __pycache__/
├── out/                      # Dossier de sortie (créé automatiquement)
│   ├── offres_emploi_cdi.json
│   ├── offres_emploi_cdd.json
│   └── ...
├── .env                      # Variables d'environnement (CLIENT_ID, CLIENT_SECRET)
├── .venv/                    # Environnement virtuel Python
└── README.md                 # Ce fichier
```

## Prérequis

- Python 3.14.3+ (compilé avec OpenSSL 3.6.1+)
- Authentifiants France Travail (CLIENT_ID et CLIENT_SECRET)
- pip 26.0+ (gestionnaire de paquets Python)
- Homebrew (sur macOS)

### Vérifier la version de Python et OpenSSL

```bash
python3 --version
python3 -c "import ssl; print('OpenSSL:', ssl.OPENSSL_VERSION)"
```

**Versioning actuelle** :
- Python 3.14.3
- OpenSSL 3.6.1 (27 Jan 2026)

## Installation

### 1. Cloner le projet

```bash
cd /Users/yaoyao/Desktop
git clone <url_du_repo> Job-market
cd Job-market
```

### 2. Créer un environnement virtuel Python

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# ou sur Windows:
# .venv\Scripts\activate
```

### 3. Installer les dépendances

```bash
pip install --upgrade pip
pip install -r script/requirements.txt
```

### 4. Configurer les authentifiants

Créez un fichier `.env` à la racine du projet avec vos identifiants France Travail :

```env
CLIENT_ID=votre_client_id
CLIENT_SECRET=votre_client_secret
```

**Obtenir vos identifiants** :
1. Accédez à [France Travail API](https://www.francetravail.fr/partenaire/nos-api)
2. Inscrivez-vous ou connectez-vous
3. Créez une application et récupérez CLIENT_ID et CLIENT_SECRET

## Utilisation

### 1️⃣ Récupérer les offres depuis l'API (JSON)

**L'API France Travail retourne du JSON.** Ce script récupère les offres et les sauvegarde directement en JSON.

#### Utilisation simple :
```bash
cd script
python3 offers_fetcher.py
```

**Résultat** : `out/offres_emploi_cdi.json` (format JSON natif de l'API)

#### Options en ligne de commande :
```bash
python3 offers_fetcher.py --window-days 1 --batch-size 150 --dedupe --out out/offres_emploi_cdi.json
```

**Options disponibles** :
- `--window-days` : taille de la fenêtre temporelle en jours (défaut: 0.05 = ~1h à 2h)
- `--batch-size` : nombre d'offres par page (défaut: 150)
- `--dedupe` : activer la déduplication des offres par ID ou empreinte
- `--out` : chemin du fichier de sortie (défaut: `out/offres_emploi_cdi.json`)
- `--start` : date de début au format ISO ou YYYY-MM-DD (défaut: now - 90 jours)
- `--end` : date de fin au format ISO ou YYYY-MM-DD (défaut: now)

#### Exemple avec filtrage sur une période spécifique :
```bash
python3 offers_fetcher.py --start 2026-01-01 --end 2026-02-01 --out out/offres_jan_fev.json
```

## Scripts détails

### `script/offers_fetcher.py`

**Fonction principale** : `fetch_offers()` - récupère les offres depuis l'API France Travail

**Flux** :
1. Obtient un token OAuth2 via `get_access_token()` (utils.py)
2. Boucle sur des fenêtres temporelles (ex: 90 jours divisé en fenêtres de 12h par défaut)
3. Pour chaque fenêtre, pagine par lots de 150 offres
4. Gère les erreurs réseau avec retry
5. Sauvegarde toutes les offres en JSON

**Gestion des statuts HTTP** :
- **200** : succès, affiche le nombre d'offres récupérées
- **206** : contenu partiel (pagination)
- **204** : pas de contenu pour cette fenêtre
- **401, 400, etc.** : erreur, passe à la fenêtre suivante

**Déduplication** : Si `--dedupe` est activé, le script tente de dédupliquer les offres par :
- Identifiant d'offre (id, offreId, identifiant, reference)
- Empreinte JSON si pas d'ID

### `script/requete.py`

**Alternative à `offers_fetcher.py`** : script modulable avec gestion fine de réauthentification

**Différences principales** :
- Gère explicitement les erreurs 401 avec tentatives de rafraîchissement du token
- Plus facile à adapter pour des besoins personnalisés
- Variables de configuration directement dans le script (modifiables)

**Configuration** :
- `GLOBAL_MIN_CREATION_DT` : date minimale de création (par défaut: now - 30 jours)
- `GLOBAL_MAX_CREATION_DT` : date maximale de création (par défaut: now - 0.5 jours)
- `window_days` : taille des fenêtres temporelles (défaut: 0.05 = ~1h)
- `typeContrat` : type de contrat à récupérer ("CDI", "CDD", etc.)

### `script/utils.py`

**Fonction principale** : `get_access_token()`

Récupère un token d'accès OAuth2 depuis France Travail en utilisant le Client Credentials Flow.

**Détails** :
- Charge CLIENT_ID et CLIENT_SECRET depuis le fichier `.env`
- URL d'authentification : `https://entreprise.francetravail.fr/connexion/oauth2/access_token`
- Scopes requis : `o2dsoffre api_offresdemploiv2`
- Token valide environ 3600 secondes (~1 heure)

## Mettre à jour Python

Si vous voyez un warning `urllib3 v2 only supports OpenSSL 1.1.1+` ou si vous avez `LibreSSL` au lieu d'`OpenSSL`, mettez à jour Python.

### Sur macOS (recommandé avec Homebrew)

#### 1️⃣ Installer Homebrew (si pas encore installé)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Puis configurer le PATH dans votre shell :
```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

#### 2️⃣ Installer/Mettre à jour Python

```bash
brew install python
```

Cela installera Python 3.14.3+ avec OpenSSL 3.6.1+.

#### 3️⃣ Recréer l'environnement virtuel

```bash
cd /Users/yaoyao/Desktop/Job-market
rm -rf .venv
/opt/homebrew/bin/python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r script/requirements.txt
```

#### 4️⃣ Vérifier l'installation

```bash
source .venv/bin/activate
python3 --version
python3 -c "import ssl; print('OpenSSL:', ssl.OPENSSL_VERSION)"
```

**Résultat attendu** :
```
Python 3.14.3
OpenSSL: OpenSSL 3.6.1 27 Jan 2026
```

### Sur Linux

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.14 python3.14-venv python3.14-dev

# Fedora
sudo dnf install python3.14 python3.14-devel

# Puis recréer le venv comme sur macOS ci-dessus
```



## Contact / Support

Pour toute question ou problème, consultez la [documentation France Travail API](https://www.francetravail.fr/partenaire/nos-api).

---

**Dernière mise à jour** : 6 mars 2026

### 📦 Dépendances installées (mise à jour 2026-03-06)

| Package | Version |
|---------|---------|
| requests | 2.32.5 |
| python-dotenv | 1.2.2 |
| pandas | 3.0.1 |
| numpy | 2.4.2 |
| urllib3 | 2.6.3 |
| certifi | 2026.2.25 |
