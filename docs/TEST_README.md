# Tests for HelloAsso Sync

This directory contains comprehensive tests for the HelloAsso sync application.

## Test Files

- **`test_refactored_code.py`**: Tests unitaires pour la nouvelle architecture (9 tests)
- **`test_hello_asso_sync_functional.py`**: Tests fonctionnels avec vraie API HelloAsso (6 tests)
- **`test_hello_asso_sync.py`**: Tests unitaires legacy (22 tests, maintenu pour référence)

## Test Coverage - Nouvelle Architecture

La suite de tests `test_refactored_code.py` couvre:

- **UserSubscription Model** (3 tests)
  - Data parsing from HelloAsso API response
  - Field transformation (uppercase, year conversion)
  - Webhook payload generation

- **HelloAssoClient** (1 test)
  - Subscription parsing with real data structure

- **OVHMailingClient** (2 tests)
  - Adding subscribers to mailing lists
  - Handling duplicate subscriber conflicts (ResourceConflictError)

- **WebhookClient** (1 test)
  - Sending UserSubscription data to webhooks

- **SyncHelloAsso Integration** (2 tests)
  - Full workflow with all three clients
  - Client initialization and orchestration

## Test Coverage - Legacy Architecture

La suite de tests `test_hello_asso_sync.py` couvre :

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
pytest tests/test_hello_asso_sync_functional.py -v -s

# Tests legacy
pytest tests/test_hello_asso_sync.py -v
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
   - Webhook/Zapier calls
   - File system operations

3. **Tests Fonctionnels**: Les tests dans `test_hello_asso_sync_functional.py` utilisent la **vraie API HelloAsso** mais mockent OVH et les webhooks pour un mode dry-run sécurisé.

Ceci garantit que les tests unitaires sont rapides et ne dépendent pas de services externes, tout en validant l'intégration réelle avec HelloAsso.

## Code Coverage

- **Nouvelle architecture**: 9/9 tests passent
- **Tests fonctionnels**: 6/6 tests passent (avec vraie API HelloAsso)
- **Tests legacy**: 22 tests (maintenus pour référence)

## Contributing

When adding new features to `hello_asso_sync.py`:

1. Add corresponding tests in `test_hello_asso_sync.py`
2. Run the test suite to ensure all tests pass
3. Verify coverage remains above 90%
4. Update this README if new test categories are added
