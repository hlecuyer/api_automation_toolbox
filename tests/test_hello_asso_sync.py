"""Tests for hello_asso_sync module"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch, mock_open
import pytest
import ovh

from src.hello_asso_sync import SyncHelloAsso


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables for all tests to avoid loading from .env"""
    # Clear any existing env vars that might interfere
    monkeypatch.delenv("HELLOASSO_CLIENT_ID", raising=False)
    monkeypatch.delenv("HELLOASSO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("OVH_ENDPOINT", raising=False)
    monkeypatch.delenv("OVH_APP_KEY", raising=False)
    monkeypatch.delenv("OVH_APP_SECRET", raising=False)
    monkeypatch.delenv("OVH_CONSUMER_KEY", raising=False)


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "credentials": {
            "helloAsso": {
                "id": "test_id",
                "secret": "test_secret"
            },
            "ovh": {
                "endpoint": "ovh-eu",
                "ak": "test_ak",
                "as": "test_as",
                "ck": "test_ck"
            }
        },
        "conf": {
            "helloAsso": {
                "api_url": "https://api.helloasso.com",
                "organization_name": "test_org",
                "form_name": "Test Form",
                "subscription_after": "2024-01-01T00:00:00",
                "first_sub_field": "first_sub",
                "name_field": "name",
                "default": {
                    "default_field": "default_value"
                }
            },
            "cotisation_label": "test_label",
            "groupe": "test_group",
            "webhook_url": "https://webhook.test/endpoint",
            "ovh": {
                "mailing_list": {
                    "name": "test_list",
                    "domain": "test.org"
                }
            }
        }
    }


@pytest.fixture
def config_file(sample_config, tmp_path):
    """Create a temporary config file"""
    config_path = tmp_path / "test_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(sample_config, f)
    return str(config_path)


@pytest.fixture
def mock_auth_response():
    """Mock authentication response"""
    return {"access_token": "test_token_123"}


@pytest.fixture
def sample_form_data():
    """Sample form data from HelloAsso API"""
    return {
        "data": [
            {
                "title": "Test Form",
                "formType": "Membership",
                "formSlug": "test-form-slug"
            },
            {
                "title": "Other Form",
                "formType": "Event",
                "formSlug": "other-form-slug"
            }
        ]
    }


@pytest.fixture
def sample_items_data():
    """Sample items data with pagination"""
    return {
        "data": [
            {
                "state": "Processed",
                "payer": {
                    "email": "test@example.com"
                },
                "user": {
                    "firstName": "John",
                    "lastName": "doe"
                },
                "order": {
                    "date": "2024-06-15T10:30:00.000+02:00"
                },
                "customFields": [
                    {
                        "name": "custom_field_1",
                        "answer": "answer_1"
                    }
                ]
            },
            {
                "state": "Processed",
                "payer": {
                    "email": "jane@example.com"
                },
                "user": {
                    "firstName": "Jane",
                    "lastName": "smith"
                },
                "order": {
                    "date": "2024-06-16T14:20:00.000+02:00"
                },
                "customFields": [
                    {
                        "name": "first_sub",
                        "answer": "Oui"
                    },
                    {
                        "name": "name",
                        "answer": "jane"
                    }
                ]
            }
        ],
        "pagination": {
            "totalPages": 1,
            "currentPage": 1
        }
    }


class TestSyncHelloAssoInit:
    """Tests for SyncHelloAsso initialization"""

    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_init_loads_config_successfully(self, mock_ovh_client, mock_post, 
                                           config_file, mock_auth_response):
        """Test that initialization loads config file correctly"""
        mock_response = Mock()
        mock_response.json.return_value = mock_auth_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        sync = SyncHelloAsso(config_file)

        assert sync.conf_path == config_file
        assert sync.conf["helloAsso"]["organization_name"] == "test_org"
        assert sync.conf["cotisation_label"] == "test_label"
        mock_post.assert_called_once()

    @patch('src.clients.hello_asso_client.requests.post')
    def test_init_fails_with_invalid_config_path(self, mock_post):
        """Test that initialization fails with non-existent config file"""
        with pytest.raises(Exception):
            SyncHelloAsso("/nonexistent/path/config.json")

    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_init_calls_authentication(self, mock_ovh_client, mock_post, 
                                       config_file, mock_auth_response):
        """Test that initialization calls authentication"""
        mock_response = Mock()
        mock_response.json.return_value = mock_auth_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        sync = SyncHelloAsso(config_file)

        # Check that the HelloAsso client has the token
        assert sync.hello_asso_client._token == "test_token_123"

    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_init_creates_ovh_client(self, mock_ovh_client, mock_post,
                                     config_file, mock_auth_response, sample_config):
        """Test that OVH client is initialized correctly"""
        mock_response = Mock()
        mock_response.json.return_value = mock_auth_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        sync = SyncHelloAsso(config_file)

        mock_ovh_client.assert_called_once_with(
            endpoint=sample_config["credentials"]["ovh"]["endpoint"],
            application_key=sample_config["credentials"]["ovh"]["ak"],
            application_secret=sample_config["credentials"]["ovh"]["as"],
            consumer_key=sample_config["credentials"]["ovh"]["ck"]
        )


