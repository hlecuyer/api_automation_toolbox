"""Tests for AirtableClient"""

import json
from unittest.mock import Mock, patch, call
import pytest

from src.clients.airtable_client import AirtableClient


@pytest.fixture
def airtable_client():
    """Create an AirtableClient instance for testing"""
    return AirtableClient(
        api_key="test_api_key",
        base_id="test_base_id",
        table_name="Test Table"
    )


@pytest.fixture
def mock_airtable_response():
    """Mock Airtable API response"""
    return {
        "records": [
            {
                "id": "rec123",
                "fields": {
                    "Email": "test@example.com",
                    "Name": "John Doe",
                    "Status": "Active"
                },
                "createdTime": "2024-01-01T00:00:00.000Z"
            }
        ]
    }


@pytest.fixture
def mock_create_response():
    """Mock Airtable create response"""
    return {
        "id": "rec456",
        "fields": {
            "Email": "new@example.com",
            "Name": "Jane Smith"
        },
        "createdTime": "2024-01-02T00:00:00.000Z"
    }


class TestAirtableClientInit:
    """Tests for AirtableClient initialization"""

    def test_init_sets_attributes(self):
        """Test that initialization sets all attributes correctly"""
        client = AirtableClient(
            api_key="my_key",
            base_id="my_base",
            table_name="My Table"
        )
        
        assert client.api_key == "my_key"
        assert client.base_id == "my_base"
        assert client.table_name == "My Table"
        assert client.base_url == "https://api.airtable.com/v0/my_base/My%20Table"
        assert client.headers["Authorization"] == "Bearer my_key"

    def test_init_encodes_table_name(self):
        """Test that table name is URL-encoded"""
        client = AirtableClient(
            api_key="key",
            base_id="base",
            table_name="Test Table With Spaces"
        )
        
        assert "Test%20Table%20With%20Spaces" in client.base_url


class TestAirtableClientListRecords:
    """Tests for list_records method"""

    @patch('src.clients.airtable_client.requests.get')
    def test_list_records_success(self, mock_get, airtable_client, mock_airtable_response):
        """Test successful listing of records"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_airtable_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        records = airtable_client.list_records()

        assert len(records) == 1
        assert records[0]["id"] == "rec123"
        assert records[0]["fields"]["Email"] == "test@example.com"
        mock_get.assert_called_once()

    @patch('src.clients.airtable_client.requests.get')
    def test_list_records_with_filters(self, mock_get, airtable_client, mock_airtable_response):
        """Test listing records with filters"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_airtable_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        records = airtable_client.list_records(
            filter_by_formula="{Status}='Active'",
            max_records=10
        )

        assert len(records) == 1
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["params"]["filterByFormula"] == "{Status}='Active'"
        assert call_kwargs["params"]["maxRecords"] == 10

    @patch('src.clients.airtable_client.requests.get')
    def test_list_records_handles_errors(self, mock_get, airtable_client):
        """Test error handling in list_records"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_get.return_value = mock_response

        records = airtable_client.list_records()

        assert records == []


class TestAirtableClientFindRecord:
    """Tests for find_record_by_email method"""

    @patch('src.clients.airtable_client.requests.get')
    def test_find_record_by_email_found(self, mock_get, airtable_client, mock_airtable_response):
        """Test finding a record by email when it exists"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_airtable_response
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        record = airtable_client.find_record_by_email("test@example.com")

        assert record is not None
        assert record["id"] == "rec123"
        assert record["fields"]["Email"] == "test@example.com"
        
        # Verify the filter formula was used (with E-mail field name)
        call_kwargs = mock_get.call_args[1]
        assert "{E-mail}='test@example.com'" in call_kwargs["params"]["filterByFormula"]

    @patch('src.clients.airtable_client.requests.get')
    def test_find_record_by_email_not_found(self, mock_get, airtable_client):
        """Test finding a record when it doesn't exist"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"records": []}
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        record = airtable_client.find_record_by_email("nonexistent@example.com")

        assert record is None

    @patch('src.clients.airtable_client.requests.get')
    def test_find_record_by_email_handles_errors(self, mock_get, airtable_client):
        """Test error handling in find_record_by_email"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_get.return_value = mock_response

        record = airtable_client.find_record_by_email("test@example.com")

        assert record is None


class TestAirtableClientCreateRecord:
    """Tests for create_record method"""

    @patch('src.clients.airtable_client.requests.post')
    def test_create_record_success(self, mock_post, airtable_client, mock_create_response):
        """Test successful record creation"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_create_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        fields = {"Email": "new@example.com", "Name": "Jane Smith"}
        record = airtable_client.create_record(fields)

        assert record is not None
        assert record["id"] == "rec456"
        assert record["fields"]["Email"] == "new@example.com"
        
        # Verify the request payload
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]
        assert payload["fields"] == fields

    @patch('src.clients.airtable_client.requests.post')
    def test_create_record_handles_errors(self, mock_post, airtable_client):
        """Test error handling in create_record"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_post.return_value = mock_response

        fields = {"Email": "test@example.com"}
        record = airtable_client.create_record(fields)

        assert record is None


