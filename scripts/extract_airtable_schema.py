#!/usr/bin/env python3
"""
Script pour extraire le schéma de la table Airtable.
Affiche tous les champs disponibles pour faciliter le mapping.
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

# Load environment variables
load_dotenv()

def main():
    """Extract Airtable schema"""
    config_path = "config/hello-asso-automation-conf.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return 1
    
    # Load config
    config = load_config(config_path)
    
    # Get Airtable credentials
    airtable_creds = config["credentials"]["airtable"]
    airtable_conf = config["conf"]["airtable"]
    
    print("=" * 70)
    print("📊 SCHÉMA AIRTABLE - Extraction des champs")
    print("=" * 70)
    print()
    
    # Get base_id from credentials (not conf)
    base_id = airtable_creds.get("base_id")
    if not base_id:
        print("❌ base_id manquant dans credentials.airtable")
        return 1
    
    # Create client
    client = AirtableClient(
        api_key=airtable_creds["api_key"],
        base_id=base_id,
        table_name=airtable_conf["table_name"],
    )
    
    print(f"Base: {base_id}")
    print(f"Table: {airtable_conf['table_name']}")
    print()
    
    # List records to get field names
    print("🔍 Récupération des enregistrements...")
    records = client.list_records()
    
    if not records:
        print("❌ Aucun enregistrement trouvé dans la table")
        print("   Ajoutez au moins un enregistrement dans Airtable pour voir les champs")
        return 1
    
    # Get all unique field names from all records
    all_fields = set()
    for record in records:
        fields = record.get("fields", {})
        all_fields.update(fields.keys())
    
    # Sort fields alphabetically
    sorted_fields = sorted(all_fields)
    
    print(f"\n✅ {len(records)} enregistrement(s) trouvé(s)")
    print(f"\n📋 {len(sorted_fields)} champs détectés dans la table Airtable:")
    print("=" * 70)
    
    # Display fields with example values
    example_record = records[0].get("fields", {})
    
    for field in sorted_fields:
        value = example_record.get(field, "")
        value_type = type(value).__name__
        
        # Truncate long values
        if isinstance(value, str) and len(value) > 50:
            display_value = value[:47] + "..."
        elif isinstance(value, list) and len(value) > 0:
            display_value = f"[{len(value)} élément(s)]"
        else:
            display_value = value
        
        print(f"  • {field:30s} ({value_type:10s}) : {display_value}")
    
    # Suggest mapping
    print("\n" + "=" * 70)
    print("💡 MAPPING SUGGÉRÉ pour src/models/user_subscription.py")
    print("=" * 70)
    print()
    print("Modifiez la méthode to_airtable_payload() comme ceci:")
    print()
    print("```python")
    print("def to_airtable_payload(self) -> Dict[str, Any]:")
    print('    """Convert subscription to Airtable format"""')
    print("    return {")
    
    # Suggest mappings based on common field names
    mapping_suggestions = {
        "E-mail": "self.email",
        "Email": "self.email",
        "email": "self.email",
        "Prénom": "self.first_name",
        "Prenom": "self.first_name",
        "firstName": "self.first_name",
        "Nom": "self.last_name",
        "lastName": "self.last_name",
        "Date d'adhésion": "self.subscription_date.isoformat() if self.subscription_date else None",
        "Date": "self.subscription_date.isoformat() if self.subscription_date else None",
        "date": "self.subscription_date.isoformat() if self.subscription_date else None",
        "Cotisation": "self.amount",
        "Cotisation LCDC": "self.amount",
        "Amount": "self.amount",
        "amount": "self.amount",
        "Montant": "self.amount",
        "Groupe(s)": "self.group",
        "Groupe": "self.group",
        "Group": "self.group",
        "group": "self.group",
    }
    
    for field in sorted_fields:
        if field in mapping_suggestions:
            print(f'        "{field}": {mapping_suggestions[field]},')
        else:
            print(f'        "{field}": None,  # TODO: mapper ce champ')
    
    print("    }")
    print("```")
    
    # Show example record
    print("\n" + "=" * 70)
    print("📝 EXEMPLE D'ENREGISTREMENT (premier de la table)")
    print("=" * 70)
    print()
    import json
    print(json.dumps(example_record, indent=2, ensure_ascii=False))
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
