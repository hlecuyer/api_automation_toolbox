# Tests for hello_asso_sync.py

This directory contains comprehensive tests for the HelloAsso sync module.

## Test Coverage

The test suite includes 22 tests covering:

- **Configuration & Authentication** (6 tests)
  - Configuration file loading
  - HelloAsso API authentication
  - OVH client initialization
  - Error handling for invalid configurations

- **Form Management** (4 tests)
  - Form details retrieval
  - Form data fetching with pagination
  - Edge cases (non-existent forms, multiple pages)

- **OVH Mailing List** (2 tests)
  - Adding subscribers to mailing lists
  - Handling duplicate subscriber conflicts

- **User Synchronization** (6 tests)
  - Date-based filtering
  - Record processing and transformation
  - Custom field handling (first_sub, name fields)
  - State filtering (Processed vs Pending)
  - Webhook failure handling

- **Configuration Updates** (2 tests)
  - Date field updates
  - File write error handling

- **Integration** (2 tests)
  - Full workflow execution
  - Missing configuration handling

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
pytest test_hello_asso_sync.py -v
```

### Run with Coverage Report

```bash
pytest test_hello_asso_sync.py --cov=hello_asso_sync --cov-report=term-missing
```

### Run Specific Test Classes

```bash
# Run only initialization tests
pytest test_hello_asso_sync.py::TestSyncHelloAssoInit -v

# Run only sync tests
pytest test_hello_asso_sync.py::TestSyncUserToAirtable -v
```

### Run Specific Tests

```bash
pytest test_hello_asso_sync.py::TestSyncUserToAirtable::test_sync_user_to_airtable_filters_by_date -v
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

1. **Pagination Bug**: The current implementation has a bug in `get_form_data` where it uses `current_page += current_page` instead of `current_page += 1`. The test suite documents this behavior.

2. **Mocked External Dependencies**: All tests mock:
   - HelloAsso API calls
   - OVH API calls
   - Webhook/Zapier calls
   - File system operations

This ensures tests run quickly and don't depend on external services.

## Code Coverage

Current coverage: **96%**

Uncovered lines (225-231): The `if __name__ == "__main__"` block for command-line execution.

## Contributing

When adding new features to `hello_asso_sync.py`:

1. Add corresponding tests in `test_hello_asso_sync.py`
2. Run the test suite to ensure all tests pass
3. Verify coverage remains above 90%
4. Update this README if new test categories are added
