#!/usr/bin/env python3
"""
Script pour comparer les champs HelloAsso et Airtable.
Affiche le mapping actuel et identifie ce qui manque.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.clients.hello_asso_client import HelloAssoClient
from src.clients.airtable_client import AirtableClient
from src.config_loader import load_config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Compare HelloAsso and Airtable schemas"""
    config_path = "config/hello-asso-automation-conf.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return 1
    
    # Load config
    config = load_config(config_path)
    conf = config["conf"]
    
    print("=" * 80)
    print("🔄 COMPARAISON HELLOASSO ↔ AIRTABLE")
    print("=" * 80)
    print()
    
    # ===== HELLOASSO =====
    print("📥 RÉCUPÉRATION D'UN ENREGISTREMENT HELLOASSO...")
    helloasso_creds = config["credentials"]["helloAsso"]
    helloasso_conf = conf["helloAsso"]
    
    helloasso_client = HelloAssoClient(
        client_id=helloasso_creds["id"],
        client_secret=helloasso_creds["secret"],
        api_url=helloasso_conf["api_url"],
        organization_name=helloasso_conf["organization_name"],
    )
    
    # Get form details first
    form_details = helloasso_client.get_form_details(form_name=helloasso_conf["form_name"])
    
    # Get items from form (all items, no filter for analysis)
    items = helloasso_client.get_form_items(
        form_type=form_details["formType"],
        form_slug=form_details["formSlug"],
    )
    
    if not items:
        print("❌ Aucune adhésion trouvée sur HelloAsso")
        return 1
    
    # Take first item
    item = items[0]
    print(f"✅ Adhésion trouvée: {item.get('payer', {}).get('firstName')} {item.get('payer', {}).get('lastName')}")
    
    # Extract all fields
    payer = item.get("payer", {})
    custom_fields = {}
    for field in item.get("customFields", []):
        custom_fields[field.get("name")] = field.get("answer", "")
    
    print()
    print("📋 CHAMPS HELLOASSO DISPONIBLES:")
    print("-" * 80)
    print(f"  • email            : {payer.get('email')}")
    print(f"  • firstName        : {payer.get('firstName')}")
    print(f"  • lastName         : {payer.get('lastName')}")
    print(f"  • date             : {item.get('date')}")
    print(f"  • amount           : {item.get('amount', 0) / 100} €")
    print()
    print(f"  Custom Fields ({len(custom_fields)} champs):")
    for field_name, field_value in sorted(custom_fields.items()):
        value_display = field_value[:50] + "..." if len(field_value) > 50 else field_value
        print(f"    - {field_name:60s} : {value_display}")
    
    # ===== AIRTABLE =====
    print()
    print("=" * 80)
    print("📊 RÉCUPÉRATION DES CHAMPS AIRTABLE...")
    airtable_creds = config["credentials"]["airtable"]
    airtable_conf = conf["airtable"]
    
    airtable_client = AirtableClient(
        api_key=airtable_creds["api_key"],
        base_id=airtable_creds["base_id"],
        table_name=airtable_conf["table_name"],
    )
    
    records = airtable_client.list_records()
    if not records:
        print("❌ Aucun enregistrement trouvé dans Airtable")
        return 1
    
    # Get all field names
    all_fields = set()
    for record in records:
        all_fields.update(record.get("fields", {}).keys())
    
    print(f"✅ {len(records)} enregistrement(s) trouvés")
    print()
    print(f"📋 CHAMPS AIRTABLE DISPONIBLES ({len(all_fields)} champs):")
    print("-" * 80)
    for field in sorted(all_fields):
        print(f"  • {field}")
    
    # ===== MAPPING ACTUEL =====
    print()
    print("=" * 80)
    print("🔗 MAPPING ACTUEL (dans src/models/user_subscription.py)")
    print("=" * 80)
    print()
    
    current_mapping = {
        "email": "E-mail",
        "firstName": "Prénom",
        "lastName": "Nom",
        "cotisation": "Cotisation LCDC",
        "groupe": "Groupe(s)",
    }
    
    custom_field_mapping = {
        "Genre": "Genre",
        "Structure": "Structure(s)",
        "Fonction au sein de votre structure": "Fonction (structure)",
        "Intérêts (mot-clés)": "Intérêts",
        "Localisation (code postal)": "code postal",
        "Visible sur le site": "Visible sur le site",
        "Règles de Confidentialité": "Règles de Confidentialité",
    }
    
    print("Champs de base:")
    for ha_field, at_field in current_mapping.items():
        status = "✅" if at_field in all_fields else "❌"
        print(f"  {status} {ha_field:20s} → {at_field}")
    
    print()
    print("Custom fields:")
    for ha_field, at_field in custom_field_mapping.items():
        status = "✅" if at_field in all_fields else "❌"
        in_ha = "✅" if ha_field in custom_fields else "❌"
        print(f"  {status} (HelloAsso: {in_ha}) {ha_field:60s} → {at_field}")
    
    # ===== CHAMPS MANQUANTS =====
    print()
    print("=" * 80)
    print("⚠️  CHAMPS HELLOASSO NON MAPPÉS")
    print("=" * 80)
    print()
    
    mapped_ha_fields = set(custom_field_mapping.keys())
    unmapped_ha_fields = set(custom_fields.keys()) - mapped_ha_fields
    
    if unmapped_ha_fields:
        print(f"Ces {len(unmapped_ha_fields)} champs HelloAsso ne sont pas mappés vers Airtable:")
        print()
        for field in sorted(unmapped_ha_fields):
            value = custom_fields[field]
            value_display = value[:50] + "..." if len(value) > 50 else value
            print(f"  ❌ {field:60s} : {value_display}")
        print()
        print("💡 Pour les mapper, ajoutez-les dans custom_field_mapping dans")
        print("   src/models/user_subscription.py")
    else:
        print("✅ Tous les champs HelloAsso sont mappés !")
    
    # ===== PROBLÈME AVEC COTISATION =====
    print()
    print("=" * 80)
    print("⚠️  VÉRIFICATION DU CHAMP 'Cotisation LCDC'")
    print("=" * 80)
    print()
    
    cotisation_value = conf.get("cotisation_label", "Payé 2025")
    print(f"Valeur configurée : '{cotisation_value}'")
    print()
    
    # Get possible values from existing records
    cotisation_values = set()
    for record in records:
        val = record.get("fields", {}).get("Cotisation LCDC")
        if val:
            cotisation_values.add(val)
    
    print(f"Valeurs existantes dans Airtable ({len(cotisation_values)}):")
    for val in sorted(cotisation_values):
        match = "✅" if val == cotisation_value else "  "
        print(f"  {match} '{val}'")
    
    if cotisation_value not in cotisation_values:
        print()
        print(f"❌ PROBLÈME: '{cotisation_value}' n'existe pas comme option dans Airtable!")
        print()
        print("SOLUTIONS:")
        print(f"  1. Ajouter '{cotisation_value}' comme option dans le champ 'Cotisation LCDC'")
        print(f"     dans Airtable (paramètres du champ → personnaliser le type de champ)")
        print()
        print(f"  2. OU changer cotisation_label dans config pour utiliser une valeur existante")
        print(f"     Par exemple: {list(cotisation_values)[0] if cotisation_values else 'N/A'}")
    else:
        print()
        print(f"✅ La valeur '{cotisation_value}' existe dans Airtable")
    
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
