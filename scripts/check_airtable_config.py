#!/usr/bin/env python3
"""Script pour vérifier la configuration Airtable et afficher le Base ID."""

import os
import sys
from dotenv import load_dotenv

def main():
    print("🔍 Vérification de la configuration Airtable...\n")
    
    # Load .env
    load_dotenv()
    
    api_key = os.getenv('AIRTABLE_API_KEY')
    base_id = os.getenv('AIRTABLE_BASE_ID')
    table_name = os.getenv('AIRTABLE_TABLE_NAME', 'Annuaire')
    
    errors = []
    warnings = []
    
    # Check API Key
    print("📋 AIRTABLE_API_KEY:")
    if not api_key:
        print("   ❌ Non défini")
        errors.append("AIRTABLE_API_KEY manquant")
    elif not api_key.startswith('pat'):
        print(f"   ⚠️  '{api_key[:20]}...'")
        warnings.append("AIRTABLE_API_KEY devrait commencer par 'pat'")
    else:
        print(f"   ✅ '{api_key[:15]}...' (length: {len(api_key)})")
    
    # Check Base ID
    print("\n📋 AIRTABLE_BASE_ID:")
    if not base_id:
        print("   ❌ Non défini")
        errors.append("AIRTABLE_BASE_ID manquant")
        print("\n   💡 Pour trouver votre Base ID:")
        print("      1. Ouvrez votre base Airtable dans le navigateur")
        print("      2. L'URL ressemble à: https://airtable.com/appXXXXXXXXXXXXXX/...")
        print("      3. Le Base ID est: appXXXXXXXXXXXXXX (la partie après airtable.com/)")
        print("      4. Ou allez sur: https://airtable.com/api")
    elif not base_id.startswith('app'):
        print(f"   ❌ '{base_id}'")
        errors.append(f"AIRTABLE_BASE_ID invalide: doit commencer par 'app', pas '{base_id}'")
        print("\n   ⚠️  Vous avez probablement mis le NOM de la base au lieu de l'ID")
        print("   💡 Pour trouver votre Base ID:")
        print("      1. Ouvrez votre base dans le navigateur")
        print("      2. L'URL ressemble à: https://airtable.com/appXXXXXXXXXXXXXX/...")
        print("      3. Copiez la partie appXXXXXXXXXXXXXX")
    else:
        print(f"   ✅ '{base_id}'")
        
        # Try to get the actual base info
        try:
            import requests
            
            # Test READ permission
            url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
            headers = {
                'Authorization': f"Bearer {api_key}",
            }
            response = requests.get(url, headers=headers, params={'maxRecords': 1}, timeout=10)
            
            if response.status_code == 200:
                records = response.json().get('records', [])
                print(f"   ✅ Lecture (READ) réussie! ({len(records)} record(s) trouvé(s))")
                
                # Test WRITE permission (dry test)
                print("\n📋 Test des permissions d'ÉCRITURE:")
                test_payload = {
                    "fields": {
                        "E-mail": "test-permission-check@temp.local",
                        "Nom": "TEST_PERMISSION",
                        "Prénom": "Test"
                    }
                }
                headers_post = {
                    'Authorization': f"Bearer {api_key}",
                    'Content-Type': 'application/json'
                }
                write_response = requests.post(url, headers=headers_post, json=test_payload, timeout=10)
                
                if write_response.status_code == 200 or write_response.status_code == 201:
                    created_record = write_response.json()
                    record_id = created_record.get('id')
                    print(f"   ✅ Écriture (WRITE) réussie!")
                    
                    # Cleanup: delete the test record
                    if record_id:
                        delete_url = f"{url}/{record_id}"
                        requests.delete(delete_url, headers=headers_post, timeout=10)
                        print(f"   ✅ Test cleanup effectué")
                elif write_response.status_code == 403:
                    print(f"   ❌ Pas de permission d'écriture (403 Forbidden)")
                    errors.append("Token en LECTURE SEULE - permissions d'écriture manquantes")
                    print(f"\n   💡 Votre token n'a PAS les permissions data.records:write")
                    print(f"   📖 Consultez: AIRTABLE_PERMISSIONS_FIX.md pour la solution")
                else:
                    print(f"   ⚠️  Erreur d'écriture {write_response.status_code}: {write_response.text[:100]}")
                    warnings.append(f"Test d'écriture échoué (HTTP {write_response.status_code})")
                    
            elif response.status_code == 401:
                print(f"   ❌ Erreur d'authentification (401)")
                errors.append("API Key invalide ou expirée")
            elif response.status_code == 404:
                print(f"   ❌ Base ou table non trouvée (404)")
                errors.append(f"Base '{base_id}' ou table '{table_name}' introuvable")
            else:
                print(f"   ⚠️  Erreur {response.status_code}: {response.text[:100]}")
                warnings.append(f"Impossible de vérifier la connexion (HTTP {response.status_code})")
        except Exception as e:
            print(f"   ⚠️  Impossible de tester la connexion: {e}")
            warnings.append("Erreur lors du test de connexion")
    
    # Check table name
    print(f"\n📋 Table: '{table_name}'")
    
    # Summary
    print("\n" + "="*60)
    if errors:
        print(f"❌ {len(errors)} erreur(s) trouvée(s):")
        for error in errors:
            print(f"   • {error}")
        print("\n📝 Modifiez votre fichier .env avec les bonnes valeurs:")
        print("   AIRTABLE_API_KEY=patXXXXXXXXXXXX.XXXXXXXXX")
        print("   AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX")
        return 1
    elif warnings:
        print(f"⚠️  {len(warnings)} avertissement(s):")
        for warning in warnings:
            print(f"   • {warning}")
        return 0
    else:
        print("✅ Configuration Airtable correcte!")
        print("\n🧪 Vous pouvez maintenant lancer les tests:")
        print("   pytest tests/test_functional.py::TestAirtableConnection -v -s")
        return 0

if __name__ == '__main__':
    sys.exit(main())
