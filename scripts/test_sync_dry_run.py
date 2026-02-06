#!/usr/bin/env python3
"""
Script de test de synchronisation en mode DRY RUN.
N'effectue AUCUNE modification réelle :
- N'envoie PAS d'emails
- N'écrit PAS dans Airtable  
- N'ajoute PAS à la mailing list OVH

Affiche simplement ce qui serait fait.
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
    """Run sync in DRY RUN mode"""
    config_path = "config/hello-asso-automation-conf.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        print(f"   Using test config instead...")
        config_path = "config/hello-asso-automation-conf-test.json"
    
    print("=" * 70)
    print("🧪 MODE DRY RUN ACTIVÉ")
    print("=" * 70)
    print("✓ Récupération des données HelloAsso : OUI")
    print("✓ Écriture dans Airtable : NON (simulation)")
    print("✓ Ajout à la mailing list OVH : NON (simulation)")
    print("✓ Envoi d'emails : NON (simulation)")
    print("=" * 70)
    print()
    
    try:
        # Initialize with dry_run="full" for complete simulation
        sync = SyncHelloAsso(config_path, dry_run="full")
        
        print("📥 Récupération des adhésions HelloAsso...")
        sync.run()
        
        print()
        print("=" * 70)
        print("✅ TEST TERMINÉ - Aucune modification effectuée")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
