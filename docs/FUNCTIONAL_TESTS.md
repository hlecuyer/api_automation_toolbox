# Tests Fonctionnels

## Vue d'ensemble

La suite de tests fonctionnels (`tests/test_functional.py`) teste les connexions réelles aux APIs:
- **HelloAsso**: Authentification et récupération de données
- **Airtable**: CRUD sur les utilisateurs
- **OVH Email**: Envoi d'emails
- **OVH Mailing List**: Gestion de liste de diffusion

## Prérequis

### Variables d'environnement (.env)

```bash
# HelloAsso
HELLOASSO_CLIENT_ID=your_client_id
HELLOASSO_CLIENT_SECRET=your_client_secret
HELLOASSO_API_URL=https://api.helloasso.com

# Airtable
AIRTABLE_API_KEY=patXXXXXXXXXXXX.XXXXX
AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX  # Doit commencer par 'app'

# OVH
OVH_ENDPOINT=ovh-eu
OVH_APP_KEY=your_app_key
OVH_APP_SECRET=your_app_secret
OVH_CONSUMER_KEY=your_consumer_key
```

### Installation

```bash
pip install -r requirements.txt
```

## Exécution des tests

### Tous les tests fonctionnels

```bash
pytest tests/test_functional.py -v -s
```

### Tests par connexion

```bash
# HelloAsso seulement
pytest tests/test_functional.py::TestHelloAssoConnection -v -s

# Airtable seulement
pytest tests/test_functional.py::TestAirtableConnection -v -s

# OVH Email seulement
pytest tests/test_functional.py::TestOVHEmailConnection -v -s

# OVH Mailing List seulement
pytest tests/test_functional.py::TestOVHMailingListConnection -v -s
```

### Test spécifique

```bash
pytest tests/test_functional.py::TestHelloAssoConnection::test_get_real_users -v -s
```

## Description des tests

### TestHelloAssoConnection

#### test_authentication
- **Objectif**: Vérifier l'authentification HelloAsso
- **Actions**: 
  - Initialise le client
  - Vérifie que le token est obtenu
  - Vérifie que les headers sont configurés
- **Résultat attendu**: ✓ Token valide avec longueur > 0

#### test_get_forms
- **Objectif**: Récupérer les formulaires HelloAsso
- **Actions**:
  - Authentification
  - Récupère le formulaire "Adhésion année 2026"
- **Résultat attendu**: ✓ Formulaire trouvé avec slug et type

#### test_get_real_users
- **Objectif**: Récupérer de vrais utilisateurs
- **Actions**:
  - Récupère les items du formulaire 2026
  - Filtre les items "Processed"
  - Affiche un échantillon
- **Résultat attendu**: ✓ Liste d'utilisateurs avec emails

### TestAirtableConnection

#### test_list_records
- **Objectif**: Lister les enregistrements Airtable
- **Actions**:
  - Liste jusqu'à 5 enregistrements
  - Affiche les IDs
- **Résultat attendu**: ✓ Liste retournée (peut être vide)

#### test_create_and_delete_user
- **Objectif**: Test CRUD - Création et suppression
- **Actions**:
  1. Crée un utilisateur de test (email: `test-YYYYMMDDHHMMSS@test-automation.local`)
  2. Vérifie que l'enregistrement existe
  3. Supprime l'enregistrement (cleanup)
- **Résultat attendu**: ✓ Création + suppression réussies
- **Note**: Skip si `AIRTABLE_BASE_ID` invalide (doit commencer par 'app')

#### test_update_and_rollback_user
- **Objectif**: Test CRUD - Mise à jour et rollback
- **Actions**:
  1. Trouve un enregistrement existant
  2. Modifie le champ `Nom` 
  3. Vérifie la mise à jour
  4. Restaure la valeur originale (rollback)
- **Résultat attendu**: ✓ Mise à jour + rollback réussis
- **Note**: Skip si aucun enregistrement disponible

### TestOVHEmailConnection

#### test_send_test_email
- **Objectif**: Tester l'envoi d'email
- **Actions**:
  - Prépare un email pour `support@dsi.coop`
  - Envoie en mode DRY RUN (pas d'envoi réel)
- **Résultat attendu**: ✓ Email préparé sans erreur
- **Protection**: **Pas d'envoi sur de vrais users** (uniquement dry-run vers support@)

### TestOVHMailingListConnection

#### test_connection
- **Objectif**: Vérifier l'initialisation du client
- **Actions**:
  - Initialise le client mailing list
  - Vérifie les attributs (domain, list name)
- **Résultat attendu**: ✓ Client correctement initialisé

## Résultats attendus

```
tests/test_functional.py::TestHelloAssoConnection::test_authentication PASSED
tests/test_functional.py::TestHelloAssoConnection::test_get_forms PASSED
tests/test_functional.py::TestHelloAssoConnection::test_get_real_users PASSED
tests/test_functional.py::TestAirtableConnection::test_list_records PASSED
tests/test_functional.py::TestAirtableConnection::test_create_and_delete_user SKIPPED*
tests/test_functional.py::TestAirtableConnection::test_update_and_rollback_user SKIPPED*
tests/test_functional.py::TestOVHEmailConnection::test_send_test_email PASSED
tests/test_functional.py::TestOVHMailingListConnection::test_connection PASSED

6 passed, 2 skipped
```

\* *Skipped si configuration Airtable incomplète ou base vide*

## Tests unitaires

Les tests unitaires (mockés) restent disponibles:

```bash
# Tous les tests unitaires
pytest tests/test_airtable_client.py tests/test_ovh_email_client.py tests/test_refactored_code.py -v

# Total: 42 tests unitaires passent
```

## Tous les tests (unitaires + fonctionnels)

```bash
pytest tests/ -v

# Résultat attendu: 48 passed, 2 skipped
```

## Dépannage

### "Invalid Airtable base_id"
- Vérifier que `AIRTABLE_BASE_ID` commence par `app`
- Format correct: `appXXXXXXXXXXXXXX`

### "No records available"
- La table Airtable est vide
- Les tests de mise à jour seront skipped automatiquement

### Erreurs d'authentification HelloAsso
- Vérifier `HELLOASSO_CLIENT_ID` et `HELLOASSO_CLIENT_SECRET`
- Les credentials doivent être valides et actifs

### Erreurs OVH
- Vérifier toutes les variables `OVH_*`
- Le consumer key doit être validé

## Sécurité

- ✅ **Pas d'envoi d'email sur de vrais users** (uniquement support@dsi.coop en dry-run)
- ✅ **Cleanup automatique** des enregistrements de test Airtable
- ✅ **Rollback automatique** des modifications de test
- ✅ **Credentials dans .env** (jamais committé)
- ✅ **Tests isolés** - pas d'effet de bord entre tests
