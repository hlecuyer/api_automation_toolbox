"""Configuration loader with support for environment variables and JSON files"""

import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def load_config(config_path):
    """
    Load configuration from JSON file and inject credentials from environment variables.
    
    Priority for credentials:
    1. Environment variables (highest priority) - for sensitive data
    2. JSON config file - for non-sensitive configuration
    
    Args:
        config_path: Path to JSON config file
        
    Returns:
        dict: Configuration dictionary with credentials from env vars
    """
    # Load configuration from JSON file
    if not config_path or not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Please provide a valid configuration file."
        )
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Override credentials from environment variables
    # This keeps sensitive data out of the JSON file
    if "credentials" not in config:
        config["credentials"] = {}
    
    # HelloAsso credentials from env vars
    if "helloAsso" not in config["credentials"]:
        config["credentials"]["helloAsso"] = {}
    
    if os.getenv("HELLOASSO_CLIENT_ID"):
        config["credentials"]["helloAsso"]["id"] = os.getenv("HELLOASSO_CLIENT_ID")
    if os.getenv("HELLOASSO_CLIENT_SECRET"):
        config["credentials"]["helloAsso"]["secret"] = os.getenv("HELLOASSO_CLIENT_SECRET")
    
    # OVH credentials from env vars
    if "ovh" not in config["credentials"]:
        config["credentials"]["ovh"] = {}
    
    if os.getenv("OVH_ENDPOINT"):
        config["credentials"]["ovh"]["endpoint"] = os.getenv("OVH_ENDPOINT")
    if os.getenv("OVH_APP_KEY"):
        config["credentials"]["ovh"]["ak"] = os.getenv("OVH_APP_KEY")
    if os.getenv("OVH_APP_SECRET"):
        config["credentials"]["ovh"]["as"] = os.getenv("OVH_APP_SECRET")
    if os.getenv("OVH_CONSUMER_KEY"):
        config["credentials"]["ovh"]["ck"] = os.getenv("OVH_CONSUMER_KEY")
    
    # Airtable credentials from env vars
    if "airtable" not in config["credentials"]:
        config["credentials"]["airtable"] = {}
    
    if os.getenv("AIRTABLE_API_KEY"):
        config["credentials"]["airtable"]["api_key"] = os.getenv("AIRTABLE_API_KEY")
    if os.getenv("AIRTABLE_BASE_ID"):
        config["credentials"]["airtable"]["base_id"] = os.getenv("AIRTABLE_BASE_ID")
    
    # SMTP credentials from env vars
    if "smtp" not in config["credentials"]:
        config["credentials"]["smtp"] = {}
    
    if os.getenv("SMTP_HOST"):
        config["credentials"]["smtp"]["host"] = os.getenv("SMTP_HOST")
    if os.getenv("SMTP_PORT"):
        config["credentials"]["smtp"]["port"] = int(os.getenv("SMTP_PORT"))
    if os.getenv("SMTP_USER"):
        config["credentials"]["smtp"]["user"] = os.getenv("SMTP_USER")
    if os.getenv("SMTP_PASSWORD"):
        config["credentials"]["smtp"]["password"] = os.getenv("SMTP_PASSWORD")
    
    # Validate required fields
    _validate_config(config)
    
    return config


def _validate_config(config):
    """Validate that required configuration fields are present"""
    required_fields = [
        ("credentials", "helloAsso", "id"),
        ("credentials", "helloAsso", "secret"),
        ("conf", "helloAsso", "organization_name"),
        ("conf", "helloAsso", "form_name"),
    ]
    
    missing_fields = []
    for field_path in required_fields:
        value = config
        try:
            for key in field_path:
                value = value[key]
            if value is None or value == "":
                missing_fields.append(".".join(field_path))
        except (KeyError, TypeError):
            missing_fields.append(".".join(field_path))
    
    if missing_fields:
        raise ValueError(
            f"Missing required configuration fields: {', '.join(missing_fields)}\n"
            f"Credentials should be in your .env file.\n"
            f"Other configuration should be in your JSON config file."
        )
