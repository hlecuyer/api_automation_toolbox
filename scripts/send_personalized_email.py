#!/usr/bin/env python3
"""
Envoi d'emails personnalisés (un destinataire = un mail rendu avec ses propres valeurs).

Le CSV doit avoir `mail` en première colonne. Les colonnes suivantes sont des
placeholders qui remplacent les `{nom_de_colonne}` présents dans le template.

Usage:
    # Test (envoie 1 mail à l'adresse fournie, prenom="Test")
    python send_personalized_email.py --template "10 ans intervenants" --test test@example.com

    # Dry-run sur le CSV
    python send_personalized_email.py --csv data/10ans_intervenants_perso.csv \\
        --template "10 ans intervenants" --dry-run

    # Envoi réel
    python send_personalized_email.py --csv data/10ans_intervenants_perso.csv \\
        --template "10 ans intervenants"
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.clients.ovh_email_client import OVHEmailClient
from scripts.email_templates_personalized import PERSONALIZED_EMAIL_TEMPLATES
from scripts.send_bulk_emails import LOGO_INLINE_IMAGES, load_attachments


def parse_csv(csv_path: str) -> List[Dict[str, str]]:
    """Lit le CSV et retourne une liste de dicts (un par ligne).

    La première colonne doit s'appeler 'mail'.
    """
    print(f"\n📄 Lecture du fichier CSV: {csv_path}")

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = [c.strip() for c in (reader.fieldnames or [])]

        if not fieldnames or fieldnames[0] != 'mail':
            print(f"❌ La première colonne du CSV doit s'appeler 'mail' (trouvé: {fieldnames[:1]})")
            sys.exit(1)

        rows = []
        for raw in reader:
            row = {k.strip(): (v or '').strip() for k, v in raw.items() if k}
            rows.append(row)

    placeholders = [c for c in fieldnames if c != 'mail']
    print(f"📊 {len(rows)} destinataires — placeholders: {placeholders or '(aucun)'}")
    return rows


def render_template(template: dict, row: Dict[str, str]) -> Tuple[str, str, str]:
    """Substitue les placeholders dans subject/body_text/body_html."""
    subject = template['subject'].format(**row)
    body_text = template['body_text'].format(**row)
    body_html = template['body_html'].format(**row)
    return subject, body_text, body_html


def send_personalized(
    client: OVHEmailClient,
    sender: str,
    template: dict,
    rows: List[Dict[str, str]],
    dry_run: bool = False,
    delay: float = 2.0,
) -> Tuple[int, int]:
    sent_count = 0
    error_count = 0

    attachments = load_attachments(template)

    print("=" * 80)
    print("📧 DÉBUT DE L'ENVOI DES EMAILS PERSONNALISÉS")
    print("=" * 80)
    print(f"   Sujet (template): {template['subject']}")
    print(f"   Destinataires: {len(rows)}")
    if attachments:
        print(f"   Pièces jointes: {', '.join(a[0] for a in attachments)}")
    print("-" * 80)

    for i, row in enumerate(rows, 1):
        recipient = row.get('mail', '')
        if not recipient or '@' not in recipient:
            print(f"   [{i}/{len(rows)}] ⚠️  mail invalide, skip: {recipient!r}")
            error_count += 1
            continue

        try:
            subject, body_text, body_html = render_template(template, row)
        except KeyError as e:
            print(f"   [{i}/{len(rows)}] ✗ placeholder manquant pour {recipient}: {e}")
            error_count += 1
            continue

        try:
            print(f"   [{i}/{len(rows)}] Envoi à {recipient}...", end=" ")
            result = client.send_email(
                sender=sender,
                to=[recipient],
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                inline_images=LOGO_INLINE_IMAGES,
                attachments=attachments or None,
                dry_run=dry_run,
            )
            if result:
                print("✓ [DRY RUN]" if dry_run else "✓")
                sent_count += 1
            else:
                print("✗ Échec")
                error_count += 1

            if not dry_run and i < len(rows):
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


def main():
    parser = argparse.ArgumentParser(
        description="Envoi d'emails personnalisés (1 mail par destinataire avec placeholders)."
    )
    parser.add_argument('--template', required=True,
                        help='Nom du template (clé de PERSONALIZED_EMAIL_TEMPLATES)')
    parser.add_argument('--csv',
                        help='Chemin vers le CSV (col 1 = mail, cols suivantes = placeholders). Requis sauf en --test.')
    parser.add_argument('--test', metavar='EMAIL',
                        help='Mode test: envoie 1 mail à cette adresse avec des valeurs factices.')
    parser.add_argument('--var', action='append', metavar='KEY=VALUE', default=[],
                        help='Valeur de placeholder pour le mode test (répétable). '
                             'Ex: --var prenom=Hugo --var role=crucial')
    parser.add_argument('--dry-run', action='store_true',
                        help="Simule l'envoi sans envoyer.")
    parser.add_argument('--delay', type=float, default=2.0,
                        help='Délai en secondes entre chaque mail (défaut 2.0)')
    parser.add_argument('--sender', default=os.getenv('SMTP_USER', 'contact@coopdescommuns.org'))
    parser.add_argument('--smtp-host', default=os.getenv('SMTP_HOST', 'ssl0.ovh.net'))
    parser.add_argument('--smtp-port', type=int, default=int(os.getenv('SMTP_PORT', '587')))
    parser.add_argument('--smtp-user', default=os.getenv('SMTP_USER'))
    parser.add_argument('--smtp-password', default=os.getenv('SMTP_PASSWORD'))

    args = parser.parse_args()

    if args.template not in PERSONALIZED_EMAIL_TEMPLATES:
        print(f"❌ Template '{args.template}' introuvable.")
        print(f"   Templates dispos: {', '.join(PERSONALIZED_EMAIL_TEMPLATES.keys())}")
        sys.exit(1)

    template = PERSONALIZED_EMAIL_TEMPLATES[args.template]

    if not args.test and not args.csv:
        print("❌ --csv est requis sauf en mode --test")
        sys.exit(1)
    if args.csv and not os.path.exists(args.csv):
        print(f"❌ Fichier CSV introuvable: {args.csv}")
        sys.exit(1)
    if not args.smtp_user or not args.smtp_password:
        print("❌ SMTP_USER et SMTP_PASSWORD requis (via .env ou flags).")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("📧 ENVOI EMAILS PERSONNALISÉS - Coop des Communs")
    print("=" * 80)
    print(f"Template: {args.template}")
    print(f"Mode: {'🧪 TEST' if args.test else '🔥 PRODUCTION'}")
    print(f"Dry-run: {'✓ Oui (simulation)' if args.dry_run else '✗ Non (envoi réel)'}")
    print(f"Expéditeur: {args.sender}")
    print(f"SMTP: {args.smtp_host}:{args.smtp_port}")
    print("=" * 80)

    client = OVHEmailClient(
        smtp_host=args.smtp_host,
        smtp_port=args.smtp_port,
        smtp_user=args.smtp_user,
        smtp_password=args.smtp_password,
    )

    if args.test:
        # Construire la ligne factice : defaults raisonnables + overrides via --var
        row = {'mail': args.test, 'prenom': 'Test', 'role': 'éminent'}
        for raw in args.var:
            if '=' not in raw:
                print(f"❌ --var attendu KEY=VALUE, reçu: {raw!r}")
                sys.exit(1)
            k, v = raw.split('=', 1)
            row[k.strip()] = v
        rows = [row]
        print(f"\n🧪 Valeurs de test: {row}")
    else:
        rows = parse_csv(args.csv)
        if not rows:
            print("❌ Aucun destinataire trouvé dans le CSV.")
            sys.exit(1)

        if not args.dry_run:
            print("\n⚠️  ATTENTION: Vous êtes sur le point d'envoyer des emails réels.")
            response = input("   Tapez 'OUI' pour confirmer: ")
            if response != 'OUI':
                print("❌ Envoi annulé.")
                sys.exit(0)

    sent, errors = send_personalized(
        client, args.sender, template, rows,
        dry_run=args.dry_run, delay=args.delay,
    )

    if errors > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
