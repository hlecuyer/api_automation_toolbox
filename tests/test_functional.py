"""Functional tests for API integrations with real connections"""

import json
import os
from datetime import datetime
from unittest.mock import patch, Mock
import pytest
from dotenv import load_dotenv
import requests

from src.clients.hello_asso_client import HelloAssoClient
from src.clients.airtable_client import AirtableClient
from src.clients.ovh_email_client import OVHEmailClient
from src.clients.ovh_client import OVHMailingClient

# Load environment variables
load_dotenv()


@pytest.fixture
def hello_asso_credentials():
    """Get HelloAsso credentials from environment"""
    return {
        'client_id': os.getenv('HELLOASSO_CLIENT_ID'),
        'client_secret': os.getenv('HELLOASSO_CLIENT_SECRET'),
        'api_url': os.getenv('HELLOASSO_API_URL', 'https://api.helloasso.com'),
        'organization': 'la-coop-des-communs'
    }


@pytest.fixture
def airtable_credentials():
    """Get Airtable credentials from environment"""
    return {
        'api_key': os.getenv('AIRTABLE_API_KEY'),
        'base_id': os.getenv('AIRTABLE_BASE_ID'),
        'table_name': 'Annuaire'
    }


@pytest.fixture
def ovh_credentials():
    """Get OVH credentials from environment"""
    return {
        'endpoint': os.getenv('OVH_ENDPOINT', 'ovh-eu'),
        'application_key': os.getenv('OVH_APP_KEY'),
        'application_secret': os.getenv('OVH_APP_SECRET'),
        'consumer_key': os.getenv('OVH_CONSUMER_KEY'),
        'smtp_host': os.getenv('SMTP_HOST'),
        'smtp_port': int(os.getenv('SMTP_PORT', '587')),
        'smtp_user': os.getenv('SMTP_USER'),
        'smtp_password': os.getenv('SMTP_PASSWORD')
    }


class TestHelloAssoConnection:
    """Test HelloAsso API connection"""

    def test_authentication(self, hello_asso_credentials):
        """Test HelloAsso authentication"""
        client = HelloAssoClient(
            client_id=hello_asso_credentials['client_id'],
            client_secret=hello_asso_credentials['client_secret'],
            api_url=hello_asso_credentials['api_url'],
            organization_name=hello_asso_credentials['organization']
        )
        
        assert client._token is not None, "Authentication failed - no token"
        assert len(client._token) > 0, "Token is empty"
        assert 'Authorization' in client._headers
        print(f"✓ HelloAsso authentication successful")
        print(f"✓ Token length: {len(client._token)}")

    def test_get_forms(self, hello_asso_credentials):
        """Test retrieving forms from HelloAsso"""
        client = HelloAssoClient(
            client_id=hello_asso_credentials['client_id'],
            client_secret=hello_asso_credentials['client_secret'],
            api_url=hello_asso_credentials['api_url'],
            organization_name=hello_asso_credentials['organization']
        )
        
        # Get form details
        form_details = client.get_form_details('Adhésion année 2026')
        
        assert form_details is not None, "No form details returned"
        assert 'formSlug' in form_details, "Form slug missing"
        assert 'formType' in form_details, "Form type missing"
        
        print(f"✓ Found form: {form_details['title']}")
        print(f"✓ Form slug: {form_details['formSlug']}")
        print(f"✓ Form type: {form_details['formType']}")

    def test_get_real_users(self, hello_asso_credentials):
        """Test retrieving real user data from HelloAsso"""
        client = HelloAssoClient(
            client_id=hello_asso_credentials['client_id'],
            client_secret=hello_asso_credentials['client_secret'],
            api_url=hello_asso_credentials['api_url'],
            organization_name=hello_asso_credentials['organization']
        )
        
        # Get form details
        form_details = client.get_form_details('Adhésion année 2026')
        if not form_details or 'formSlug' not in form_details:
            pytest.skip("Form 'Adhésion année 2026' not found")
        
        # Get form items
        items = client.get_form_items(
            form_details['formType'],
            form_details['formSlug']
        )
        
        assert isinstance(items, list), "Items should be a list"
        print(f"✓ Retrieved {len(items)} items from HelloAsso")
        
        if items:
            processed = [item for item in items if item.get('state') == 'Processed']
            print(f"✓ Processed items: {len(processed)}")
            if processed:
                sample = processed[0]
                print(f"✓ Sample email: {sample.get('payer', {}).get('email', 'N/A')}")