class TestAirtableClientUpdateRecord:
    """Tests for update_record method"""

    @patch('src.clients.airtable_client.requests.patch')
    def test_update_record_success(self, mock_patch, airtable_client):
        """Test successful record update"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "rec123",
            "fields": {
                "Email": "test@example.com",
                "Name": "Updated Name"
            }
        }
        mock_response.raise_for_status = Mock()
        mock_patch.return_value = mock_response

        fields = {"Name": "Updated Name"}
        record = airtable_client.update_record("rec123", fields)

        assert record is not None
        assert record["fields"]["Name"] == "Updated Name"
        
        # Verify the URL includes the record ID
        call_args = mock_patch.call_args
        assert "rec123" in call_args[0][0]

    @patch('src.clients.airtable_client.requests.patch')
    def test_update_record_handles_errors(self, mock_patch, airtable_client):
        """Test error handling in update_record"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("API Error")
        mock_patch.return_value = mock_response

        record = airtable_client.update_record("rec123", {"Name": "Test"})

        assert record is None


class TestAirtableClientUpsertRecord:
    """Tests for upsert_record method"""

    @patch.object(AirtableClient, 'find_record_by_email')
    @patch.object(AirtableClient, 'update_record')
    def test_upsert_updates_existing_record(self, mock_update, mock_find, airtable_client):
        """Test upsert updates an existing record"""
        existing_record = {
            "id": "rec123",
            "fields": {"Email": "test@example.com", "Name": "Old Name"}
        }
        mock_find.return_value = existing_record
        mock_update.return_value = {
            "id": "rec123",
            "fields": {"Email": "test@example.com", "Name": "New Name"}
        }

        fields = {"Email": "test@example.com", "Name": "New Name"}
        result = airtable_client.upsert_record("test@example.com", fields)

        assert result is not None
        mock_find.assert_called_once_with("test@example.com")
        mock_update.assert_called_once_with("rec123", fields)

    @patch.object(AirtableClient, 'find_record_by_email')
    @patch.object(AirtableClient, 'create_record')
    def test_upsert_creates_new_record(self, mock_create, mock_find, airtable_client):
        """Test upsert creates a new record when it doesn't exist"""
        mock_find.return_value = None
        mock_create.return_value = {
            "id": "rec456",
            "fields": {"Email": "new@example.com", "Name": "New User"}
        }

        fields = {"Email": "new@example.com", "Name": "New User"}
        result = airtable_client.upsert_record("new@example.com", fields)

        assert result is not None
        mock_find.assert_called_once_with("new@example.com")
        mock_create.assert_called_once_with(fields)

    @patch.object(AirtableClient, 'find_record_by_email')
    def test_upsert_handles_find_errors(self, mock_find, airtable_client):
        """Test upsert handles errors during find"""
        mock_find.side_effect = Exception("Find error")

        result = airtable_client.upsert_record("test@example.com", {"Name": "Test"})

        assert result is None


class TestAirtableClientDryRun:
    """Tests for dry-run mode"""

    def test_dry_run_list_returns_empty(self, airtable_client):
        """Test list_records returns empty list in dry-run mode"""
        records = airtable_client.list_records(dry_run=True)
        assert records == []

    def test_dry_run_find_returns_none(self, airtable_client):
        """Test find_record_by_email returns None in dry-run mode"""
        record = airtable_client.find_record_by_email("test@example.com", dry_run=True)
        assert record is None

    def test_dry_run_create_returns_mock(self, airtable_client):
        """Test create_record returns mock data in dry-run mode"""
        fields = {"Email": "test@example.com", "Name": "Test User"}
        record = airtable_client.create_record(fields, dry_run=True)
        
        assert record is not None
        assert record["id"] == "dry_run_record_id"
        assert record["fields"] == fields

    def test_dry_run_update_returns_mock(self, airtable_client):
        """Test update_record returns mock data in dry-run mode"""
        fields = {"Name": "Updated Name"}
        record = airtable_client.update_record("rec123", fields, dry_run=True)
        
        assert record is not None
        assert record["id"] == "rec123"
        assert record["fields"] == fields

    def test_dry_run_upsert_returns_mock(self, airtable_client):
        """Test upsert_record returns mock data in dry-run mode"""
        fields = {"Email": "test@example.com", "Name": "Test User"}
        record = airtable_client.upsert_record("test@example.com", fields, dry_run=True)
        
        assert record is not None
        assert record["fields"] == fields
