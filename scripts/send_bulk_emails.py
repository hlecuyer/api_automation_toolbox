#!/usr/bin/env python3
"""
Script d'envoi d'emails groupés avec le client OVH SMTP.

Ce script lit un fichier CSV avec 4 colonnes d'emails et envoie
un message différent pour chaque colonne.

Usage:
    # Mode normal (envoi réel)
    python send_bulk_emails.py --csv "data/Liste mail non envoye adhésion 2026-VV.csv"

    # Mode test (envoie les 4 types de mails à une adresse de test)
    python send_bulk_emails.py --csv "data/Liste mail non envoye adhésion 2026-VV.csv" --test test@example.com

    # Dry run (simule l'envoi sans envoyer)
    python send_bulk_emails.py --csv "data/Liste mail non envoye adhésion 2026-VV.csv" --dry-run
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.clients.ovh_email_client import OVHEmailClient
from scripts.email_templates import EMAIL_TEMPLATES

# Load logo image for inline embedding
LOGO_PATH = Path(__file__).parent / "data" / "image.png"
LOGO_INLINE_IMAGES = None
if LOGO_PATH.exists():
    with open(LOGO_PATH, 'rb') as f:
        LOGO_INLINE_IMAGES = [("logo", f.read(), "png")]


DATA_DIR = Path(__file__).parent / "data"
MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def load_attachments(template: dict) -> list:
    """Load attachment files declared in a template's "attachments" key."""
    paths = template.get("attachments") or []
    loaded = []
    for name in paths:
        path = DATA_DIR / name
        if not path.exists():
            print(f"⚠️  Pièce jointe introuvable: {path}")
            continue
        mime = MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")
        with open(path, "rb") as f:
            loaded.append((path.name, f.read(), mime))
    return loaded


def parse_csv(csv_path: str) -> Dict[str, List[str]]:
    """
    Parse le fichier CSV et retourne un dictionnaire avec les emails par catégorie.
    
    Args:
        csv_path: Chemin vers le fichier CSV
        
    Returns:
        Dict avec les noms de colonnes comme clés et listes d'emails comme valeurs
    """
    print(f"\n📄 Lecture du fichier CSV: {csv_path}")

    emails_by_category = {}

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        # Initialiser les catégories à partir des en-têtes du CSV
        for col in (reader.fieldnames or []):
            col = col.strip()
            if col:
                emails_by_category[col] = []

        for row in reader:
            for category in emails_by_category.keys():
                email = row.get(category, '').strip()
                if email and '@' in email:  # Vérifier que c'est un email valide
                    emails_by_category[category].append(email)
    
    # Afficher les statistiques
    print("\n📊 Statistiques des emails:")
    total = 0
    for category, emails in emails_by_category.items():
        count = len(emails)
        total += count
        print(f"   • {category}: {count} emails")
    print(f"   • TOTAL: {total} emails\n")
    
    return emails_by_category


