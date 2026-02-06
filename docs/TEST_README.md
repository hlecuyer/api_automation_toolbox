# Tests for HelloAsso Sync

This directory contains comprehensive tests for the HelloAsso sync application.

## Test Files

- **`test_functional.py`**: Tests fonctionnels avec vraies APIs (8 tests) - HelloAsso, Airtable, OVH
- **`test_refactored_code.py`**: Tests unitaires architecture (8 tests)
- **`test_airtable_client.py`**: Tests unitaires Airtable (20 tests)
- **`test_ovh_email_client.py`**: Tests unitaires OVH Email (14 tests)

## Test Coverage - Nouvelle Architecture

La suite de tests `test_refactored_code.py` couvre:

- **UserSubscription Model** (3 tests)
  - Data parsing from HelloAsso API response
  - Field transformation (uppercase, year conversion)
  - Airtable payload generation

- **HelloAssoClient** (1 test)
  - Subscription parsing with real data structure

- **OVHMailingClient** (2 tests)
  - Adding subscribers to mailing lists
  - Handling duplicate subscriber conflicts (ResourceConflictError)

- **AirtableClient** (20 tests)
  - CRUD operations on Airtable records
  - Upsert functionality (find or create)
  - Dry-run mode

- **OVHEmailClient** (14 tests)
  - Sending emails via OVH API
  - Email validation
  - Dry-run mode

- **SyncHelloAsso Integration** (2 tests)
  - Full workflow with all three clients
  - Client initialization and orchestration

## Test Coverage - Legacy Architecture

## Tests Disponibles

- **Configuration & Authentication** (6 tests)
- **Form Management** (4 tests)
- **OVH Mailing List** (2 tests)
- **User Synchronization** (6 tests)
- **Configuration Updates** (2 tests)
- **Integration** (2 tests)

## Running the Tests

### Prerequisites

Install the test dependencies:

```bash
pip install -r requirements.txt
```

Or install just the test packages:

```bash
pip install pytest pytest-mock pytest-cov
```

### Run All Tests

```bash
# Tous les tests
pytest tests/ -v

# Tests unitaires nouvelle architecture uniquement
pytest tests/test_refactored_code.py -v

# Tests fonctionnels (API réelle HelloAsso)
pytest tests/test_functional.py -v -s

# Tests legacy
pytest tests/test_refactored_code.py tests/test_airtable_client.py tests/test_ovh_email_client.py -v
```

### Run with Coverage Report

```bash
pytest tests/test_refactored_code.py --cov=src --cov-report=term-missing
```

### Run Specific Test Classes

```bash
# Tests du modèle UserSubscription
pytest tests/test_refactored_code.py::TestUserSubscription -v

# Tests du client HelloAsso
pytest tests/test_refactored_code.py::TestHelloAssoClient -v

# Tests d'intégration
pytest tests/test_refactored_code.py::TestSyncHelloAssoIntegration -v
```

### Run Specific Tests

```bash
pytest tests/test_refactored_code.py::TestUserSubscription::test_from_hello_asso_item -v
```

## Test Structure

The tests use:
- **pytest**: Test framework
- **unittest.mock**: For mocking external dependencies (API calls, file I/O)
- **pytest fixtures**: For reusable test data and configuration

### Key Fixtures

- `sample_config`: Sample configuration dictionary
- `config_file`: Temporary config file for testing
- `mock_auth_response`: Mock HelloAsso authentication response
- `sample_form_data`: Mock form data from HelloAsso API
- `sample_items_data`: Mock subscription items data

## Known Issues & Notes

1. **Pagination Bug Fixed**: Le bug de pagination dans `get_form_data` (utilisant `current_page += current_page`) a été corrigé dans `HelloAssoClient.get_form_items()` qui utilise maintenant `current_page += 1`.

2. **Mocked External Dependencies**: Les tests unitaires mockent :
   - HelloAsso API calls
   - OVH API calls
   - Airtable/OVH calls
   - File system operations

3. **Tests Fonctionnels**: Les tests dans `test_functional.py` utilisent les **vraies APIs** (HelloAsso, Airtable, OVH) avec rollback automatique.

Ceci garantit que les tests unitaires sont rapides et ne dépendent pas de services externes, tout en validant l'intégration réelle avec HelloAsso.

## Code Coverage

**Total : 61 tests, 89% de couverture globale**

- `test_refactored_code.py` : **17 tests** (UserSubscription, HelloAssoClient, OVHMailingClient, SyncHelloAsso, error handling, config validation)
- `test_functional.py` : **8 tests** (HelloAsso, Airtable, OVH Email/Mailing - APIs réelles)
- `test_airtable_client.py` : **20 tests** (CRUD, upsert, dry-run)
- `test_ovh_email_client.py` : **14 tests** (email sending, validation, dry-run)

**Couverture par module :**
- `airtable_client.py` : 99%
- `ovh_email_client.py` : 98%
- `user_subscription.py` : 91%
- `config_loader.py` : 88%
- `hello_asso_client.py` : 86%
- `ovh_client.py` : 83%
- `hello_asso_sync.py` : 74%

**Note :** La couverture de 89% couvre tous les chemins principaux. Les 11% restants sont principalement des cas d'erreur rares (échecs réseau, fichiers illisibles, etc.).

## Contributing

When adding new features to `hello_asso_sync.py`:

1. Add corresponding tests in `test_refactored_code.py` or `test_functional.py`
2. Run the test suite to ensure all tests pass
3. Verify coverage: `pytest --cov=src --cov-report=term-missing`
4. Update this README if new test categories are added
