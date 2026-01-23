"""Functional tests for hello_asso_sync module with real API connections"""

import json
import os
from datetime import datetime
from unittest.mock import patch, Mock
import pytest
import requests

from src.hello_asso_sync import SyncHelloAsso


@pytest.fixture
def functional_config():
    """Load functional test configuration from environment or config file"""
    config_path = os.getenv('FUNCTIONAL_TEST_CONFIG', 'hello-asso-automation-conf-test.json')
    
    if not os.path.exists(config_path):
        pytest.skip(f"Functional test config not found: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


class TestFunctionalSync:
    """Functional tests with real HelloAsso API connection only"""

    @patch('src.clients.ovh_client.ovh.Client')
    def test_real_connection_to_helloasso(self, mock_ovh_client, functional_config, tmp_path):
        """Test real connection to HelloAsso API (no webhook/OVH calls)"""
        # Create temporary config file for test
        test_config_path = tmp_path / "test_config.json"
        with open(test_config_path, 'w', encoding='utf-8') as f:
            json.dump(functional_config, f)
        
        # Initialize with real HelloAsso credentials, mocked OVH
        sync = SyncHelloAsso(str(test_config_path))
        
        # Verify authentication worked
        assert sync.hello_asso_client._token is not None
        assert sync.hello_asso_client._headers is not None
        assert 'Authorization' in sync.hello_asso_client._headers
        assert sync.hello_asso_client._headers['Authorization'].startswith('Bearer ')
        
        # Get form details from real HelloAsso API
        form_name = sync.conf_global['conf']['helloAsso']['form_name']
        form_details = sync.hello_asso_client.get_form_details(form_name)
        
        assert form_details is not None
        assert 'formSlug' in form_details
        print(f"✓ Successfully connected to HelloAsso - Form: {form_name}")
        print(f"✓ Form type: {form_details.get('formType')}")
        print(f"✓ Form slug: {form_details.get('formSlug')}")

    @patch('src.clients.ovh_client.ovh.Client')
    def test_get_form_data_from_helloasso(self, mock_ovh_client, functional_config, tmp_path):
        """Test retrieving form data from HelloAsso (no webhook/OVH calls)"""
        test_config_path = tmp_path / "test_config.json"
        with open(test_config_path, 'w', encoding='utf-8') as f:
            json.dump(functional_config, f)
        
        sync = SyncHelloAsso(str(test_config_path))
        form_name = sync.conf_global['conf']['helloAsso']['form_name']
        form_details = sync.hello_asso_client.get_form_details(form_name)
        
        assert form_details, "Could not get form details"
        
        # Get recent data from HelloAsso
        form_data = sync.hello_asso_client.get_form_items(
            form_details['formType'],
            form_details['formSlug']
        )
        
        assert isinstance(form_data, list), "Form data should be a list"
        print(f"✓ Retrieved {len(form_data)} records from HelloAsso")
        
        # Display summary
        if form_data:
            processed_count = sum(1 for item in form_data if item.get('state') == 'Processed')
            print(f"✓ Processed records: {processed_count}")
            print(f"✓ Sample email: {form_data[0].get('payer', {}).get('email')}")

    @patch('src.clients.ovh_client.ovh.Client')
    def test_sync_workflow_without_sending(
        self,
        mock_ovh_client,
        functional_config,
        tmp_path
    ):
        """Test full sync workflow but mock webhook and OVH calls"""
        # Mock OVH client
        mock_ovh_instance = Mock()
        mock_ovh_client.return_value = mock_ovh_instance
        
        test_config_path = tmp_path / "test_config.json"
        with open(test_config_path, 'w', encoding='utf-8') as f:
            json.dump(functional_config, f)
        
        # Initialize with REAL HelloAsso authentication
        sync = SyncHelloAsso(str(test_config_path))
        
        # Now mock webhook AFTER initialization
        with patch('src.clients.webhook_client.requests.post') as mock_webhook:
            mock_webhook_response = Mock()
            mock_webhook_response.status_code = 200
            mock_webhook.return_value = mock_webhook_response
            
            # Simply run the workflow - webhooks and OVH are already mocked
            sync.run()
            
            print(f"✓ Workflow executed successfully (webhooks mocked)")
            print(f"✓ Would have sent {mock_webhook.call_count} webhook calls")
            print(f"✓ OVH mailing list calls: {mock_ovh_instance.post.call_count}")

    @patch('src.clients.ovh_client.ovh.Client')
    def test_inspect_webhook_and_ovh_data(
        self,
        mock_ovh_client,
        functional_config,
        tmp_path
    ):
        """Inspect and display exactly what would be sent to webhooks and OVH"""
        # Mock OVH client to capture calls
        mock_ovh_instance = Mock()
        mock_ovh_client.return_value = mock_ovh_instance
        
        test_config_path = tmp_path / "test_config.json"
        with open(test_config_path, 'w', encoding='utf-8') as f:
            json.dump(functional_config, f)
        
        # Initialize with REAL HelloAsso authentication
        sync = SyncHelloAsso(str(test_config_path))
        
        print("\n" + "="*100)
        print("📊 INSPECTION DES DONNÉES ENVOYÉES AUX SERVICES EXTERNES")
        print("="*100)
        
        # Mock webhook AFTER initialization
        with patch('src.clients.webhook_client.requests.post') as mock_webhook:
            mock_webhook_response = Mock()
            mock_webhook_response.status_code = 200
            mock_webhook.return_value = mock_webhook_response
            
            # Run the sync - webhooks and OVH are mocked
            # Run the sync - webhooks and OVH are mocked
            sync.run()
            
            # Display webhook calls
            print(f"\n🌐 WEBHOOKS ZAPIER/AIRTABLE: {mock_webhook.call_count} appel(s)")
            print("-" * 100)
            
            if mock_webhook.call_count > 0:
                for i, call in enumerate(mock_webhook.call_args_list, 1):
                    args, kwargs = call
                    webhook_url = args[0] if args else kwargs.get('url', 'N/A')
                    data = kwargs.get('data', 'N/A')
                    headers = kwargs.get('headers', {})
                    
                    print(f"\n  📤 Appel Webhook #{i}")
                    print(f"     URL: {webhook_url}")
                    print(f"     Headers: {headers}")
                    
                    if data != 'N/A':
                        try:
                            parsed_data = json.loads(data)
                            print(f"     Données JSON envoyées:")
                            for key, value in parsed_data.items():
                                # Truncate long values for readability
                                display_value = str(value)
                                if len(display_value) > 80:
                                    display_value = display_value[:77] + "..."
                                print(f"       • {key}: {display_value}")
                        except:
                            print(f"     Données brutes: {data[:200]}...")
                    
                    print()
            else:
                print("  ⚠️  Aucun appel webhook effectué (aucune donnée ne correspond aux critères)")
            
            # Display OVH calls
            print(f"\n📧 OVH MAILING LIST: {mock_ovh_instance.post.call_count} appel(s)")
            print("-" * 100)
            
            if mock_ovh_instance.post.call_count > 0:
                for i, call in enumerate(mock_ovh_instance.post.call_args_list, 1):
                    args, kwargs = call
                    
                    print(f"\n  📤 Appel OVH #{i}")
                    if args:
                        if len(args) > 0:
                            endpoint = args[0]
                            print(f"     Endpoint: {endpoint}")
                        if len(args) > 1:
                            data = args[1]
                            print(f"     Données envoyées:")
                            if isinstance(data, dict):
                                for key, value in data.items():
                                    print(f"       • {key}: {value}")
                            else:
                                print(f"       {data}")
                    if kwargs:
                        print(f"     Paramètres kwargs: {kwargs}")
                    print()
            else:
                print("  ⚠️  Aucun appel OVH effectué")
            
            print("\n" + "="*100)
            print(f"📊 RÉSUMÉ: {mock_webhook.call_count} webhook(s) + {mock_ovh_instance.post.call_count} OVH call(s)")
            print("="*100 + "\n")

    @patch('src.clients.ovh_client.ovh.Client')
    def test_dry_run_data_inspection(self, mock_ovh_client, functional_config, tmp_path):
        """Dry run: Get data from HelloAsso for inspection without sending anywhere"""
        test_config_path = tmp_path / "test_config.json"
        with open(test_config_path, 'w', encoding='utf-8') as f:
            json.dump(functional_config, f)
        
        sync = SyncHelloAsso(str(test_config_path))
        form_name = sync.conf_global['conf']['helloAsso']['form_name']
        form_details = sync.hello_asso_client.get_form_details(form_name)
        
        form_data = sync.hello_asso_client.get_form_items(
            form_details['formType'],
            form_details['formSlug']
        )
        
        # Save to file for manual inspection
        output_file = tmp_path / "helloasso_data_inspection.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(form_data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Data saved to: {output_file}")
        print(f"✓ Total records: {len(form_data)}")
        
        # Display summary
        if form_data:
            processed_count = sum(1 for item in form_data if item.get('state') == 'Processed')
            pending_count = len(form_data) - processed_count
            print(f"✓ Processed records: {processed_count}")
            print(f"✓ Pending/Other records: {pending_count}")
            
            # Show sample data
            if processed_count > 0:
                sample = next(item for item in form_data if item.get('state') == 'Processed')
                print(f"\n✓ Sample processed record:")
                print(f"  - Email: {sample.get('payer', {}).get('email')}")
                print(f"  - Name: {sample.get('user', {}).get('firstName')} {sample.get('user', {}).get('lastName')}")
                print(f"  - Date: {sample.get('order', {}).get('date')}")

    @patch('src.clients.ovh_client.ovh.Client')
    def test_authentication_token_valid(self, mock_ovh_client, functional_config, tmp_path):
        """Verify HelloAsso authentication token is valid and can make API calls"""
        test_config_path = tmp_path / "test_config.json"
        with open(test_config_path, 'w', encoding='utf-8') as f:
            json.dump(functional_config, f)
        
        sync = SyncHelloAsso(str(test_config_path))
        
        # Try to make a real API call to verify token
        api_url = sync.conf['helloAsso']['api_url']
        org_name = sync.conf['helloAsso']['organization_name']
        
        url = f"{api_url}/v5/organizations/{org_name}/forms"
        response = requests.get(
            url,
            params={"pageSize": "1"},
            headers=sync.hello_asso_client._headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"API call failed with status {response.status_code}"
        print(f"✓ Authentication token is valid")
        print(f"✓ API response status: {response.status_code}")


@pytest.mark.slow
class TestFullWorkflow:
    """Full workflow tests - marked as slow"""

    def test_complete_sync_workflow_mocked(
        self,
        functional_config,
        tmp_path
    ):
        """Test complete sync workflow with mocked external services"""
        # Setup test config
        test_config_path = tmp_path / "test_config.json"
        with open(test_config_path, 'w', encoding='utf-8') as f:
            json.dump(functional_config, f)
        
        # Initialize with REAL HelloAsso
        sync = SyncHelloAsso(str(test_config_path))
        
        # Mock webhook and OVH AFTER initialization to allow HelloAsso auth
        with patch('src.clients.webhook_client.requests.post') as mock_webhook, \
             patch('src.clients.ovh_client.ovh.Client') as mock_ovh_client:
            
            # Mock OVH client
            mock_ovh_instance = Mock()
            mock_ovh_client.return_value = mock_ovh_instance
            
            # Mock webhook
            mock_webhook_response = Mock()
            mock_webhook_response.status_code = 200
            mock_webhook.return_value = mock_webhook_response
            
            # Run full workflow
            sync.run()
            
            print("✓ Complete workflow executed successfully (external services mocked)")
            print(f"✓ Webhook calls made: {mock_webhook.call_count}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "not slow"])