def send_emails(
    client: OVHEmailClient,
    sender: str,
    emails_by_category: Dict[str, List[str]],
    dry_run: bool = False,
    delay: float = 2.0
) -> Tuple[int, int]:
    """
    Envoie les emails pour chaque catégorie.
    
    Args:
        client: Client OVH Email
        sender: Adresse email de l'expéditeur
        emails_by_category: Dict avec les emails par catégorie
        dry_run: Si True, simule l'envoi sans envoyer
        delay: Délai en secondes entre chaque email
        
    Returns:
        Tuple (nombre d'emails envoyés, nombre d'erreurs)
    """
    sent_count = 0
    error_count = 0
    
    print("=" * 80)
    print("📧 DÉBUT DE L'ENVOI DES EMAILS")
    print("=" * 80)
    
    for category, emails in emails_by_category.items():
        if not emails:
            continue

        template = EMAIL_TEMPLATES[category]
        attachments = load_attachments(template)

        print(f"\n📮 Catégorie: {category}")
        print(f"   Sujet: {template['subject']}")
        print(f"   Destinataires: {len(emails)}")
        if attachments:
            print(f"   Pièces jointes: {', '.join(a[0] for a in attachments)}")
        print("-" * 80)

        for i, recipient in enumerate(emails, 1):
            try:
                print(f"   [{i}/{len(emails)}] Envoi à {recipient}...", end=" ")

                result = client.send_email(
                    sender=sender,
                    to=[recipient],
                    subject=template['subject'],
                    body_text=template['body_text'],
                    body_html=template['body_html'],
                    inline_images=LOGO_INLINE_IMAGES,
                    attachments=attachments or None,
                    dry_run=dry_run
                )
                
                if result:
                    print("✓")
                    sent_count += 1
                else:
                    print("✗ Échec")
                    error_count += 1
                
                # Délai entre les emails pour éviter de surcharger le serveur
                if not dry_run and i < len(emails):
                    time.sleep(delay)
                    
            except Exception as e:
                print(f"✗ Erreur: {e}")
                error_count += 1
    
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ")
    print("=" * 80)
    print(f"✅ Emails envoyés: {sent_count}")
    print(f"❌ Erreurs: {error_count}")
    print(f"📧 Total traité: {sent_count + error_count}")
    print("=" * 80 + "\n")
    
    return sent_count, error_count


