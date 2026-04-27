"""Send the welcome email to a target address for visual/deliverability testing.

Usage:
    python scripts/send_welcome_test.py recipient@example.com [--name "Hugo"]

Reads SMTP credentials from .env (or already-set env vars). Renders the same
template that hello_asso_sync.py sends in production.
"""

import argparse
import os
import sys
from pathlib import Path

# Allow running from repo root or via PYTHONPATH=.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from src.clients.ovh_email_client import OVHEmailClient
from src.templates import welcome_email


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipient", help="Email address to send the welcome mail to")
    parser.add_argument("--name", default="Hugo", help="First name to inject (default: Hugo)")
    parser.add_argument(
        "--from",
        dest="sender",
        default="@@SIG_EMAIL@@",
        help="Sender address (default: @@SIG_EMAIL@@)",
    )
    parser.add_argument("--env", default=".env", help="Path to .env file (default: .env)")
    args = parser.parse_args()

    load_dotenv(args.env)

    body_text, body_html = welcome_email.render(args.name)

    inline_images = None
    if welcome_email.LOGO_PATH.exists():
        with open(welcome_email.LOGO_PATH, "rb") as f:
            inline_images = [("logo", f.read(), "png")]
    else:
        print(f"WARN: logo not found at {welcome_email.LOGO_PATH}", file=sys.stderr)

    client = OVHEmailClient(
        application_key=os.environ.get("OVH_APP_KEY", ""),
        application_secret=os.environ.get("OVH_APP_SECRET", ""),
        consumer_key=os.environ.get("OVH_CONSUMER_KEY", ""),
        endpoint=os.environ.get("OVH_ENDPOINT", "ovh-eu"),
        smtp_host=os.environ.get("SMTP_HOST"),
        smtp_port=int(os.environ["SMTP_PORT"]) if os.environ.get("SMTP_PORT") else None,
        smtp_user=os.environ.get("SMTP_USER"),
        smtp_password=os.environ.get("SMTP_PASSWORD"),
    )

    print(f"Sending welcome email:")
    print(f"  From:    {args.sender}")
    print(f"  To:      {args.recipient}")
    print(f"  Name:    {args.name}")
    print(f"  SMTP:    {os.environ.get('SMTP_HOST')}:{os.environ.get('SMTP_PORT')} (user={os.environ.get('SMTP_USER')})")
    print(f"  Subject: {welcome_email.SUBJECT}")
    print(f"  Logo:    {'attached' if inline_images else 'MISSING'}")

    ok = client.send_email(
        sender=args.sender,
        to=[args.recipient],
        subject=welcome_email.SUBJECT,
        body_text=body_text,
        body_html=body_html,
        inline_images=inline_images,
    )
    if ok:
        print("✓ Sent.")
        return 0
    print("✗ Send failed (check syslog).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
