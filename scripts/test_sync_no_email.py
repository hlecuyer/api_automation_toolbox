#!/usr/bin/env python3
"""
Script de test de synchronisation SANS ENVOI D'EMAILS.

Effectue les modifications RÉELLES :
✓ Récupère les données HelloAsso
✓ Écrit dans Airtable
✓ Ajoute à la mailing list OVH

Mais N'ENVOIE PAS d'emails (dry_run=True pour les emails seulement)
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
    """Run sync WITHOUT sending emails (but does everything else)"""
    config_path = "config/hello-asso-automation-conf.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        print(f"   Using test config instead...")
        config_path = "config/hello-asso-automation-conf-test.json"
    
    print("=" * 70)
    print("📧 MODE: PAS D'EMAILS (mais tout le reste est RÉEL)")
    print("=" * 70)
    print("✓ Récupération des données HelloAsso : OUI (RÉEL)")
    print("✓ Écriture dans Airtable : OUI (RÉEL)")
    print("✓ Ajout à la mailing list OVH : OUI (RÉEL)")
    print("✓ Envoi d'emails : NON (désactivé)")
    print("=" * 70)
    print()
    
    # Demander confirmation
    response = input("⚠️  ATTENTION: Ceci va modifier Airtable et OVH. Continuer? (oui/non): ")
    if response.lower() not in ['oui', 'o', 'yes', 'y']:
        print("❌ Annulé")
        return
    
    try:
        # Initialize with dry_run="only_mail" (skip emails only)
        sync = SyncHelloAsso(config_path, dry_run="only_mail")
        
        print("\n📥 Récupération des adhésions HelloAsso...")
        sync.run()
        
        print()
        print("=" * 70)
        print("✅ SYNCHRONISATION TERMINÉE")
        print("   Airtable et mailing list mis à jour")
        print("   Aucun email envoyé")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
