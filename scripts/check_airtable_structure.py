#!/usr/bin/env python3
"""
Script pour lister les champs Airtable et voir leur structure.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.clients.airtable_client import AirtableClient
from src.config_loader import load_config
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

def main():
    """List Airtable structure"""
    config_path = "config/hello-asso-automation-conf.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return 1
    
    # Load config
    config = load_config(config_path)
    
    # Get credentials
    airtable_creds = config["credentials"]["airtable"]
    table_name = config["conf"]["airtable"]["table_name"]
    
    print("=" * 70)
    print("📊 STRUCTURE AIRTABLE")
    print("=" * 70)
    print(f"Base ID: {airtable_creds['base_id']}")
    print(f"Table: {table_name}")
    print()
    
    # Create client
    client = AirtableClient(
        api_key=airtable_creds["api_key"],
        base_id=airtable_creds["base_id"],
        table_name=table_name,
    )
    
    print("📥 Récupération des enregistrements (max 3)...")
    records = client.list_records()
    
    if not records:
        print("⚠️  Aucun enregistrement trouvé dans la table")
        return 0
    
    print(f"✓ {len(records)} enregistrement(s) trouvé(s)")
    print()
    
    # Show first record structure
    print("=" * 70)
    print("🔍 STRUCTURE DU PREMIER ENREGISTREMENT")
    print("=" * 70)
    
    first_record = records[0]
    fields = first_record.get("fields", {})
    
    print("\n📋 CHAMPS DISPONIBLES:")
    for i, (field_name, field_value) in enumerate(fields.items(), 1):
        value_preview = str(field_value)[:50]
        if len(str(field_value)) > 50:
            value_preview += "..."
        print(f"   {i}. '{field_name}' = {value_preview}")
    
    print("\n" + "=" * 70)
    print("💡 MAPPING SUGGÉRÉ POUR user_subscription.py")
    print("=" * 70)
    print("\nCherche les champs suivants dans la liste ci-dessus:")
    print("   - Email (ou email, ou E-mail)")
    print("   - Prénom (ou firstName, ou First Name)")
    print("   - Nom (ou lastName, ou Last Name)")
    print("   - Date")
    print("   - Cotisation")
    print("   - Groupe")
    
    print("\n📄 ENREGISTREMENT COMPLET (JSON):")
    print(json.dumps(first_record, indent=2, ensure_ascii=False))
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
