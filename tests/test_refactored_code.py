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
from src.clients.webhook_client import WebhookClient


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
    
    def test_to_webhook_payload(self):
        """Test conversion to webhook payload"""
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
        
        payload = sub.to_webhook_payload()
        
        assert payload["email"] == "test@example.com"
        assert payload["firstName"] == "John"
        assert payload["lastName"] == "DOE"  # Uppercase
        assert payload["cotisation"] == "test_label"
        assert payload["field1"] == "value1"
    
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


class TestWebhookClient:
    """Tests for WebhookClient"""
    
    @patch('src.clients.webhook_client.requests.post')
    def test_send_subscription_success(self, mock_post):
        """Test sending a subscription successfully"""
        from datetime import datetime
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        client = WebhookClient("https://webhook.test/endpoint")
        
        sub = UserSubscription(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            subscription_date=datetime(2024, 6, 15),
            cotisation="test",
            groupe="test"
        )
        
        result = client.send_subscription(sub)
        
        assert result is True
        mock_post.assert_called_once()


class TestSyncHelloAssoIntegration:
    """Integration tests for SyncHelloAsso"""
    
    @patch('src.clients.hello_asso_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    def test_initialization(self, mock_ovh_client, mock_post, config_file):
        """Test SyncHelloAsso initialization"""
        mock_response = Mock()
        mock_response.json = Mock(return_value={"access_token": "test_token"})
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        sync = SyncHelloAsso(config_file)
        
        assert sync.hello_asso_client is not None
        assert sync.ovh_client is not None
        assert sync.webhook_client is not None
    
    @patch('src.clients.webhook_client.requests.post')
    @patch('src.clients.ovh_client.ovh.Client')
    @patch('src.clients.hello_asso_client.requests')
    def test_run_method(self, mock_requests, mock_ovh, mock_webhook, config_file):
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
        
        # Mock webhook
        mock_webhook_response = Mock()
        mock_webhook_response.status_code = 200
        mock_webhook.return_value = mock_webhook_response
        
        sync = SyncHelloAsso(config_file)
        sync.run()
        
        # Verify workflow executed
        assert mock_requests.get.call_count == 2
        # Should have called webhook once for the processed item
        assert mock_webhook.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
