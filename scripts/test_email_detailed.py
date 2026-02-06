#!/usr/bin/env python3
"""
Script de test d'envoi d'email avec détails complets.

Ce script envoie un email de test et affiche les headers complets
pour diagnostiquer les problèmes potentiels.
"""

import sys
import os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.clients.ovh_email_client import OVHEmailClient
from src.config_loader import load_config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    """Send a detailed test email"""
    config_path = "config/hello-asso-automation-conf.json"
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return 1
    
    # Load config
    config = load_config(config_path)
    
    # Get SMTP credentials
    smtp_creds = config["credentials"]["smtp"]
    
    print("=" * 70)
    print("📧 TEST EMAIL AVEC HEADERS COMPLETS")
    print("=" * 70)
    print()
    print(f"SMTP Host: {smtp_creds['host']}")
    print(f"SMTP Port: {smtp_creds['port']}")
    print(f"SMTP User: {smtp_creds['user']}")
    print()
    
    # Create client (SMTP only, no OVH API needed)
    client = OVHEmailClient(
        smtp_host=smtp_creds["host"],
        smtp_port=smtp_creds["port"],
        smtp_user=smtp_creds["user"],
        smtp_password=smtp_creds["password"],
    )
    
    # Get email configuration
    sender = config.get("ovh", {}).get("email", {}).get("from", smtp_creds["user"])
    
    # Ask for recipient
    print("🎯 Suggestions de test:")
    print("   1. Adresse Gmail (test@gmail.com) - pour vérifier si c'est un problème spécifique")
    print("   2. Adresse Outlook/Hotmail - autre test")
    print("   3. support@dsi.coop (défaut)")
    print()
    recipient = input("📮 Email destinataire (ou Entrée pour support@dsi.coop): ").strip()
    if not recipient:
        recipient = "support@dsi.coop"
    
    print()
    print(f"Envoi d'un email de test à {recipient}...")
    print()
    
    # Create a test message manually to show headers
    msg = MIMEMultipart('alternative')
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = "✅ Test Email avec Headers Complets"
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=sender.split('@')[1] if '@' in sender else 'mail.local')
    
    # Add body
    body_text = """
Bonjour,

Ceci est un email de test envoyé depuis le script de synchronisation HelloAsso.

Si vous recevez cet email, la configuration SMTP fonctionne correctement.

Headers inclus:
- From: Expéditeur de l'email
- To: Destinataire
- Subject: Sujet
- Date: Date d'envoi
- Message-ID: Identifiant unique du message

Cordialement,
Système de synchronisation HelloAsso
"""
    
    body_html = """
<html>
<head></head>
<body>
    <h2>✅ Email de Test</h2>
    <p><strong>Bonjour,</strong></p>
    <p>Ceci est un email de test envoyé depuis le script de synchronisation HelloAsso.</p>
    <p>Si vous recevez cet email, la configuration SMTP fonctionne correctement.</p>
    
    <h3>Headers inclus:</h3>
    <ul>
        <li><strong>From:</strong> Expéditeur de l'email</li>
        <li><strong>To:</strong> Destinataire</li>
        <li><strong>Subject:</strong> Sujet</li>
        <li><strong>Date:</strong> Date d'envoi</li>
        <li><strong>Message-ID:</strong> Identifiant unique du message</li>
    </ul>
    
    <p><em>Cordialement,<br>
    Système de synchronisation HelloAsso</em></p>
</body>
</html>
"""
    
    # Display headers
    print("📋 HEADERS:")
    print(f"   From: {msg['From']}")
    print(f"   To: {msg['To']}")
    print(f"   Subject: {msg['Subject']}")
    print(f"   Date: {msg['Date']}")
    print(f"   Message-ID: {msg['Message-ID']}")
    print()
    
    # Send via client
    try:
        result = client.send_email(
            sender=sender,
            to=[recipient],
            subject="✅ Test Email avec Headers Complets",
            body_text=body_text,
            body_html=body_html,
            dry_run=False,
        )
        
        if result:
            print("✅ Email envoyé avec succès !")
            print()
            print("🔍 VÉRIFICATIONS À FAIRE:")
            print("   1. Vérifiez votre boîte de réception")
            print("   2. Vérifiez le dossier SPAM/Courrier indésirable")
            print("   3. Vérifiez les règles de filtrage de votre boîte mail")
            print("   4. Si l'email disparaît, vérifiez:")
            print("      - Les règles de messagerie automatiques")
            print("      - Les filtres anti-spam du serveur")
            print("      - Les logs du serveur de messagerie")
        else:
            print("❌ Échec de l'envoi")
            return 1
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
