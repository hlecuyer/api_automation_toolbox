"""Module pushing data from helloasso to a (zapier) webhook"""

from datetime import datetime
import json
import syslog
import argparse
from src.config_loader import load_config
from src.clients import HelloAssoClient, OVHMailingClient, WebhookClient
from src.models import UserSubscription

# Class to sync data from hello-asso to airtable using zapier automation with webhooks


class SyncHelloAsso:
    """Class to handle helloasso data synchronization using dedicated clients."""

    def __init__(self, config_path):
        """
        Initialize SyncHelloAsso with configuration.
        
        Args:
            config_path: Path to JSON config file containing non-sensitive configuration.
                        Credentials will be loaded from environment variables (.env file).
        """
        self.conf_path = config_path
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
        self.ovh_client = OVHMailingClient(
            application_key=self.conf_global["credentials"]["ovh"]["ak"],
            application_secret=self.conf_global["credentials"]["ovh"]["as"],
            consumer_key=self.conf_global["credentials"]["ovh"]["ck"],
            domain=self.conf["ovh"]["mailing_list"]["domain"],
            mailing_list_name=self.conf["ovh"]["mailing_list"]["name"],
            endpoint=self.conf_global["credentials"]["ovh"].get("endpoint", "ovh-eu"),
        )
        
        # Initialize webhook client
        self.webhook_client = WebhookClient(
            webhook_url=self.conf["webhook_url"],
        )

    
    def sync_subscriptions(
        self,
        subscriptions: list[UserSubscription],
        filter_date: datetime,
    ) -> None:
        """
        Sync user subscriptions to webhook and mailing list.
        
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
                # Send to webhook
                success = self.webhook_client.send_subscription(subscription)
                
                if not success:
                    syslog.syslog(
                        syslog.LOG_ERR,
                        f"Failed to send subscription for {subscription.email}",
                    )
                    continue
                
                # Add to OVH mailing list
                self.ovh_client.add_subscriber(subscription.email)
            
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
        
        # Update config with current date
        self.update_date_conf()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--conf", help="path to a config file")
    args = parser.parse_args()

    hello_asso_sync = SyncHelloAsso(args.conf)
    hello_asso_sync.run()
