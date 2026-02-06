# API Automation Toolbox

Outil d'automatisation pour synchroniser les adhésions HelloAsso vers Airtable et gérer les listes de diffusion OVH.

## 🚀 Installation Rapide

```bash
# Cloner le projet
git clone <repo-url>
cd api_automation_toolbox

# Créer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Configurer les credentials
cp .env.example .env
# Éditer .env avec vos vraies valeurs
```

## 📋 Configuration

### Variables d'environnement (.env)

```bash
# HelloAsso
HELLOASSO_CLIENT_ID=your_client_id
HELLOASSO_CLIENT_SECRET=your_client_secret

# Airtable (Base ID doit commencer par 'app')
AIRTABLE_API_KEY=patXXXXXXXXXXXX.XXXXX
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

# OVH
OVH_ENDPOINT=ovh-eu
OVH_APP_KEY=your_app_key
OVH_APP_SECRET=your_app_secret
OVH_CONSUMER_KEY=your_consumer_key
```

### Fichiers de configuration

- `config/hello-asso-automation-conf.json` - Configuration principale
- `config/hello-asso-automation-conf-test.json` - Configuration pour les tests

## 🧪 Tests

### Tous les tests
```bash
pytest tests/ -v
```

### Tests unitaires (42 tests - rapide)
```bash
pytest tests/test_airtable_client.py tests/test_ovh_email_client.py tests/test_refactored_code.py -v
```

### Tests fonctionnels (8 tests - APIs réelles)
```bash
pytest tests/test_functional.py -v
```

## 🛠️ Scripts Utiles

### Vérifier la configuration Airtable
```bash
python scripts/check_airtable_config.py
```

## 📖 Documentation

- [docs/setup/AIRTABLE_SETUP.md](docs/setup/AIRTABLE_SETUP.md) - Configuration Airtable
- [docs/setup/FIX_AIRTABLE_TESTS.md](docs/setup/FIX_AIRTABLE_TESTS.md) - Solutions problèmes Airtable
- [docs/FUNCTIONAL_TESTS_NEW.md](docs/FUNCTIONAL_TESTS_NEW.md) - Documentation tests fonctionnels
- [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) - Structure complète du projet

## 🏗️ Structure du Projet

```
api_automation_toolbox/
├── config/                    # Fichiers de configuration
│   ├── hello-asso-automation-conf.json
│   └── hello-asso-automation-conf-test.json
├── docs/                      # Documentation
│   ├── setup/                 # Guides de configuration
│   └── *.md                   # Docs diverses
├── scripts/                   # Scripts utilitaires
│   └── check_airtable_config.py
├── src/                       # Code source
│   ├── clients/               # Clients API
│   │   ├── hello_asso_client.py
│   │   ├── airtable_client.py
│   │   ├── ovh_client.py
│   │   └── ovh_email_client.py
│   ├── models/                # Modèles de données
│   └── hello_asso_sync.py     # Point d'entrée principal
├── tests/                     # Tests
│   ├── test_functional.py     # Tests fonctionnels (8)
│   └── test_*.py              # Tests unitaires (42)
├── .env                       # Credentials (ne pas commiter!)
├── requirements.txt           # Dépendances Python
└── pytest.ini                 # Configuration pytest
```

## ✅ Statut des Tests

- **Tests unitaires:** 42/42 ✅ (mockés, rapides)
- **Tests fonctionnels:** 8/8 ✅ (APIs réelles)
  - HelloAsso: 3 tests (authentification, formulaires, utilisateurs)
  - Airtable: 3 tests (liste, création/suppression, mise à jour/rollback)
  - OVH Email: 1 test (envoi dry-run)
  - OVH Mailing: 1 test (connexion)

## 🔒 Sécurité

- ✅ Credentials dans `.env` (jamais commité)
- ✅ Tests isolés avec cleanup automatique
- ✅ Pas d'envoi d'email sur vrais users (dry-run uniquement)
- ✅ Rollback automatique des modifications de test

## 📝 License

[Votre licence]
