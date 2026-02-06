# HelloAsso Sync - Structure du Projet

## 📁 Organisation des Fichiers

```
api_automation_toolbox/
│
├── config/                           # Configuration
│   ├── hello-asso-automation-conf.json          # Config principale (gitignored)
│   ├── hello-asso-automation-conf-test.json     # Config tests (gitignored)
│   └── hello-asso-automation-conf.json.example  # Template
│
├── docs/                             # Documentation
│   ├── setup/                        # Guides de configuration
│   │   ├── AIRTABLE_PERMISSIONS_FIX.md
│   │   ├── AIRTABLE_SETUP.md
│   │   ├── FIX_AIRTABLE_TESTS.md
│   │   └── FUNCTIONAL_TESTS_SUMMARY.md
│   ├── CREDENTIALS_GUIDE.md
│   ├── FUNCTIONAL_TESTS_NEW.md
│   └── ...
│
├── scripts/                          # Scripts utilitaires
│   └── check_airtable_config.py     # Vérification config Airtable
│
├── src/                              # Code source principal
│   ├── __init__.py
│   ├── hello_asso_sync.py           # Orchestrateur principal
│   ├── config_loader.py              # Chargement de la configuration
│   │
│   ├── models/                       # Modèles de données typés
│   │   ├── __init__.py
│   │   └── user_subscription.py      # Dataclass UserSubscription
│   │
│   └── clients/                      # Clients pour services externes
│       ├── __init__.py
│       ├── hello_asso_client.py      # Client API HelloAsso
│       ├── airtable_client.py        # Client Airtable direct
│       ├── ovh_client.py             # Client listes OVH
│       └── ovh_email_client.py       # Client email OVH
│
├── tests/                            # Tests
│   ├── __init__.py
│   ├── test_functional.py            # Tests fonctionnels (8 tests)
│   ├── test_refactored_code.py       # Tests unitaires architecture (8)
│   ├── test_airtable_client.py       # Tests unitaires Airtable (20)
│   └── test_ovh_email_client.py      # Tests unitaires OVH Email (14)
│
├── docs/                             # Documentation
│   ├── README.md                     # Documentation principale
│   ├── TEST_README.md                # Guide des tests
│   ├── CREDENTIALS_GUIDE.md          # Guide gestion des credentials
│   ├── ENV_MIGRATION_GUIDE.md        # Guide migration .env
│   └── FUNCTIONAL_TESTS.md           # Guide tests fonctionnels
│
├── config/                           # Templates de configuration
│   ├── .env.example                  # Template credentials
│   └── hello-asso-automation-conf.json.example  # Template config
│
├── .env                              # Credentials (git ignoré)
├── hello-asso-automation-conf.json   # Configuration (git ignoré)
├── hello-asso-automation-conf-test.json  # Config test (git ignoré)
│
├── .gitignore                        # Exclusions git
├── pytest.ini                        # Configuration pytest
├── requirements.txt                  # Dépendances Python
└── .pylintrc                         # Configuration linter
```

## 🎯 Philosophie d'Organisation

### `/src` - Code Source
Tout le code de production, organisé selon le pattern de séparation des responsabilités :
- **`/models`** : Objets de données typés (dataclasses) pour représenter les données métier
- **`/clients`** : Classes dédiées à chaque service externe (HelloAsso, OVH, Airtable)
- **Orchestrateur** : `hello_asso_sync.py` coordonne les différents clients

### `/tests` - Tests
- **Tests unitaires** : Rapides, avec mocks, valident la logique
- **Tests fonctionnels** : Connexion réelle HelloAsso, mocks Airtable/OVH

### `/docs` - Documentation
Toute la documentation centralisée pour faciliter la maintenance.

### `/config` - Templates
Les fichiers d'exemple pour démarrer rapidement, jamais de secrets.

### Racine - Configuration du projet
Fichiers de configuration du projet (.env, pytest.ini, requirements.txt).

## 🚀 Utilisation

### Installation
```bash
pip install -r requirements.txt
```

### Configuration
```bash
# Copier les templates
cp config/.env.example .env
cp config/hello-asso-automation-conf.json.example hello-asso-automation-conf.json

# Éditer avec vos credentials
nano .env
nano hello-asso-automation-conf.json
```

### Lancer les tests
```bash
# Tests unitaires
pytest tests/test_hello_asso_sync.py -v

# Tests fonctionnels
pytest tests/test_hello_asso_sync_functional.py -v -s

# Tous les tests
pytest tests/ -v
```

### Exécution
```bash
python -m src.hello_asso_sync hello-asso-automation-conf.json
```

## 📚 Documentation

- **[README.md](docs/README.md)** - Vue d'ensemble du projet
- **[CREDENTIALS_GUIDE.md](docs/CREDENTIALS_GUIDE.md)** - Gestion sécurisée des credentials
- **[FUNCTIONAL_TESTS.md](docs/FUNCTIONAL_TESTS.md)** - Guide complet des tests fonctionnels
- **[TEST_README.md](docs/TEST_README.md)** - Guide général des tests

## 🔒 Sécurité

Les fichiers sensibles sont dans `.gitignore` :
- `.env` - Credentials
- `hello-asso-automation-conf.json` - Configuration avec données
- `hello-asso-automation-conf-test.json` - Configuration de test

Les templates dans `/config` ne contiennent **jamais** de secrets.
