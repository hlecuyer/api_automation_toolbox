"""Client classes for external services."""
from src.clients.hello_asso_client import HelloAssoClient
from src.clients.ovh_client import OVHMailingClient
from src.clients.airtable_client import AirtableClient
from src.clients.ovh_email_client import OVHEmailClient

__all__ = [
    "HelloAssoClient",
    "OVHMailingClient",
    "AirtableClient",
    "OVHEmailClient",
]
