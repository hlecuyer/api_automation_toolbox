#!/usr/bin/env python3
"""
Script de test de synchronisation AIRTABLE SEULEMENT.

Effectue UNIQUEMENT :
✓ Récupère les données HelloAsso
✓ Écrit dans Airtable

N'EFFECTUE PAS :
✗ Ajout à la mailing list OVH (désactivé)
✗ Envoi d'emails (désactivé)
✗ Mise à jour de la date config (désactivé)
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.hello_asso_sync import SyncHelloAsso
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Run sync with ONLY Airtable updates (no OVH, no emails)"""
    config_path = "config/hello-asso-automation-conf.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        print(f"   Using test config instead...")
        config_path = "config/hello-asso-automation-conf-test.json"
    
    print("=" * 70)
    print("📊 MODE: AIRTABLE SEULEMENT")
    print("=" * 70)
    print("✓ Récupération des données HelloAsso : OUI (RÉEL)")
    print("✓ Écriture dans Airtable : OUI (RÉEL)")
    print("✗ Ajout à la mailing list OVH : NON (désactivé)")
    print("✗ Envoi d'emails : NON (désactivé)")
    print("✗ Mise à jour date config : NON (désactivé)")
    print("=" * 70)
    print()
    
    # Demander confirmation
    response = input("⚠️  ATTENTION: Ceci va modifier Airtable uniquement. Continuer? (oui/non): ")
    if response.lower() not in ['oui', 'o', 'yes', 'y']:
        print("❌ Annulé")
        return
    
    try:
        # Initialize with dry_run="only_airtable" (Airtable only)
        sync = SyncHelloAsso(config_path, dry_run="only_airtable")
        
        print("\n📥 Récupération des adhésions HelloAsso...")
        sync.run()
        
        print()
        print("=" * 70)
        print("✅ SYNCHRONISATION TERMINÉE")
        print("   Airtable mis à jour")
        print("   Mailing list OVH non modifiée")
        print("   Aucun email envoyé")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
