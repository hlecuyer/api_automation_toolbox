"""Simple tests for the refactored code structure"""

import json
import tempfile
from unittest.mock import Mock, patch
import pytest
import ovh

from src.hello_asso_sync import SyncHelloAsso
from src.models.user_subscription import UserSubscription
from src.clients.hello_asso_client import HelloAssoClient
from src.clients.ovh_client import OVHMailingClient


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
            },
            "airtable": {
                "api_key": "test_airtable_key",
                "base_id": "test_base_id"
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
            "airtable": {
                "table_name": "Annuaire"
            },
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


class TestUserSubscription:
    """Tests for UserSubscription model"""
    
    def test_user_subscription_creation(self):
        """Test creating a UserSubscription instance"""
        from datetime import datetime
        
        sub = UserSubscription(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            subscription_date=datetime(2024, 6, 15, 10, 30),
            cotisation="test_label",
            groupe="test_group"
        )
        
        assert sub.email == "test@example.com"
        assert sub.first_name == "John"
        assert sub.last_name == "Doe"
    
    def test_to_airtable_payload(self):
        """Test conversion to Airtable payload"""
        from datetime import datetime
        
        sub = UserSubscription(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            subscription_date=datetime(2024, 6, 15, 10, 30),
            cotisation="test_label",
            groupe="test_group",
            custom_fields={"field1": "value1"}
        )
        
        payload = sub.to_airtable_payload()
        
        # Check Airtable field names (with French naming convention)
        assert payload["E-mail"] == "test@example.com"
        assert payload["Prénom"] == "John"
        assert payload["Nom"] == "DOE"  # Uppercase
        assert payload["Cotisation LCDC"] == "test_label"
        assert payload["Groupe(s)"] == "test_group"
    
    def test_from_hello_asso_item(self):
        """Test creating UserSubscription from HelloAsso API item"""
        item = {
            "state": "Processed",
            "payer": {"email": "test@example.com"},
            "user": {"firstName": "John", "lastName": "Doe"},
            "order": {"date": "2024-06-15T10:30:00.000+02:00"},
            "customFields": [
                {"name": "field1", "answer": "value1"}
            ]
        }
        
        sub = UserSubscription.from_hello_asso_item(
            item=item,
            cotisation="test_label",
            groupe="test_group"
        )
        
        assert sub.email == "test@example.com"
        assert sub.first_name == "John"
        assert sub.last_name == "Doe"
        assert sub.custom_fields["field1"] == "value1"


class TestHelloAssoClient:
    """Tests for HelloAssoClient"""
    
    @patch('src.clients.hello_asso_client.requests.post')
    def test_client_initialization(self, mock_post):
        """Test HelloAssoClient initialization"""
        mock_response = Mock()
        mock_response.json.return_value = {"access_token": "test_token"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        client = HelloAssoClient(
            api_url="https://api.test.com",
            organization_name="test_org",
            client_id="test_id",
            client_secret="test_secret"
        )
        
        assert client._token == "test_token"
        assert "Bearer test_token" in client._headers["Authorization"]  # type: ignore


class TestOVHMailingClient:
    """Tests for OVHMailingClient"""
    
    @patch('src.clients.ovh_client.ovh.Client')
    def test_add_subscriber_success(self, mock_ovh_client):
        """Test adding a subscriber successfully"""
        mock_client_instance = Mock()
        mock_ovh_client.return_value = mock_client_instance
        
        client = OVHMailingClient(
            application_key="ak",
            application_secret="as",
            consumer_key="ck",
            domain="test.org",
            mailing_list_name="test_list"
        )
        
        result = client.add_subscriber("test@example.com")
        
        assert result is True
        mock_client_instance.post.assert_called_once()
    
    @patch('src.clients.ovh_client.ovh.Client')
    def test_add_subscriber_already_exists(self, mock_ovh_client):
        """Test adding a subscriber that already exists"""
        mock_client_instance = Mock()
        mock_client_instance.post.side_effect = ovh.exceptions.ResourceConflictError("Exists")
        mock_ovh_client.return_value = mock_client_instance
        
        client = OVHMailingClient(
            application_key="ak",
            application_secret="as",
            consumer_key="ck",
            domain="test.org",
            mailing_list_name="test_list"
        )
        
        result = client.add_subscriber("test@example.com")
        
        # Should return True even for existing subscribers
        assert result is True


class TestHelloAssoClientErrorHandling:
    """Tests for HelloAssoClient error handling"""
    
    @patch('src.clients.hello_asso_client.requests.post')
    def test_authentication_failure(self, mock_post):
        """Test authentication error handling"""
        mock_post.side_effect = Exception("Network error")
        
        with pytest.raises(Exception, match="Network error"):
            HelloAssoClient(
                api_url="https://api.helloasso.com",
                organization_name="test_org",
                client_id="test_id",
                client_secret="test_secret"
            )
    
    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.hello_asso_client.requests.get')
    def test_get_form_details_list_format(self, mock_get, mock_post):
        """Test handling of list response format"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.json.return_value = {"access_token": "test_token"}
        mock_auth_response.raise_for_status = Mock()
        mock_post.return_value = mock_auth_response
        
        client = HelloAssoClient(
            api_url="https://api.helloasso.com",
            organization_name="test_org",
            client_id="test_id",
            client_secret="test_secret"
        )
        
        # Mock list format (direct array)
        mock_form_response = Mock()
        mock_form_response.json.return_value = [
            {"title": "Test Form", "formSlug": "test-slug"},
            {"title": "Other Form", "formSlug": "other-slug"}
        ]
        mock_form_response.raise_for_status = Mock()
        mock_get.return_value = mock_form_response
        
        result = client.get_form_details("Test Form")
        
        # Should find form in list
        assert result["title"] == "Test Form"
        assert result["formSlug"] == "test-slug"
    
    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.hello_asso_client.requests.get')
    def test_get_form_details_with_data_key(self, mock_get, mock_post):
        """Test handling of response with 'data' key"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.json.return_value = {"access_token": "test_token"}
        mock_auth_response.raise_for_status = Mock()
        mock_post.return_value = mock_auth_response
        
        client = HelloAssoClient(
            api_url="https://api.helloasso.com",
            organization_name="test_org",
            client_id="test_id",
            client_secret="test_secret"
        )
        
        # Mock response with 'data' key (common format)
        mock_form_response = Mock()
        mock_form_response.json.return_value = {
            "data": [
                {"title": "Test Form", "formSlug": "test-slug"},
                {"title": "Other Form", "formSlug": "other-slug"}
            ]
        }
        mock_form_response.raise_for_status = Mock()
        mock_get.return_value = mock_form_response
        
        result = client.get_form_details("Test Form")
        
        # Should find form in data array
        assert result["title"] == "Test Form"
        assert result["formSlug"] == "test-slug"
    
    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.hello_asso_client.requests.get')
    def test_get_form_details_form_not_found(self, mock_get, mock_post):
        """Test when requested form is not in the list"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.json.return_value = {"access_token": "test_token"}
        mock_auth_response.raise_for_status = Mock()
        mock_post.return_value = mock_auth_response
        
        client = HelloAssoClient(
            api_url="https://api.helloasso.com",
            organization_name="test_org",
            client_id="test_id",
            client_secret="test_secret"
        )
        
        # Mock response with different forms
        mock_form_response = Mock()
        mock_form_response.json.return_value = {
            "data": [
                {"title": "Other Form", "formSlug": "other"},
                {"title": "Another Form", "formSlug": "another"}
            ]
        }
        mock_form_response.raise_for_status = Mock()
        mock_get.return_value = mock_form_response
        
        result = client.get_form_details("Missing Form")
        
        # Should return empty dict when form not found
        assert result == {}
    
    @patch('src.clients.hello_asso_client.requests.post')
    def test_parse_items_parsing_error(self, mock_post):
        """Test handling of item parsing errors"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.json.return_value = {"access_token": "test_token"}
        mock_auth_response.raise_for_status = Mock()
        mock_post.return_value = mock_auth_response
        
        client = HelloAssoClient(
            api_url="https://api.helloasso.com",
            organization_name="test_org",
            client_id="test_id",
            client_secret="test_secret"
        )
        
        # Mock items with one malformed and one valid
        items = [
            {
                "state": "Processed",
                # Missing required fields - will cause parsing error
                "payer": {},
                "order": {}
            },
            {
                "state": "Processed",
                "payer": {"email": "valid@example.com"},
                "user": {"firstName": "John", "lastName": "Doe"},
                "order": {"date": "2024-06-15T10:30:00"},
                "customFields": []
            }
        ]
        
        subscriptions = client.parse_items_to_subscriptions(
            items=items,
            cotisation="test_label",
            groupe="test_group"
        )
        
        # Should skip malformed item and return only valid one
        assert len(subscriptions) == 1
        assert subscriptions[0].email == "valid@example.com"


class TestConfigLoaderValidation:
    """Tests for config_loader validation"""
    
    def test_load_config_missing_credentials(self, tmp_path):
        """Test load_config fails with missing credentials"""
        from src.config_loader import load_config
        import os
        
        # Create config file without credentials
        config = {
            "credentials": {
                "helloAsso": {
                    "id": "test_id"
                    # Missing 'secret'
                },
                "ovh": {"endpoint": "ovh-eu", "ak": "ak", "as": "as", "ck": "ck"},
                "airtable": {"api_key": "key", "base_id": "base"}
            },
            "conf": {
                "helloAsso": {
                    "organization_name": "test",
                    "form_name": "Test Form"
                },
                "airtable": {"table_name": "Table"},
                "ovh": {"mailing_list": {"name": "list", "domain": "test.org"}}
            }
        }
        config_path = tmp_path / "test_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)
        
        # Set minimal env vars (missing secret)
        os.environ["HELLOASSO_CLIENT_ID"] = "test_id"
        os.environ.pop("HELLOASSO_CLIENT_SECRET", None)
        
        with pytest.raises(ValueError, match="credentials.helloAsso.secret"):
            load_config(str(config_path))
    
    def test_load_config_missing_conf_fields(self, tmp_path):
        """Test load_config fails with missing conf fields"""
        from src.config_loader import load_config
        import os
        
        # Create config file missing form_name
        config = {
            "credentials": {
                "helloAsso": {"id": "test_id", "secret": "secret"},
                "ovh": {"endpoint": "ovh-eu", "ak": "ak", "as": "as", "ck": "ck"},
                "airtable": {"api_key": "key", "base_id": "base"}
            },
            "conf": {
                "helloAsso": {
                    "organization_name": "test"
                    # Missing 'form_name'
                },
                "airtable": {"table_name": "Table"},
                "ovh": {"mailing_list": {"name": "list", "domain": "test.org"}}
            }
        }
        config_path = tmp_path / "test_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)
        
        # Set all env vars
        os.environ["HELLOASSO_CLIENT_ID"] = "test_id"
        os.environ["HELLOASSO_CLIENT_SECRET"] = "secret"
        
        with pytest.raises(ValueError, match="conf.helloAsso.form_name"):
            load_config(str(config_path))
    
    def test_load_config_success(self, tmp_path):
        """Test load_config succeeds with all required fields"""
        from src.config_loader import load_config
        import os
        
        # Create valid config file
        config = {
            "credentials": {
                "helloAsso": {"id": "test_id", "secret": "secret"},
                "ovh": {"endpoint": "ovh-eu", "ak": "ak", "as": "as", "ck": "ck"},
                "airtable": {"api_key": "key", "base_id": "base"}
            },
            "conf": {
                "helloAsso": {
                    "organization_name": "test",
                    "form_name": "Test Form"
                },
                "airtable": {"table_name": "Table"},
                "ovh": {"mailing_list": {"name": "list", "domain": "test.org"}}
            }
        }
        config_path = tmp_path / "test_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f)
        
        # Set all env vars
        os.environ["HELLOASSO_CLIENT_ID"] = "test_id"
        os.environ["HELLOASSO_CLIENT_SECRET"] = "secret"
        
        # Should not raise exception
        result = load_config(str(config_path))
        assert result["credentials"]["helloAsso"]["secret"] == "secret"


class TestSyncHelloAssoIntegration:
    """Integration tests for SyncHelloAsso"""
    
    @patch('src.clients.airtable_client.requests.get')
    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_initialization(self, mock_ovh_client, mock_post, mock_airtable_get, config_file):
        """Test SyncHelloAsso initialization"""
        mock_response = Mock()
        mock_response.json = Mock(return_value={"access_token": "test_token"})
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        sync = SyncHelloAsso(config_file)
        
        assert sync.hello_asso_client is not None
        assert sync.ovh_mailing_client is not None
        assert sync.airtable_client is not None
    
    @patch('src.clients.airtable_client.requests.post')
    @patch('src.clients.airtable_client.requests.get')
    @patch('src.clients.ovh_client.ovh.Client')
    @patch('src.clients.hello_asso_client.requests')
    def test_run_method(self, mock_requests, mock_ovh, mock_airtable_get, mock_airtable_post, config_file):
        """Test the run method executes without errors"""
        # Mock authentication response
        mock_auth_response = Mock()
        mock_auth_response.json.return_value = {"access_token": "test_token"}
        mock_auth_response.raise_for_status = Mock()
        
        # Mock form details response
        mock_form_response = Mock()
        mock_form_response.json.return_value = {
            "data": [{
                "title": "Test Form",
                "formType": "Membership",
                "formSlug": "test-slug"
            }]
        }
        mock_form_response.raise_for_status = Mock()
        
        # Mock form items response 
        mock_items_response = Mock()
        mock_items_response.json.return_value = {
            "data": [{
                "state": "Processed",
                "payer": {"email": "test@example.com"},
                "user": {"firstName": "John", "lastName": "Doe"},
                "order": {"date": "2024-06-15T10:30:00"},
                "customFields": []
            }],
            "pagination": {"totalPages": 1, "currentPage": 1}
        }
        mock_items_response.raise_for_status = Mock()
        
        # Setup mock_requests
        mock_requests.post.return_value = mock_auth_response
        mock_requests.get.side_effect = [mock_form_response, mock_items_response]
        
        # Mock Airtable: record doesn't exist, so create
        mock_airtable_get_resp = Mock()
        mock_airtable_get_resp.json.return_value = {"records": []}
        mock_airtable_get_resp.raise_for_status = Mock()
        mock_airtable_get.return_value = mock_airtable_get_resp
        
        mock_airtable_post_resp = Mock()
        mock_airtable_post_resp.json.return_value = {"id": "rec123", "fields": {}}
        mock_airtable_post_resp.raise_for_status = Mock()
        mock_airtable_post.return_value = mock_airtable_post_resp
        
        sync = SyncHelloAsso(config_file)
        sync.run()
        
        # Verify workflow executed
        assert mock_requests.get.call_count == 2
        # Should have called Airtable for the processed item
        assert mock_airtable_post.call_count >= 1
    
    @patch('src.hello_asso_sync.OVHEmailClient')
    @patch('src.clients.airtable_client.requests.post')
    @patch('src.clients.airtable_client.requests.get')
    @patch('src.clients.ovh_client.ovh.Client')
    @patch('src.clients.hello_asso_client.requests')
    def test_run_with_confirmation_email(self, mock_requests, mock_ovh_mailing, mock_airtable_get, mock_airtable_post, mock_ovh_email_class, tmp_path):
        """Test run method with confirmation email enabled"""
        # Create config with email confirmation enabled
        config_with_email = {
            "credentials": {
                "helloAsso": {"id": "test_id", "secret": "test_secret"},
                "ovh": {"endpoint": "ovh-eu", "ak": "test_ak", "as": "test_as", "ck": "test_ck"},
                "airtable": {"api_key": "test_airtable_key", "base_id": "test_base_id"}
            },
            "conf": {
                "helloAsso": {
                    "api_url": "https://api.helloasso.com",
                    "organization_name": "test_org",
                    "form_name": "Test Form",
                    "subscription_after": "2024-01-01T00:00:00",
                    "first_sub_field": "first_sub",
                    "name_field": "name",
                    "default": {"default_field": "default_value"}
                },
                "cotisation_label": "test_label",
                "groupe": "test_group",
                "airtable": {"table_name": "Annuaire"},
                "ovh": {
                    "mailing_list": {"name": "test_list", "domain": "test.org"},
                    "email": {
                        "send_confirmation": True,
                        "from": "noreply@test.org",
                        "subject": "Welcome!",
                        "body_html": "<p>Welcome!</p>",
                        "body_text": "Welcome!"
                    }
                }
            }
        }
        
        config_path = tmp_path / "test_config_email.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_with_email, f)
        
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.json.return_value = {"access_token": "test_token"}
        mock_auth_response.raise_for_status = Mock()
        
        # Mock form details
        mock_form_response = Mock()
        mock_form_response.json.return_value = {
            "data": [{"title": "Test Form", "formType": "Membership", "formSlug": "test-slug"}]
        }
        mock_form_response.raise_for_status = Mock()
        
        # Mock form items
        mock_items_response = Mock()
        mock_items_response.json.return_value = {
            "data": [{
                "state": "Processed",
                "payer": {"email": "test@example.com"},
                "user": {"firstName": "John", "lastName": "Doe"},
                "order": {"date": "2025-06-15T10:30:00"},
                "customFields": []
            }],
            "pagination": {"totalPages": 1, "currentPage": 1}
        }
        mock_items_response.raise_for_status = Mock()
        
        mock_requests.post.return_value = mock_auth_response
        mock_requests.get.side_effect = [mock_form_response, mock_items_response]
        
        # Mock Airtable
        mock_airtable_get_resp = Mock()
        mock_airtable_get_resp.json.return_value = {"records": []}
        mock_airtable_get_resp.raise_for_status = Mock()
        mock_airtable_get_resp.status_code = 200
        mock_airtable_get.return_value = mock_airtable_get_resp
        
        mock_airtable_post_resp = Mock()
        mock_airtable_post_resp.json.return_value = {"id": "rec123", "fields": {}}
        mock_airtable_post_resp.raise_for_status = Mock()
        mock_airtable_post_resp.status_code = 200
        mock_airtable_post.return_value = mock_airtable_post_resp
        
        # Mock OVH email client
        mock_email_instance = Mock()
        mock_email_instance.send_email.return_value = True
        mock_ovh_email_class.return_value = mock_email_instance
        
        sync = SyncHelloAsso(str(config_path))
        sync.run()
        
        # Verify email was sent
        assert mock_email_instance.send_email.called
    
    @patch('src.clients.airtable_client.requests.post')
    @patch('src.clients.airtable_client.requests.get')
    @patch('src.clients.ovh_client.ovh.Client')
    @patch('src.clients.hello_asso_client.requests')
    def test_run_airtable_error_handling(self, mock_requests, mock_ovh, mock_airtable_get, mock_airtable_post, config_file):
        """Test run method with Airtable error"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.json.return_value = {"access_token": "test_token"}
        mock_auth_response.raise_for_status = Mock()
        
        # Mock form details
        mock_form_response = Mock()
        mock_form_response.json.return_value = {
            "data": [{"title": "Test Form", "formType": "Membership", "formSlug": "test-slug"}]
        }
        mock_form_response.raise_for_status = Mock()
        
        # Mock form items
        mock_items_response = Mock()
        mock_items_response.json.return_value = {
            "data": [{
                "state": "Processed",
                "payer": {"email": "test@example.com"},
                "user": {"firstName": "John", "lastName": "Doe"},
                "order": {"date": "2025-06-15T10:30:00"},
                "customFields": []
            }],
            "pagination": {"totalPages": 1, "currentPage": 1}
        }
        mock_items_response.raise_for_status = Mock()
        
        mock_requests.post.return_value = mock_auth_response
        mock_requests.get.side_effect = [mock_form_response, mock_items_response]
        
        # Mock Airtable to fail
        mock_airtable_get_resp = Mock()
        mock_airtable_get_resp.json.return_value = {"records": []}
        mock_airtable_get_resp.raise_for_status = Mock()
        mock_airtable_get_resp.status_code = 500  # Error
        mock_airtable_get.return_value = mock_airtable_get_resp
        
        sync = SyncHelloAsso(config_file)
        sync.run()
        
        # Should continue despite error
        assert mock_requests.get.call_count == 2
    
    @patch('src.clients.airtable_client.requests.get')
    @patch('src.clients.ovh_client.ovh.Client')
    @patch('src.clients.hello_asso_client.requests.post')
    def test_update_date_conf(self, mock_post, mock_ovh, mock_airtable_get, config_file):
        """Test update_date_conf method"""
        # Mock authentication
        mock_auth_response = Mock()
        mock_auth_response.json.return_value = {"access_token": "test_token"}
        mock_auth_response.raise_for_status = Mock()
        mock_post.return_value = mock_auth_response
        
        sync = SyncHelloAsso(config_file)
        
        # Update date
        sync.update_date_conf()
        
        # Read config and verify date was updated
        with open(config_file, "r", encoding="utf-8") as f:
            updated_config = json.load(f)
        
        # Should have updated subscription_after
        assert "subscription_after" in updated_config["conf"]["helloAsso"]
        # Verify it's a valid date string
        from datetime import datetime
        datetime.strptime(
            updated_config["conf"]["helloAsso"]["subscription_after"],
            "%Y-%m-%dT%H:%M:%S"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