class TestAirtableConnection:
    """Test Airtable API connection"""

    def test_list_records(self, airtable_credentials):
        """Test listing records from Airtable"""
        client = AirtableClient(
            api_key=airtable_credentials['api_key'],
            base_id=airtable_credentials['base_id'],
            table_name=airtable_credentials['table_name']
        )
        
        records = client.list_records(max_records=5)
        
        assert isinstance(records, list), "Records should be a list"
        print(f"✓ Retrieved {len(records)} records from Airtable")
        
        if records:
            print(f"✓ Sample record ID: {records[0].get('id', 'N/A')}")

    def test_create_and_delete_user(self, airtable_credentials):
        """Test creating and deleting a test user in Airtable"""
        # Skip if BASE_ID is not a valid Airtable Base ID (must start with 'app')
        if not airtable_credentials['base_id'].startswith('app'):
            pytest.skip(f"Invalid Airtable base_id: {airtable_credentials['base_id']} (should start with 'app')")
        
        client = AirtableClient(
            api_key=airtable_credentials['api_key'],
            base_id=airtable_credentials['base_id'],
            table_name=airtable_credentials['table_name']
        )
        
        # Create test user
        test_email = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}@test-automation.local"
        test_fields = {
            'E-mail': test_email,
            'Prénom': 'Test',
            'Nom': 'AUTOMATION'
            # On n'ajoute pas Statut car c'est un champ select avec options prédéfinies
        }
        
        print(f"Creating test user: {test_email}")
        created_record = client.create_record(test_fields)
        
        assert created_record is not None, "Failed to create record"
        assert 'id' in created_record, "No ID in created record"
        record_id = created_record['id']
        
        print(f"✓ Created test user with ID: {record_id}")
        
        try:
            # Verify the record exists
            found_record = client.find_record_by_email(test_email)
            assert found_record is not None, "Created record not found"
            assert found_record['id'] == record_id, "Record ID mismatch"
            print(f"✓ Verified test user exists")
            
        finally:
            # Cleanup: Delete the test record
            url = f"https://api.airtable.com/v0/{airtable_credentials['base_id']}/{client.table_name_encoded}/{record_id}"
            headers = {
                'Authorization': f"Bearer {airtable_credentials['api_key']}",
                'Content-Type': 'application/json'
            }
            response = requests.delete(url, headers=headers, timeout=10)
            response.raise_for_status()
            print(f"✓ Deleted test user {record_id}")

    def test_update_and_rollback_user(self, airtable_credentials):
        """Test updating a user and rolling back to original state"""
        # Skip if BASE_ID is not valid
        if not airtable_credentials['base_id'].startswith('app'):
            pytest.skip(f"Invalid Airtable base_id: {airtable_credentials['base_id']} (should start with 'app')")
        
        client = AirtableClient(
            api_key=airtable_credentials['api_key'],
            base_id=airtable_credentials['base_id'],
            table_name=airtable_credentials['table_name']
        )
        
        # Find an existing record to update, or create one if needed
        records = client.list_records(max_records=1)
        
        created_for_test = False
        if not records:
            # Create a test record to update
            print("⚠️  No existing records - creating one for testing")
            test_email = f"test-update-{datetime.now().strftime('%Y%m%d%H%M%S')}@test-automation.local"
            test_fields = {
                'E-mail': test_email,
                'Prénom': 'TestUpdate',
                'Nom': 'ORIGINAL'
            }
            created_record = client.create_record(test_fields)
            if not created_record:
                pytest.skip("Failed to create test record for update")
            
            record = created_record
            created_for_test = True
            print(f"✓ Created test record: {record['id']}")
        else:
            record = records[0]
        
        record_id = record['id']
        original_fields = record.get('fields', {}).copy()
        
        print(f"Testing update on record: {record_id}")
        print(f"Original Nom: {original_fields.get('Nom', 'N/A')}")
        
        # Update the record
        test_update = {
            'Nom': 'TEST_UPDATE_' + datetime.now().strftime('%H%M%S')
        }
        
        updated_record = client.update_record(record_id, test_update)
        assert updated_record is not None, "Update failed"
        print(f"✓ Updated Nom to: {test_update['Nom']}")
        
        try:
            # Verify the update
            url = f"https://api.airtable.com/v0/{airtable_credentials['base_id']}/{client.table_name_encoded}/{record_id}"
            headers = {
                'Authorization': f"Bearer {airtable_credentials['api_key']}"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            current_fields = response.json()['fields']
            assert current_fields.get('Nom') == test_update['Nom'], "Update not applied"
            print(f"✓ Verified update was applied")
            
        finally:
            if created_for_test:
                # Delete the test record we created
                url = f"https://api.airtable.com/v0/{airtable_credentials['base_id']}/{client.table_name_encoded}/{record_id}"
                headers = {
                    'Authorization': f"Bearer {airtable_credentials['api_key']}",
                    'Content-Type': 'application/json'
                }
                response = requests.delete(url, headers=headers, timeout=10)
                response.raise_for_status()
                print(f"✓ Deleted test record {record_id}")
            else:
                # Rollback: Restore original value for existing record
                rollback_fields = {'Nom': original_fields.get('Nom', '')}
                client.update_record(record_id, rollback_fields)
                print(f"✓ Rolled back to original Nom: {original_fields.get('Nom', 'N/A')}")



class TestOVHEmailConnection:
    """Test OVH Email API connection"""

    def test_send_test_email(self, ovh_credentials):
        """Test sending an email to support@dsi.coop (not to real users)"""
        with patch('src.clients.ovh_client.ovh.Client'):
            client = OVHEmailClient(
                endpoint=ovh_credentials['endpoint'],
                application_key=ovh_credentials['application_key'],
                application_secret=ovh_credentials['application_secret'],
                consumer_key=ovh_credentials['consumer_key'],
                smtp_host=ovh_credentials['smtp_host'],
                smtp_port=ovh_credentials['smtp_port'],
                smtp_user=ovh_credentials['smtp_user'],
                smtp_password=ovh_credentials['smtp_password']
            )
        
        # Send test email to support (not real users)
        test_email = {
            'sender': 'contact@coopdescommuns.org',
            'to': ['support@dsi.coop'],
            'subject': f'Test automatique - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            'body_text': 'Ceci est un test automatique du système. Ce message peut être ignoré.',
            'body_html': '<p>Ceci est un <strong>test automatique</strong> du système.</p><p>Ce message peut être ignoré.</p>'
        }
        
        # Use dry_run to avoid actually sending
        result = client.send_email(
            sender=test_email['sender'],
            to=test_email['to'],
            subject=test_email['subject'],
            body_text=test_email['body_text'],
            body_html=test_email['body_html'],
            dry_run=True  # DRY RUN - no actual email sent
        )
        
        assert result is True, "Email send (dry-run) failed"
        print(f"✓ Email test passed (DRY RUN - not actually sent)")
        print(f"✓ Would send to: {', '.join(test_email['to'])}")
        print(f"✓ Subject: {test_email['subject']}")

    def test_smtp_connection(self, ovh_credentials):
        """Test SMTP connection without sending email"""
        import smtplib
        
        print(f"\n🔌 Test de connexion SMTP...")
        print(f"   Serveur: {ovh_credentials['smtp_host']}:{ovh_credentials['smtp_port']}")
        print(f"   Utilisateur: {ovh_credentials['smtp_user']}")
        
        try:
            # Test connection
            with smtplib.SMTP(ovh_credentials['smtp_host'], ovh_credentials['smtp_port']) as server:
                server.starttls()
                print(f"✓ Connexion STARTTLS établie")
                
                # Test authentication
                server.login(ovh_credentials['smtp_user'], ovh_credentials['smtp_password'])
                print(f"✓ Authentification réussie")
                
                # Don't send anything - just verify connection works
                print(f"✓ Serveur SMTP prêt à envoyer des emails")
                
            print(f"\n✅ Configuration SMTP valide!")
            assert True
            
        except smtplib.SMTPAuthenticationError as e:
            print(f"\n❌ Erreur d'authentification: {e}")
            print(f"   Vérifiez SMTP_USER et SMTP_PASSWORD dans .env")
            assert False, f"Authentication failed: {e}"
            
        except Exception as e:
            print(f"\n❌ Erreur de connexion: {e}")
            assert False, f"Connection failed: {e}"

    @pytest.mark.manual
    def test_send_real_email(self, ovh_credentials):
        """Test sending a REAL email via SMTP
        
        Run with: pytest tests/test_functional.py::TestOVHEmailConnection::test_send_real_email -v -s -m manual
        """
        client = OVHEmailClient(
            endpoint=ovh_credentials['endpoint'],
            application_key=ovh_credentials['application_key'],
            application_secret=ovh_credentials['application_secret'],
            consumer_key=ovh_credentials['consumer_key'],
            smtp_host=ovh_credentials['smtp_host'],
            smtp_port=ovh_credentials['smtp_port'],
            smtp_user=ovh_credentials['smtp_user'],
            smtp_password=ovh_credentials['smtp_password']
        )
        
        # Send REAL email to support
        test_email = {
            'sender': ovh_credentials['smtp_user'],  # Use SMTP user as sender
            'to': ['support@dsi.coop'],
            'subject': f'Test RÉEL SMTP - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
            'body_text': 'Ceci est un test RÉEL du système d\'envoi d\'emails via SMTP OVH.\n\nSi vous recevez ce message, le système fonctionne correctement.',
            'body_html': '<p>Ceci est un test <strong>RÉEL</strong> du système d\'envoi d\'emails via <strong>SMTP OVH</strong>.</p><p>Si vous recevez ce message, le système fonctionne correctement.</p>'
        }
        
        print(f"\n📧 Envoi d'email via SMTP...")
        print(f"   Serveur: {ovh_credentials['smtp_host']}:{ovh_credentials['smtp_port']}")
        print(f"   De: {test_email['sender']}")
        print(f"   À: {', '.join(test_email['to'])}")
        print(f"   Sujet: {test_email['subject']}")
        
        # NO DRY RUN - actually send the email via SMTP
        result = client.send_email(
            sender=test_email['sender'],
            to=test_email['to'],
            subject=test_email['subject'],
            body_text=test_email['body_text'],
            body_html=test_email['body_html'],
            dry_run=False  # REAL SEND via SMTP
        )
        
        assert result is True, "Email send via SMTP failed"
        print(f"\n✅ Email envoyé avec succès via SMTP!")
        print(f"✓ Destinataire: {', '.join(test_email['to'])}")
        print(f"✓ Vérifiez votre boîte mail à support@dsi.coop")


class TestOVHMailingListConnection:
    """Test OVH Mailing List API connection"""

    def test_connection(self, ovh_credentials):
        """Test OVH mailing list connection"""
        client = OVHMailingClient(
            endpoint=ovh_credentials['endpoint'],
            application_key=ovh_credentials['application_key'],
            application_secret=ovh_credentials['application_secret'],
            consumer_key=ovh_credentials['consumer_key'],
            domain='coopdescommuns.org',
            mailing_list_name='membres'
        )
        
        # Just verify the client initializes correctly
        assert client.client is not None, "OVH client not initialized"
        assert client.domain == 'coopdescommuns.org'
        assert client.mailing_list_name == 'membres'
        print(f"✓ OVH mailing list client initialized")
        print(f"✓ Domain: {client.domain}")
        print(f"✓ List: {client.mailing_list_name}")
