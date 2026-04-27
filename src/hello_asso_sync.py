"""Module pushing data from HelloAsso to Airtable"""

from datetime import datetime
import json
import syslog
import argparse
from src.config_loader import load_config
from src.clients import (
    HelloAssoClient,
    OVHMailingClient,
    AirtableClient,
    OVHEmailClient,
)
from src.models import UserSubscription
from src.templates import welcome_email

# Class to sync data from hello-asso to Airtable


class SyncHelloAsso:
    """Class to handle helloasso data synchronization using dedicated clients."""

    def __init__(self, config_path, dry_run=None):
        """
        Initialize SyncHelloAsso with configuration.
        
        Args:
            config_path: Path to JSON config file containing non-sensitive configuration.
                        Credentials will be loaded from environment variables (.env file).
            dry_run: Dry run mode:
                    - None: Normal mode (everything is real)
                    - "only_airtable": Only Airtable is updated (no OVH, no emails, no date update)
                    - "only_mail": Email dry run (Airtable + OVH updated, but no emails sent)
                    - "full": Full dry run (nothing is modified, only simulation)
        """
        self.conf_path = config_path
        self.dry_run = dry_run
        try:
            # Load config from JSON file with credentials from env vars
            config = load_config(config_path)
            # store the full config to update the config file
            self.conf_global = config
            self.conf = config["conf"]
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, f"Failed to load configuration: {e}")
            raise e
        
        # Initialize clients
        self._init_clients()
    
    def _init_clients(self):
        """Initialize all service clients."""
        # Initialize HelloAsso client
        self.hello_asso_client = HelloAssoClient(
            api_url=self.conf["helloAsso"]["api_url"],
            organization_name=self.conf["helloAsso"]["organization_name"],
            client_id=self.conf_global["credentials"]["helloAsso"]["id"],
            client_secret=self.conf_global["credentials"]["helloAsso"]["secret"],
        )
        
        # Initialize OVH mailing client
        self.ovh_mailing_client = OVHMailingClient(
            application_key=self.conf_global["credentials"]["ovh"]["ak"],
            application_secret=self.conf_global["credentials"]["ovh"]["as"],
            consumer_key=self.conf_global["credentials"]["ovh"]["ck"],
            domain=self.conf["ovh"]["mailing_list"]["domain"],
            mailing_list_name=self.conf["ovh"]["mailing_list"]["name"],
            endpoint=self.conf_global["credentials"]["ovh"].get("endpoint", "ovh-eu"),
        )
        
        # Initialize OVH email client (optional - only if email config exists)
        if self.conf.get("ovh", {}).get("email"):
            self.ovh_email_client = OVHEmailClient(
                application_key=self.conf_global["credentials"]["ovh"]["ak"],
                application_secret=self.conf_global["credentials"]["ovh"]["as"],
                consumer_key=self.conf_global["credentials"]["ovh"]["ck"],
                endpoint=self.conf_global["credentials"]["ovh"].get("endpoint", "ovh-eu"),
                smtp_host=self.conf_global["credentials"].get("smtp", {}).get("host"),
                smtp_port=self.conf_global["credentials"].get("smtp", {}).get("port"),
                smtp_user=self.conf_global["credentials"].get("smtp", {}).get("user"),
                smtp_password=self.conf_global["credentials"].get("smtp", {}).get("password"),
            )
        else:
            self.ovh_email_client = None
        
        # Initialize Airtable client
        self.airtable_client = AirtableClient(
            api_key=self.conf_global["credentials"]["airtable"]["api_key"],
            base_id=self.conf_global["credentials"]["airtable"]["base_id"],
            table_name=self.conf["airtable"].get("table_name", "Annuaire"),
        )

        # Load welcome email logo for inline embedding (cid:logo)
        self.logo_inline_images = None
        try:
            with open(welcome_email.LOGO_PATH, "rb") as f:
                self.logo_inline_images = [("logo", f.read(), "png")]
        except FileNotFoundError:
            syslog.syslog(
                syslog.LOG_WARNING,
                f"Welcome email logo not found at {welcome_email.LOGO_PATH} — emails will be sent without inline logo",
            )


    def sync_subscriptions(
        self,
        subscriptions: list[UserSubscription],
        filter_date: datetime,
    ) -> None:
        """
        Sync user subscriptions to Airtable and mailing list.
        
        Args:
            subscriptions: List of UserSubscription objects
            filter_date: Only process subscriptions after this date
        """
        processed_emails = set()
        
        for subscription in subscriptions:
            # Skip duplicates
            if subscription.email in processed_emails:
                continue
            
            # Filter by date
            if subscription.subscription_date >= filter_date:
                # Sync to Airtable
                fields = subscription.to_airtable_payload()
                
                if self.dry_run == "full":
                    # Full dry run: don't write anything
                    syslog.syslog(
                        syslog.LOG_INFO,
                        f"[DRY RUN] Would sync {subscription.email} to Airtable with fields: {list(fields.keys())}",
                    )
                    print(f"  [DRY RUN] Airtable: {subscription.email} - {subscription.first_name} {subscription.last_name}")
                    result = True  # Simulate success
                else:
                    result = self.airtable_client.upsert_record(
                        email=subscription.email,
                        fields=fields,
                    )
                
                if not result:
                    syslog.syslog(
                        syslog.LOG_ERR,
                        f"Failed to sync {subscription.email} to Airtable",
                    )
                    continue
                
                # Add to OVH mailing list
                if self.dry_run in ("full", "only_airtable"):
                    # Full dry run or only_airtable: don't add to mailing list
                    syslog.syslog(
                        syslog.LOG_INFO,
                        f"[DRY RUN {self.dry_run}] Would add {subscription.email} to mailing list",
                    )
                    print(f"  [DRY RUN] Mailing list: {subscription.email}")
                else:
                    self.ovh_mailing_client.add_subscriber(subscription.email)
                
                # Send confirmation email if email client is configured
                if self.ovh_email_client and self.conf.get("ovh", {}).get("email", {}).get("send_confirmation"):
                    email_config = self.conf["ovh"]["email"]
                    try:
                        # dry_run pour send_email : True si mode "full", "only_mail", ou "only_airtable", False sinon
                        email_dry_run = self.dry_run in ("full", "only_mail", "only_airtable")
                        body_text, body_html = welcome_email.render(subscription.first_name)
                        self.ovh_email_client.send_email(
                            sender=email_config["from"],
                            to=[subscription.email],
                            subject=email_config.get("subject", welcome_email.SUBJECT),
                            body_html=body_html,
                            body_text=body_text,
                            inline_images=self.logo_inline_images,
                            dry_run=email_dry_run,
                        )
                        syslog.syslog(
                            syslog.LOG_INFO,
                            f"Confirmation email sent to {subscription.email}",
                        )
                    except Exception as e:
                        syslog.syslog(
                            syslog.LOG_ERR,
                            f"Failed to send confirmation email to {subscription.email}: {str(e)}",
                        )
            
            processed_emails.add(subscription.email)


    def update_date_conf(self):
        """Update subscription_after field with today's date
        (to avoid syncing several time the same user)"""
        try:
            with open(self.conf_path, "w", encoding="utf8") as jsonfile:
                self.conf_global["conf"]["helloAsso"][
                    "subscription_after"
                ] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                json.dump(self.conf_global, jsonfile, indent=2, ensure_ascii=False)
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                "Failed to update config file with new date {}".format(e),
            )
            raise e

    def run(self):
        """Main entry point for synchronization."""
        # Get form details
        form_detail = self.hello_asso_client.get_form_details(
            self.conf["helloAsso"]["form_name"]
        )
        
        if not form_detail:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Form '{self.conf['helloAsso']['form_name']}' not found",
            )
            return
        
        # Get form items
        form_items = self.hello_asso_client.get_form_items(
            form_detail["formType"],
            form_detail["formSlug"],
        )
        
        # Parse to subscriptions
        subscriptions = self.hello_asso_client.parse_items_to_subscriptions(
            items=form_items,
            cotisation=self.conf["cotisation_label"],
            groupe=self.conf["groupe"],
            default_fields=self.conf["helloAsso"].get("default"),
            first_sub_field=self.conf["helloAsso"].get("first_sub_field"),
            name_field=self.conf["helloAsso"].get("name_field"),
        )
        
        # Get filter date
        date_str = self.conf["helloAsso"].get(
            "subscription_after",
            "2000-01-01T00:00:00",
        )
        filter_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        
        # Sync subscriptions
        self.sync_subscriptions(subscriptions, filter_date)
        
        # Update config with current date (only in production mode)
        if self.dry_run is None:
            self.update_date_conf()
        else:
            syslog.syslog(
                syslog.LOG_INFO,
                f"[DRY RUN {self.dry_run}] Would update subscription_after date in config",
            )
            if self.dry_run == "full":
                print(f"  [DRY RUN] Config: subscription_after date NOT updated")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--conf", help="path to a config file")
    parser.add_argument(
        "--dry-run",
        choices=["only_airtable", "only_mail", "full"],
        default=None,
        help="dry run mode: only_airtable, only_mail, or full",
    )
    args = parser.parse_args()

    hello_asso_sync = SyncHelloAsso(args.conf, dry_run=args.dry_run)
    hello_asso_sync.run()