class TestAuthenticate:
    """Tests for authentication method"""

    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_authenticate_returns_token(self, mock_ovh_client, mock_post, 
                                        config_file, mock_auth_response):
        """Test successful authentication returns access token"""
        mock_response = Mock()
        mock_response.json.return_value = mock_auth_response
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        sync = SyncHelloAsso(config_file)

        # Authentication is called in __init__, check the client token
        assert sync.hello_asso_client._token == "test_token_123"

    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_authenticate_raises_on_missing_token(self, mock_ovh_client, mock_post, config_file):
        """Test authentication raises exception when token is missing"""
        mock_response = Mock()
        mock_response.json.return_value = {}  # No access_token
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        with pytest.raises(Exception):
            SyncHelloAsso(config_file)


class TestGetFormDetails:
    """Tests for get_form_details method"""

    @patch('src.clients.hello_asso_client.requests.get')
    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_get_form_details_returns_matching_form(self, mock_ovh_client, mock_post, 
                                                     mock_get, config_file, 
                                                     mock_auth_response, sample_form_data):
        """Test get_form_details returns correct form"""
        # Setup auth
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_auth.raise_for_status = Mock()
        mock_post.return_value = mock_auth

        # Setup get_form_details
        mock_forms = Mock()
        mock_forms.json.return_value = sample_form_data
        mock_forms.raise_for_status = Mock()
        mock_get.return_value = mock_forms

        sync = SyncHelloAsso(config_file)
        result = sync.hello_asso_client.get_form_details("Test Form")

        assert result["title"] == "Test Form"
        assert result["formType"] == "Membership"
        assert result["formSlug"] == "test-form-slug"

    @patch('src.clients.hello_asso_client.requests.get')
    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_get_form_details_returns_empty_when_not_found(self, mock_ovh_client, 
                                                           mock_post, mock_get, 
                                                           config_file, mock_auth_response, 
                                                           sample_form_data):
        """Test get_form_details returns empty dict when form not found"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_auth.raise_for_status = Mock()
        mock_post.return_value = mock_auth

        mock_forms = Mock()
        mock_forms.json.return_value = sample_form_data
        mock_forms.raise_for_status = Mock()
        mock_get.return_value = mock_forms

        sync = SyncHelloAsso(config_file)
        result = sync.hello_asso_client.get_form_details("Non-existent Form")

        assert result == {}


class TestGetFormData:
    """Tests for get_form_data method"""

    @patch('src.clients.hello_asso_client.requests.get')
    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_get_form_data_single_page(self, mock_ovh_client, mock_post, mock_get, 
                                       config_file, mock_auth_response, sample_items_data):
        """Test get_form_data with single page response"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_auth.raise_for_status = Mock()
        mock_post.return_value = mock_auth

        mock_items = Mock()
        mock_items.json.return_value = sample_items_data
        mock_items.raise_for_status = Mock()
        mock_get.return_value = mock_items

        sync = SyncHelloAsso(config_file)
        result = sync.hello_asso_client.get_form_items("Membership", "test-form-slug")

        assert len(result) == 2
        assert result[0]["payer"]["email"] == "test@example.com"

    @patch('src.clients.hello_asso_client.requests.get')
    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_get_form_data_multiple_pages(self, mock_ovh_client, mock_post, mock_get, 
                                          config_file, mock_auth_response):
        """Test get_form_data handles pagination correctly"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_auth.raise_for_status = Mock()
        mock_post.return_value = mock_auth

        first_page = {
            "data": [{"id": 1}],
            "pagination": {"totalPages": 2, "currentPage": 1}
        }
        
        second_page = {
            "data": [{"id": 2}],
            "pagination": {"totalPages": 2, "currentPage": 2}
        }

        mock_get_response1 = Mock()
        mock_get_response1.json.return_value = first_page
        mock_get_response1.raise_for_status = Mock()
        
        mock_get_response2 = Mock()
        mock_get_response2.json.return_value = second_page
        mock_get_response2.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_get_response1, mock_get_response2]

        sync = SyncHelloAsso(config_file)
        result = sync.hello_asso_client.get_form_items("Membership", "test-form-slug")

        # Now pagination is fixed - should get both pages
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2


class TestUpdateOvhMailingList:
    """Tests for OVH mailing list method"""

    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_update_ovh_mailing_list_success(self, mock_ovh_client, mock_post, 
                                             config_file, mock_auth_response):
        """Test successful mailing list update"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_auth.raise_for_status = Mock()
        mock_post.return_value = mock_auth

        mock_client_instance = Mock()
        mock_ovh_client.return_value = mock_client_instance

        sync = SyncHelloAsso(config_file)
        sync.ovh_client.add_subscriber("test@example.com")

        mock_client_instance.post.assert_called_once()

    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_update_ovh_mailing_list_handles_conflict(self, mock_ovh_client, mock_post, 
                                                      config_file, mock_auth_response):
        """Test that ResourceConflictError is handled gracefully"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_auth.raise_for_status = Mock()
        mock_post.return_value = mock_auth

        mock_client_instance = Mock()
        mock_client_instance.post.side_effect = ovh.exceptions.ResourceConflictError("Already exists")
        mock_ovh_client.return_value = mock_client_instance

        sync = SyncHelloAsso(config_file)
        # Should not raise exception
        result = sync.ovh_client.add_subscriber("test@example.com")
        assert result is True


class TestSyncUserToAirtable:
    """Tests for sync_subscriptions method"""

    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.hello_asso_client.requests.get')
    @patch('src.clients.ovh_client.ovh.Client')
    @patch('src.clients.webhook_client.requests.post')
    def test_sync_user_to_airtable_filters_by_date(self, mock_webhook_post, mock_ovh_client, 
                                                    mock_get, mock_auth_post,
                                                    config_file, mock_auth_response, 
                                                    sample_items_data, sample_form_data):
        """Test that sync filters by date correctly"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_auth.raise_for_status = Mock()
        mock_auth_post.return_value = mock_auth

        mock_client_instance = Mock()
        mock_ovh_client.return_value = mock_client_instance

        # Setup form details and items
        mock_forms = Mock()
        mock_forms.json.return_value = sample_form_data
        mock_forms.raise_for_status = Mock()
        
        mock_items = Mock()
        mock_items.json.return_value = sample_items_data
        mock_items.raise_for_status = Mock()
        
        mock_get.side_effect = [mock_forms, mock_items]

        sync = SyncHelloAsso(config_file)
        
        # Use date after all items - should not send any
        sync.run()

        # No webhook calls should have been made
        assert mock_webhook_post.call_count == 0

    @patch('src.hello_asso_sync.requests.post')
    @patch('src.hello_asso_sync.ovh.Client')
    def test_sync_user_to_airtable_processes_valid_records(self, mock_ovh_client, 
                                                           mock_post, config_file, 
                                                           mock_auth_response, 
                                                           sample_items_data):
        """Test that valid records are processed correctly"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_webhook = Mock()
        mock_webhook.status_code = 200
        mock_post.side_effect = [mock_auth, mock_webhook, mock_webhook]

        mock_client_instance = Mock()
        mock_ovh_client.return_value = mock_client_instance

        sync = SyncHelloAsso(config_file)
        
        # Use date before all items - should send all
        sync.sync_subscriptions(sample_items_data["data"], "2024-01-01T00:00:00")  # type: ignore

        # Auth + 2 webhook calls
        assert mock_post.call_count == 3

    @patch('src.hello_asso_sync.requests.post')
    @patch('src.hello_asso_sync.ovh.Client')
    def test_sync_user_to_airtable_handles_first_sub_field(self, mock_ovh_client, 
                                                           mock_post, config_file, 
                                                           mock_auth_response):
        """Test that first_sub field is converted to year when 'Oui'"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_webhook = Mock()
        mock_webhook.status_code = 200
        
        # Patch requests.post inside hello_asso_sync module
        mock_post.return_value = mock_auth
        
        mock_client_instance = Mock()
        mock_ovh_client.return_value = mock_client_instance

        sync = SyncHelloAsso(config_file)
        
        # Now setup the webhook mock after initialization
        with patch('src.hello_asso_sync.requests.post', return_value=mock_webhook) as webhook_post:
            data = [{
                "state": "Processed",
                "payer": {"email": "test@example.com"},
                "user": {"firstName": "John", "lastName": "doe"},
                "order": {"date": "2024-06-15T10:30:00.000+02:00"},
                "customFields": [{"name": "first_sub", "answer": "Oui"}]
            }]
            
            sync.sync_subscriptions(data, "2024-01-01T00:00:00")  # type: ignore

            # Verify webhook was called
            assert webhook_post.called
            webhook_data = json.loads(webhook_post.call_args[1]['data'])
            assert webhook_data["first_sub"] == "2024"

    @patch('src.hello_asso_sync.requests.post')
    @patch('src.hello_asso_sync.ovh.Client')
    def test_sync_user_to_airtable_converts_name_to_upper(self, mock_ovh_client, 
                                                          mock_post, config_file, 
                                                          mock_auth_response):
        """Test that name field is converted to uppercase"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_webhook = Mock()
        mock_webhook.status_code = 200
        
        mock_post.return_value = mock_auth
        
        mock_client_instance = Mock()
        mock_ovh_client.return_value = mock_client_instance

        sync = SyncHelloAsso(config_file)
        
        # Now setup the webhook mock after initialization
        with patch('src.hello_asso_sync.requests.post', return_value=mock_webhook) as webhook_post:
            data = [{
                "state": "Processed",
                "payer": {"email": "test@example.com"},
                "user": {"firstName": "John", "lastName": "Doe"},
                "order": {"date": "2024-06-15T10:30:00.000+02:00"},
                "customFields": [{"name": "name", "answer": "john"}]
            }]
            
            sync.sync_subscriptions(data, "2024-01-01T00:00:00")  # type: ignore

            # Verify webhook was called
            assert webhook_post.called
            webhook_data = json.loads(webhook_post.call_args[1]['data'])
            assert webhook_data["name"] == "JOHN"
            assert webhook_data["lastName"] == "DOE"

    @patch('src.hello_asso_sync.requests.post')
    @patch('src.hello_asso_sync.ovh.Client')
    def test_sync_user_to_airtable_skips_non_processed(self, mock_ovh_client, 
                                                       mock_post, config_file, 
                                                       mock_auth_response):
        """Test that non-processed records are skipped"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_post.return_value = mock_auth

        mock_client_instance = Mock()
        mock_ovh_client.return_value = mock_client_instance

        sync = SyncHelloAsso(config_file)
        
        data = [{
            "state": "Pending",
            "payer": {"email": "test@example.com"},
            "user": {"firstName": "John", "lastName": "doe"},
            "order": {"date": "2024-06-15T10:30:00.000+02:00"},
            "customFields": []
        }]
        
        sync.sync_subscriptions(data, "2024-01-01T00:00:00")  # type: ignore

        # Only auth call should have been made
        assert mock_post.call_count == 1

    @patch('builtins.print')
    @patch('src.hello_asso_sync.sys.exit')
    @patch('src.hello_asso_sync.requests.post')
    @patch('src.hello_asso_sync.ovh.Client')
    def test_sync_user_to_airtable_exits_on_webhook_failure(self, mock_ovh_client, 
                                                            mock_post, mock_exit, 
                                                            mock_print, config_file, 
                                                            mock_auth_response):
        """Test that sync exits when webhook returns error"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_webhook = Mock()
        mock_webhook.status_code = 500
        mock_post.side_effect = [mock_auth, mock_webhook]

        mock_client_instance = Mock()
        mock_ovh_client.return_value = mock_client_instance

        sync = SyncHelloAsso(config_file)
        
        data = [{
            "state": "Processed",
            "payer": {"email": "test@example.com"},
            "user": {"firstName": "John", "lastName": "doe"},
            "order": {"date": "2024-06-15T10:30:00.000+02:00"},
            "customFields": []
        }]
        
        sync.sync_subscriptions(data, "2024-01-01T00:00:00")  # type: ignore

        mock_exit.assert_called_once_with(-1)


class TestUpdateDateConf:
    """Tests for update_date_conf method"""

    @patch('src.hello_asso_sync.requests.post')
    @patch('src.hello_asso_sync.ovh.Client')
    def test_update_date_conf_updates_file(self, mock_ovh_client, mock_post, 
                                          config_file, mock_auth_response):
        """Test that update_date_conf updates config file with current date"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_post.return_value = mock_auth

        sync = SyncHelloAsso(config_file)
        
        old_date = sync.conf_global["conf"]["helloAsso"]["subscription_after"]
        sync.update_date_conf()
        
        # Read the config file
        with open(config_file, "r", encoding="utf-8") as f:
            updated_config = json.load(f)
        
        new_date = updated_config["conf"]["helloAsso"]["subscription_after"]
        assert new_date != old_date
        
        # Verify it's a valid datetime format
        datetime.strptime(new_date, "%Y-%m-%dT%H:%M:%S")

    @patch('src.hello_asso_sync.requests.post')
    @patch('src.hello_asso_sync.ovh.Client')
    def test_update_date_conf_raises_on_write_error(self, mock_ovh_client, mock_post, 
                                                    config_file, mock_auth_response):
        """Test that update_date_conf raises exception on write error"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_post.return_value = mock_auth

        sync = SyncHelloAsso(config_file)
        
        # Make file read-only
        os.chmod(config_file, 0o444)
        
        with pytest.raises(Exception):
            sync.update_date_conf()
        
        # Restore write permission
        os.chmod(config_file, 0o644)


class TestRun:
    """Tests for run method"""

    @patch('src.hello_asso_sync.requests.get')
    @patch('src.hello_asso_sync.requests.post')
    @patch('src.hello_asso_sync.ovh.Client')
    def test_run_executes_full_workflow(self, mock_ovh_client, mock_post, mock_get, 
                                        config_file, mock_auth_response, 
                                        sample_form_data, sample_items_data):
        """Test that run method executes the full workflow"""
        mock_auth = Mock()
        mock_auth.json.return_value = mock_auth_response
        mock_webhook = Mock()
        mock_webhook.status_code = 200
        mock_post.side_effect = [mock_auth, mock_webhook, mock_webhook]

        mock_forms = Mock()
        mock_forms.json.return_value = sample_form_data
        mock_items = Mock()
        mock_items.json.return_value = sample_items_data
        mock_get.side_effect = [mock_forms, mock_items]

        mock_client_instance = Mock()
        mock_ovh_client.return_value = mock_client_instance

        sync = SyncHelloAsso(config_file)
        sync.run()

        # Verify workflow calls
        assert mock_get.call_count == 2  # get_form_details + get_form_data
        assert mock_post.call_count >= 1  # At least auth call

    @patch('src.hello_asso_sync.requests.get')
    @patch('src.hello_asso_sync.requests.post')
    @patch('src.hello_asso_sync.ovh.Client')
    def test_run_handles_missing_subscription_after(self, mock_ovh_client, mock_post, 
                                                    mock_get, config_file, 
                                                    mock_auth_response, sample_form_data, 
                                                    sample_items_data, sample_config):
        """Test that run handles missing subscription_after field"""
        # Remove subscription_after from config
        del sample_config["conf"]["helloAsso"]["subscription_after"]
        
        # Create new config file
        temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(sample_config, temp_config)
        temp_config.close()

        try:
            mock_auth = Mock()
            mock_auth.json.return_value = mock_auth_response
            mock_webhook = Mock()
            mock_webhook.status_code = 200
            mock_post.side_effect = [mock_auth, mock_webhook, mock_webhook]

            mock_forms = Mock()
            mock_forms.json.return_value = sample_form_data
            mock_items = Mock()
            mock_items.json.return_value = sample_items_data
            mock_get.side_effect = [mock_forms, mock_items]

            mock_client_instance = Mock()
            mock_ovh_client.return_value = mock_client_instance

            sync = SyncHelloAsso(temp_config.name)
            sync.run()

            # Should complete without error
            assert mock_get.call_count == 2
        finally:
            os.unlink(temp_config.name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