def test_mode(
    client: OVHEmailClient,
    sender: str,
    test_email: str,
    dry_run: bool = False,
    templates: Dict[str, dict] = None
) -> None:
    """
    Mode test : envoie les types de mails sélectionnés à une seule adresse de test.

    Args:
        client: Client OVH Email
        sender: Adresse email de l'expéditeur
        test_email: Adresse email de test
        dry_run: Si True, simule l'envoi
        templates: Dict de templates à envoyer (défaut: tous)
    """
    if templates is None:
        templates = EMAIL_TEMPLATES

    total = len(templates)
    print("=" * 80)
    print("🧪 MODE TEST ACTIVÉ")
    print("=" * 80)
    print(f"Envoi de {total} type(s) de mail à: {test_email}\n")

    for i, (category, template) in enumerate(templates.items(), 1):
        print(f"[{i}/{total}] Envoi du mail '{category}'...", end=" ")
        
        # Ajouter une note dans le sujet pour le mode test
        test_subject = f"[TEST] {template['subject']}"
        test_body_html = f"""
        <div style="background-color: #fff3cd; border: 2px solid #ffc107; padding: 10px; margin-bottom: 20px;">
            <strong>⚠️ MODE TEST</strong><br>
            Type de mail: <strong>{category}</strong><br>
            Ceci est un email de test. En mode réel, ce message serait envoyé aux destinataires de la catégorie "{category}".
        </div>
        {template['body_html']}
        """
        
        try:
            attachments = load_attachments(template)
            result = client.send_email(
                sender=sender,
                to=[test_email],
                subject=test_subject,
                body_text=f"[MODE TEST - {category}]\n\n{template['body_text']}",
                body_html=test_body_html,
                inline_images=LOGO_INLINE_IMAGES,
                attachments=attachments or None,
                dry_run=dry_run
            )
            
            if result:
                print("✓")
            else:
                print("✗ Échec")
                
            # Petit délai entre les emails
            if i < total:
                time.sleep(1)
                
        except Exception as e:
            print(f"✗ Erreur: {e}")
    
    print("\n" + "=" * 80)
    print("✅ Test terminé ! Vérifiez votre boîte mail.")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Envoi d'emails groupés avec différents messages par catégorie"
    )
    parser.add_argument(
        '--csv',
        help='Chemin vers le fichier CSV avec les emails (requis sauf en mode --test)'
    )
    parser.add_argument(
        '--sender',
        default=os.getenv('SMTP_USER', 'contact@coopdescommuns.org'),
        help='Adresse email de l\'expéditeur (défaut: SMTP_USER depuis .env)'
    )
    parser.add_argument(
        '--smtp-host',
        default=os.getenv('SMTP_HOST', 'ssl0.ovh.net'),
        help='Serveur SMTP (défaut: SMTP_HOST depuis .env)'
    )
    parser.add_argument(
        '--smtp-port',
        type=int,
        default=int(os.getenv('SMTP_PORT', '587')),
        help='Port SMTP (défaut: SMTP_PORT depuis .env)'
    )
    parser.add_argument(
        '--smtp-user',
        default=os.getenv('SMTP_USER'),
        help='Utilisateur SMTP (défaut: SMTP_USER depuis .env)'
    )
    parser.add_argument(
        '--smtp-password',
        default=os.getenv('SMTP_PASSWORD'),
        help='Mot de passe SMTP (défaut: SMTP_PASSWORD depuis .env)'
    )
    parser.add_argument(
        '--test',
        metavar='EMAIL',
        help='Mode test: envoie les 4 types de mails à cette adresse de test'
    )
    parser.add_argument(
        '--template',
        metavar='NAME',
        help='Envoie uniquement ce template (ex: "Relance Adherent 2025"). Utilisable avec --test.'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simule l\'envoi sans envoyer réellement les emails'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='Délai en secondes entre chaque email (défaut: 2.0)'
    )
    
    args = parser.parse_args()
    
    # Vérifier que le fichier CSV existe (requis sauf en mode test)
    if not args.test:
        if not args.csv:
            print("❌ Erreur: --csv est requis en mode normal (non-test).")
            sys.exit(1)
        if not os.path.exists(args.csv):
            print(f"❌ Erreur: Le fichier CSV '{args.csv}' n'existe pas.")
            sys.exit(1)
    
    # Vérifier les credentials SMTP
    if not args.smtp_user or not args.smtp_password:
        print("❌ Erreur: SMTP_USER et SMTP_PASSWORD doivent être définis.")
        print("   Utilisez les arguments --smtp-user et --smtp-password")
        print("   ou définissez les variables d'environnement dans .env")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("📧 ENVOI D'EMAILS GROUPÉS - Coop des Communs")
    print("=" * 80)
    print(f"Mode: {'🧪 TEST' if args.test else '🔥 PRODUCTION'}")
    print(f"Dry-run: {'✓ Oui (simulation)' if args.dry_run else '✗ Non (envoi réel)'}")
    print(f"Expéditeur: {args.sender}")
    print(f"SMTP: {args.smtp_host}:{args.smtp_port}")
    print("=" * 80)
    
    # Créer le client email
    client = OVHEmailClient(
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        smtp_user=args.smtp_user,
        smtp_password=args.smtp_password
    )
    
    # Filtrer par template si spécifié
    templates_to_use = EMAIL_TEMPLATES
    if args.template:
        if args.template not in EMAIL_TEMPLATES:
            print(f"❌ Erreur: Template '{args.template}' introuvable.")
            print(f"   Templates disponibles: {', '.join(EMAIL_TEMPLATES.keys())}")
            sys.exit(1)
        templates_to_use = {args.template: EMAIL_TEMPLATES[args.template]}

    if args.test:
        # Mode test
        test_mode(client, args.sender, args.test, args.dry_run, templates_to_use)
    else:
        # Mode normal
        # Demander confirmation en mode production
        if not args.dry_run:
            print("\n⚠️  ATTENTION: Vous êtes sur le point d'envoyer des emails réels.")
            response = input("   Tapez 'OUI' pour confirmer: ")
            if response != 'OUI':
                print("❌ Envoi annulé.")
                sys.exit(0)
        
        # Lire le CSV
        emails_by_category = parse_csv(args.csv)
        
        # Envoyer les emails
        sent, errors = send_emails(
            client,
            args.sender,
            emails_by_category,
            dry_run=args.dry_run,
            delay=args.delay
        )
        
        if errors > 0:
            sys.exit(1)


if __name__ == '__main__':
    main()
