"""HelloAsso API client."""
import syslog
from typing import Dict, List, Optional
import requests
from src.models.user_subscription import UserSubscription


class HelloAssoClient:
    """Client for interacting with HelloAsso API."""
    
    def __init__(
        self,
        api_url: str,
        organization_name: str,
        client_id: str,
        client_secret: str,
    ):
        """
        Initialize HelloAsso client.
        
        Args:
            api_url: Base URL for HelloAsso API
            organization_name: Organization name in HelloAsso
            client_id: OAuth client ID
            client_secret: OAuth client secret
        """
        self.api_url = api_url
        self.organization_name = organization_name
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: Optional[str] = None
        self._headers: Optional[Dict[str, str]] = None
        
        # Authenticate on initialization
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with HelloAsso API and store token."""
        headers = {"content-type": "application/x-www-form-urlencoded"}
        
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        url = f"{self.api_url}/oauth2/token"
        
        try:
            response = requests.post(url, data=payload, headers=headers, timeout=10)
            response.raise_for_status()
            self._token = response.json()["access_token"]
            self._headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
            }
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to authenticate to HelloAsso: {e}",
            )
            raise
    
    def get_form_details(self, form_name: str) -> Dict:
        """
        Find form details using form name.
        
        Args:
            form_name: Name of the form to find
            
        Returns:
            Form details dictionary with formType and formSlug
        """
        payload = {"pageSize": "100"}
        
        url = f"{self.api_url}/v5/organizations/{self.organization_name}/forms"
        
        try:
            response = requests.get(
                url,
                params=payload,
                headers=self._headers,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()["data"]
            
            for item in data:
                if item["title"] == form_name:
                    return item
            
            return {}
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to get form details for '{form_name}': {e}",
            )
            raise
    
    def get_form_items(self, form_type: str, form_slug: str) -> List[Dict]:
        """
        Retrieve all items from a form with pagination.
        
        Args:
            form_type: Type of the form (e.g., 'Membership', 'Event')
            form_slug: Unique slug identifier for the form
            
        Returns:
            List of all form items
        """
        all_items = []
        current_page = 1
        total_pages = 1
        
        while current_page <= total_pages:
            payload = {
                "pageIndex": current_page,
                "pageSize": "100",
                "withDetails": True,
            }
            
            url = (
                f"{self.api_url}/v5/organizations/{self.organization_name}/"
                f"forms/{form_type}/{form_slug}/items"
            )
            
            try:
                response = requests.get(
                    url,
                    params=payload,
                    headers=self._headers,
                    timeout=10,
                )
                response.raise_for_status()
                resp_json = response.json()
                
                all_items.extend(resp_json["data"])
                total_pages = resp_json["pagination"]["totalPages"]
                current_page += 1
                
            except Exception as e:
                syslog.syslog(
                    syslog.LOG_ERR,
                    f"Failed to get form items (page {current_page}): {e}",
                )
                raise
        
        return all_items
    
    def parse_items_to_subscriptions(
        self,
        items: List[Dict],
        cotisation: str,
        groupe: str,
        default_fields: Optional[Dict[str, str]] = None,
        first_sub_field: Optional[str] = None,
        name_field: Optional[str] = None,
    ) -> List[UserSubscription]:
        """
        Parse HelloAsso items into UserSubscription objects.
        
        Args:
            items: Raw items from HelloAsso API
            cotisation: Cotisation label
            groupe: Group name
            default_fields: Default custom fields to apply
            first_sub_field: Field name for first subscription year
            name_field: Field name to uppercase
            
        Returns:
            List of UserSubscription objects (only processed items)
        """
        subscriptions = []
        
        for item in items:
            if item.get("state") == "Processed":
                try:
                    subscription = UserSubscription.from_hello_asso_item(
                        item=item,
                        cotisation=cotisation,
                        groupe=groupe,
                        default_fields=default_fields,
                        first_sub_field=first_sub_field,
                        name_field=name_field,
                    )
                    subscriptions.append(subscription)
                except Exception as e:
                    syslog.syslog(
                        syslog.LOG_WARNING,
                        f"Failed to parse item for {item.get('payer', {}).get('email', 'unknown')}: {e}",
                    )
                    continue
        
        return subscriptions
