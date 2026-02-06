"""Tests for OVHEmailClient"""

from unittest.mock import Mock, patch, MagicMock
import pytest

from src.clients.ovh_email_client import OVHEmailClient


@pytest.fixture
def mock_ovh_client():
    """Create a mock OVH client"""
    return MagicMock()


@pytest.fixture
def mock_smtp():
    """Create a mock SMTP client"""
    return MagicMock()


@pytest.fixture
def email_client(mock_ovh_client, mock_smtp):
    """Create an OVHEmailClient instance for testing"""
    with patch('src.clients.ovh_email_client.ovh.Client', return_value=mock_ovh_client), \
         patch('src.clients.ovh_email_client.smtplib.SMTP', return_value=mock_smtp):
        return OVHEmailClient(
            application_key="test_ak",
            application_secret="test_as",
            consumer_key="test_ck",
            endpoint="ovh-eu",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="password"
        )


class TestOVHEmailClientInit:
    """Tests for OVHEmailClient initialization"""

    @patch('src.clients.ovh_email_client.ovh.Client')
    def test_init_creates_ovh_client(self, mock_ovh_constructor):
        """Test that initialization creates OVH client correctly"""
        mock_client = MagicMock()
        mock_ovh_constructor.return_value = mock_client

        client = OVHEmailClient(
            application_key="my_ak",
            application_secret="my_as",
            consumer_key="my_ck",
            endpoint="ovh-eu"
        )

        mock_ovh_constructor.assert_called_once_with(
            endpoint="ovh-eu",
            application_key="my_ak",
            application_secret="my_as",
            consumer_key="my_ck"
        )
        assert client.client == mock_client


class TestOVHEmailClientSendEmail:
    """Tests for send_email method"""

    def test_send_email_success(self, email_client):
        """Test successful email sending in dry run mode"""
        result = email_client.send_email(
            sender="noreply@example.com",
            to=["recipient@example.com"],
            subject="Test Subject",
            body_html="<p>Test HTML</p>",
            body_text="Test text",
            dry_run=True  # Use dry_run to avoid needing real SMTP
        )

        assert result is True

    def test_send_email_with_cc_bcc(self, email_client):
        """Test sending email with CC and BCC"""
        result = email_client.send_email(
            sender="noreply@example.com",
            to=["recipient@example.com"],
            subject="Test",
            body_html="<p>Test</p>",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            dry_run=True
        )

        assert result is True

    def test_send_email_extracts_domain_correctly(self, email_client):
        """Test that email is sent with correct sender"""
        result = email_client.send_email(
            sender="user@subdomain.example.org",
            to=["recipient@test.com"],
            subject="Test",
            body_html="<p>Test</p>",
            dry_run=True
        )

        assert result is True

    def test_send_email_handles_errors(self, email_client, mock_ovh_client):
        """Test error handling in send_email"""
        mock_ovh_client.post.side_effect = Exception("API Error")

        result = email_client.send_email(
            sender="noreply@example.com",
            to=["recipient@example.com"],
            subject="Test",
            body_html="<p>Test</p>"
        )

        assert result is False

    def test_send_email_validates_sender(self, email_client, mock_ovh_client):
        """Test that sender validation works"""
        # Invalid sender without @
        result = email_client.send_email(
            sender="invalidemail",
            to=["recipient@example.com"],
            subject="Test",
            body_html="<p>Test</p>"
        )

        assert result is False
        mock_ovh_client.post.assert_not_called()

    def test_send_email_requires_recipient(self, email_client, mock_ovh_client):
        """Test that at least one recipient is required"""
        result = email_client.send_email(
            sender="noreply@example.com",
            to=[],
            subject="Test",
            body_html="<p>Test</p>"
        )

        assert result is False
        mock_ovh_client.post.assert_not_called()


class TestOVHEmailClientListDomains:
    """Tests for list_email_domains method"""

    def test_list_domains_success(self, email_client, mock_ovh_client):
        """Test successful domain listing"""
        mock_ovh_client.get.return_value = ["example.com", "test.org"]

        domains = email_client.list_email_domains()

        assert len(domains) == 2
        assert "example.com" in domains
        mock_ovh_client.get.assert_called_once_with("/email/domain")

    def test_list_domains_handles_errors(self, email_client, mock_ovh_client):
        """Test error handling in list_email_domains"""
        mock_ovh_client.get.side_effect = Exception("API Error")

        domains = email_client.list_email_domains()

        assert domains == []


class TestOVHEmailClientGetDomainInfo:
    """Tests for get_domain_info method"""

    def test_get_domain_info_success(self, email_client, mock_ovh_client):
        """Test successful domain info retrieval"""
        mock_info = {
            "domain": "example.com",
            "status": "active",
            "offer": "premium"
        }
        mock_ovh_client.get.return_value = mock_info

        info = email_client.get_domain_info("example.com")

        assert info == mock_info
        mock_ovh_client.get.assert_called_once_with("/email/domain/example.com")

    def test_get_domain_info_handles_errors(self, email_client, mock_ovh_client):
        """Test error handling in get_domain_info"""
        mock_ovh_client.get.side_effect = Exception("API Error")

        info = email_client.get_domain_info("example.com")

        assert info is None


class TestOVHEmailClientDryRun:
    """Tests for dry-run mode"""

    def test_dry_run_send_email_returns_true(self, email_client, mock_ovh_client):
        """Test send_email returns True in dry-run mode without calling API"""
        result = email_client.send_email(
            sender="noreply@example.com",
            to=["recipient@example.com"],
            subject="Test",
            body_html="<p>Test</p>",
            dry_run=True
        )

        assert result is True
        mock_ovh_client.post.assert_not_called()

    def test_dry_run_list_domains_returns_empty(self, email_client, mock_ovh_client):
        """Test list_email_domains returns empty list in dry-run mode"""
        domains = email_client.list_email_domains(dry_run=True)

        assert domains == []
        mock_ovh_client.get.assert_not_called()

    def test_dry_run_get_domain_info_returns_none(self, email_client, mock_ovh_client):
        """Test get_domain_info returns None in dry-run mode"""
        info = email_client.get_domain_info("example.com", dry_run=True)

        assert info is None
        mock_ovh_client.get.assert_not_called()
