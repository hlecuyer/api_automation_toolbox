"""Webhook client for sending data."""
import json
import sys
import syslog
from typing import Dict
import requests
from src.models.user_subscription import UserSubscription


class WebhookClient:
    """Client for sending data to webhooks (e.g., Zapier)."""
    
    def __init__(self, webhook_url: str):
        """
        Initialize webhook client.
        
        Args:
            webhook_url: URL of the webhook endpoint
        """
        self.webhook_url = webhook_url
        self.headers = {"content-type": "application/json"}
    
    def send_subscription(self, subscription: UserSubscription) -> bool:
        """
        Send a user subscription to the webhook.
        
        Args:
            subscription: UserSubscription object to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        payload = subscription.to_webhook_payload()
        
        return self.send_data(payload)
    
    def send_data(self, data: Dict) -> bool:
        """
        Send raw data to the webhook.
        
        Args:
            data: Dictionary to send as JSON
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            print("Sending new record to webhook")
            print(json.dumps(data, indent=2))
            
            response = requests.post(
                self.webhook_url,
                data=json.dumps(data),
                headers=self.headers,
                timeout=10,
            )
            
            print(f"Response: {response.status_code}")
            
            if response.status_code != 200:
                syslog.syslog(
                    syslog.LOG_ERR,
                    f"Webhook request failed with status code {response.status_code}",
                )
                return False
            
            return True
            
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to send data to webhook: {e}",
            )
            return False
