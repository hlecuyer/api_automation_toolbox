#!/usr/bin/env python3
"""
Script de diagnostic pour identifier pourquoi les emails disparaissent.
"""

import sys
import os
import socket
import dns.resolver
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_loader import load_config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_dns_records(domain):
    """Vérifier les enregistrements DNS pour l'authentification email"""
    print(f"\n🔍 Vérification DNS pour {domain}")
    print("=" * 70)
    
    # Check MX records
    print("\n📬 Enregistrements MX:")
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        for rdata in mx_records:
            print(f"   ✓ {rdata.preference} {rdata.exchange}")
    except Exception as e:
        print(f"   ✗ Erreur: {e}")
    
    # Check SPF record
    print("\n🛡️  Enregistrement SPF:")
    try:
        txt_records = dns.resolver.resolve(domain, 'TXT')
        spf_found = False
        for rdata in txt_records:
            txt = str(rdata).strip('"')
            if txt.startswith('v=spf1'):
                print(f"   ✓ {txt}")
                spf_found = True
        if not spf_found:
            print(f"   ⚠️  AUCUN enregistrement SPF trouvé!")
            print(f"   → Les emails peuvent être rejetés par les serveurs destinataires")
    except Exception as e:
        print(f"   ✗ Erreur: {e}")
    
    # Check DKIM
    print("\n🔐 Enregistrement DKIM:")
    selectors = ['default', 'mail', 'dkim', 'google', 'k1', 's1']
    dkim_found = False
    for selector in selectors:
        try:
            dkim_domain = f"{selector}._domainkey.{domain}"
            dkim_records = dns.resolver.resolve(dkim_domain, 'TXT')
            for rdata in dkim_records:
                txt = str(rdata).strip('"')
                if 'DKIM' in txt or 'k=' in txt:
                    print(f"   ✓ Trouvé avec selector '{selector}'")
                    print(f"     {txt[:80]}...")
                    dkim_found = True
                    break
        except:
            continue
    
    if not dkim_found:
        print(f"   ⚠️  AUCUN enregistrement DKIM trouvé (selectors testés: {', '.join(selectors)})")
        print(f"   → Les emails peuvent être considérés comme non authentifiés")
    
    # Check DMARC
    print("\n📋 Enregistrement DMARC:")
    try:
        dmarc_domain = f"_dmarc.{domain}"
        dmarc_records = dns.resolver.resolve(dmarc_domain, 'TXT')
        for rdata in dmarc_records:
            txt = str(rdata).strip('"')
            if txt.startswith('v=DMARC1'):
                print(f"   ✓ {txt}")
                if 'p=reject' in txt:
                    print(f"   ⚠️  Politique STRICTE (p=reject) - les emails non conformes sont REJETÉS")
                elif 'p=quarantine' in txt:
                    print(f"   ⚠️  Politique MODÉRÉE (p=quarantine) - les emails non conformes vont en SPAM")
    except Exception as e:
        print(f"   ⚠️  AUCUN enregistrement DMARC trouvé")
        print(f"   → Recommandé pour éviter l'usurpation d'identité")

def check_smtp_server(host, port):
    """Vérifier la connexion au serveur SMTP"""
    print(f"\n🌐 Test de connexion SMTP")
    print("=" * 70)
    print(f"Serveur: {host}:{port}")
    
    try:
        # Resolve hostname
        ip = socket.gethostbyname(host)
        print(f"✓ Résolution DNS: {host} → {ip}")
        
        # Test connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✓ Port {port} ouvert et accessible")
        else:
            print(f"✗ Port {port} fermé ou inaccessible")
            
    except Exception as e:
        print(f"✗ Erreur: {e}")

def main():
    """Diagnostic complet"""
    config_path = "config/hello-asso-automation-conf.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return 1
    
    # Load config
    config = load_config(config_path)
    smtp_creds = config["credentials"]["smtp"]
    
    print("=" * 70)
    print("🔬 DIAGNOSTIC EMAIL - Pourquoi les emails disparaissent?")
    print("=" * 70)
    
    # Extract domain from SMTP user
    sender = smtp_creds['user']
    domain = sender.split('@')[1] if '@' in sender else None
    
    if not domain:
        print("❌ Impossible d'extraire le domaine de l'expéditeur")
        return 1
    
    print(f"\n📧 Expéditeur: {sender}")
    print(f"🌍 Domaine: {domain}")
    
    # Check SMTP server
    check_smtp_server(smtp_creds['host'], smtp_creds['port'])
    
    # Check DNS records
    check_dns_records(domain)
    
    # Recommendations
    print("\n" + "=" * 70)
    print("💡 RECOMMANDATIONS")
    print("=" * 70)
    print("""
1. 🛡️  SPF: Vérifiez que le serveur SMTP est autorisé dans l'enregistrement SPF
   → Exemple: v=spf1 include:ssl0.ovh.net ~all

2. 🔐 DKIM: Configurez DKIM pour signer les emails
   → Contactez votre hébergeur pour activer DKIM

3. 📋 DMARC: Ajoutez un enregistrement DMARC avec p=none pour monitorer
   → Exemple: v=DMARC1; p=none; rua=mailto:postmaster@votre-domaine.org

4. 🔍 Logs serveur: Consultez les logs du serveur de RÉCEPTION
   → Les emails peuvent être supprimés par des règles automatiques

5. 📮 Test avec un autre destinataire:
   → Essayez d'envoyer à Gmail, Outlook pour comparer

6. 🚫 Blacklists: Vérifiez si votre IP/domaine n'est pas blacklisté
   → https://mxtoolbox.com/blacklists.aspx
   → https://multirbl.valli.org/

7. 🔧 Configuration OVH: Vérifiez dans le panel OVH
   → Authentification email (SPF, DKIM)
   → Logs d'envoi
   → Réputation du serveur SMTP
""")
    
    print("=" * 70)
    print("⚠️  CAUSE PROBABLE:")
    print("=" * 70)
    print("""
Si l'email APPARAÎT puis DISPARAÎT, c'est probablement:

1. 📧 Le serveur de RÉCEPTION supprime les emails non authentifiés
   → Vérifiez les enregistrements SPF/DKIM/DMARC ci-dessus

2. 🔒 Une règle de filtrage automatique côté destinataire
   → Vérifiez dans les paramètres de la boîte support@dsi.coop
   → Cherchez les règles de suppression automatique

3. 🛡️  Un anti-spam/anti-virus côté serveur
   → Consultez les logs du serveur mail de dsi.coop

4. 🗑️  Une politique de rétention agressive
   → Certains serveurs suppriment les emails suspects après quelques secondes
""")
    
    print("\n📞 PROCHAINE ÉTAPE:")
    print("   → Contactez l'administrateur de dsi.coop pour consulter les logs")
    print("   → OU testez avec une autre adresse email (Gmail, Outlook)")
    print()
    
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
