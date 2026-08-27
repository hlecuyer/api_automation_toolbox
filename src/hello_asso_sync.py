"""Module pushing data from HelloAsso to Airtable"""

from datetime import datetime
import json
import re
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
from src import heartbeat

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
        self._compteurs = self._compteurs_neufs()
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
    
    @staticmethod
    def _compteurs_neufs():
        """Statut pessimiste par défaut : seul un passage qui va au bout le
        remet à « ok ». Un retour anticipé ou une exception laisse donc
        « échec », sans avoir à y penser à chaque point de sortie."""
        return {"statut": "échec", "vues": 0, "traitées": 0, "erreurs": 0,
                "non_rattachés": "?"}

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
            linked_records=self.conf["airtable"].get("linked_records"),
            computed_fields=self.conf["airtable"].get("computed_fields"),
            normalized_fields=self.conf["airtable"].get("normalized_fields"),
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
        self._compteurs["vues"] = len(subscriptions)
        
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
                    self._compteurs["erreurs"] += 1
                    syslog.syslog(
                        syslog.LOG_ERR,
                        f"Failed to sync {subscription.email} to Airtable",
                    )
                    continue
                
                self._compteurs["traitées"] += 1
                
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
                        self._compteurs["erreurs"] += 1
                        syslog.syslog(
                            syslog.LOG_ERR,
                            f"Failed to send confirmation email to {subscription.email}: {str(e)}",
                        )
            
            processed_emails.add(subscription.email)


    def _compter_non_rattaches(self):
        """Compte les adhérents à jour de cotisation rattachés à aucun groupe d'adhérents.

        Le 27/08/2026, un adhérent ayant réglé par chèque le 18/02 n'avait été
        rattaché à rien : ni groupe, ni liste de diffusion, pendant six mois.
        Découvert par hasard, en tirant un autre fil. Une absence ne fait pas de
        bruit, donc rien ne pouvait la signaler.

        La synchronisation HelloAsso, elle, ne rate personne. Le trou est le
        paiement par chèque, saisi à la main dans Airtable, qui court-circuite
        toute l'automatisation. Ce compteur est le filet de ce canal-là.

        Deux points de conception qui valent d'être dits :

        - **L'année se déduit de `cotisation_label`**, elle n'est pas écrite en
          dur. Sinon le contrôle deviendrait faux au 1er janvier, en silence, et
          ce serait un défaut de la même famille que celui qu'il surveille.
        - **La formule cherche l'année dans la cotisation**, pas un libellé
          exact : « Payé 2026 » et « paiement par chèque 2026 » sont donc pris
          tous les deux, et c'est justement le second qui nous intéresse.

        Ne lève jamais : un filet qui fait tomber le trapéziste ne sert à rien.
        En cas d'échec le compte reste « ? », ce qui se voit dans la ligne de
        vie — un inconnu se dit, il ne se tait pas.
        """
        try:
            annee = re.search(r"\d{4}", self.conf.get("cotisation_label", ""))
            groupe = self.conf.get("groupe")
            if not annee or not groupe:
                return
            formule = (
                "AND(FIND('{annee}', {{Cotisation LCDC}}),"
                " NOT(FIND('{groupe}', ARRAYJOIN({{Groupe(s)}}))))"
            ).format(annee=annee.group(0), groupe=groupe.replace("'", "\\'"))
            fiches = self.airtable_client.list_records(filter_by_formula=formule)
            self._compteurs["non_rattachés"] = len(fiches)
            if fiches:
                syslog.syslog(
                    syslog.LOG_WARNING,
                    "hello_asso_sync: %d adhérent(s) à jour non rattaché(s) au groupe "
                    "« %s » — probablement une adhésion réglée par chèque, saisie à la "
                    "main sans rattachement" % (len(fiches), groupe),
                )
        except Exception as e:
            syslog.syslog(
                syslog.LOG_WARNING,
                "hello_asso_sync: contrôle de rattachement impossible (%s)" % e,
            )

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
        """Main entry point for synchronization.

        Le corps réel est dans `_executer`. Ce niveau ne sert qu'à garantir la
        ligne de fin de passage et le ping de supervision, y compris quand
        `_executer` part par un retour anticipé ou par une exception.

        Sans cette ligne, une journée sans nouvelle adhésion et une journée où
        le script n'a pas tourné du tout produisent le même log, c'est-à-dire
        rien. C'est l'angle mort qui a laissé la liste `membres` supprimer
        seize adresses par jour pendant des mois sans que personne ne le voie.
        """
        self._compteurs = self._compteurs_neufs()
        try:
            self._executer()
        finally:
            self._signaler_fin_de_passage()

    def _signaler_fin_de_passage(self):
        """Écrit la ligne de vie et ping le dead man's switch.

        Uniquement en syslog : le cron de ce script ne redirige pas stdout et
        `MAILTO` est configuré, donc un print deviendrait un mail quotidien,
        qu'on cesserait de lire en deux semaines. Le silence reviendrait par la
        fenêtre.

        Le curseur figure dans la ligne parce qu'il était jusqu'ici le seul
        signal de vie, et qu'il fallait ouvrir config.json sur le serveur pour
        le connaître.
        """
        compteurs = self._compteurs
        syslog.syslog(
            syslog.LOG_INFO,
            "hello_asso_sync: passage terminé "
            "statut={statut} vues={vues} traitées={traitées} erreurs={erreurs} "
            "non_rattachés={non_rattachés} curseur={curseur}".format(
                curseur=self.conf["helloAsso"].get("subscription_after", "inconnu"),
                **compteurs,
            ),
        )
        # Une erreur unitaire ne rend pas le passage suspect : le voyant dit
        # « le passage a eu lieu », pas « tout est parfait ». Le compteur
        # d'erreurs porte le reste.
        heartbeat.signaler(
            "HEARTBEAT_URL_SYNC", succes=compteurs["statut"] == "ok"
        )

    def _executer(self):
        """Le passage lui-même."""
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
        
        self._compter_non_rattaches()
        self._compteurs["statut"] = "ok"


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
