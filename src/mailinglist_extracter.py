import sys
import syslog
import traceback
import ovh
from pyairtable import Api
from pyairtable.formulas import match
import json
import argparse

from src.config_loader import load_config
from src import heartbeat


REQUIRED_FIELDS = [
    ("credentials", "airtable", "api_key"),
    ("credentials", "ovh", "ak"),
    ("credentials", "ovh", "as"),
    ("credentials", "ovh", "ck"),
]


def normaliser_email(email):
    """Forme canonique d'une adresse, pour comparaison uniquement.

    Ne sert jamais à écrire : les valeurs transmises à OVH restent celles reçues
    d'Airtable ou d'OVH, telles quelles.
    """
    return email.strip().lower() if isinstance(email, str) else email


class CheckOvhMailinglist:
    COMPTEURS_NEUFS = {
        "statut": "échec",
        "listes": 0,
        "ajouts": 0,
        "suppressions": 0,
        "erreurs": 0,
    }

    def __init__(self, config_path):
        self.conf_path = config_path
        self._compteurs = dict(self.COMPTEURS_NEUFS)
        try:
            config = load_config(config_path, required_fields=REQUIRED_FIELDS)
            self.conf_global = config
            self.conf = config["conf"]
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, "Failed to load configuration: {}".format(e))
            raise e

        self.ovh_client = ovh.Client(
            endpoint="ovh-eu",
            application_key=self.conf_global["credentials"]["ovh"]["ak"],
            application_secret=self.conf_global["credentials"]["ovh"]["as"],
            consumer_key=self.conf_global["credentials"]["ovh"]["ck"],
        )
        self.airtable_key = self.conf_global["credentials"]["airtable"]["api_key"]

    def AddOvhMailingListSubscriber(self, mailing_list, mail):
        try:
            result = self.ovh_client.post(
                "/email/domain/{}/mailingList/{}/subscriber".format(
                    mailing_list["domain"], mailing_list["name"]
                ),
                email=mail,
            )
        except ovh.exceptions.ResourceConflictError as e:
            syslog.syslog(
                syslog.LOG_INFO,
                "The subscriber {} already exists in this mailing list. Details: {}".format(
                    mail, e
                ),
            )

    def DeleteOvhMailinglistSubscriber(self, mailing_list, mail):
        try:
            result = self.ovh_client.delete(
                "/email/domain/{}/mailingList/{}/subscriber/{}".format(
                    mailing_list["domain"], mailing_list["name"], mail
                )
            )
        except Exception as e:
            raise e

    def UpdateAirtableData(self, base_id, table_id, entry_id, values):
        airtable_client = Api(self.airtable_key).table(base_id, table_id)
        airtable_client.update(entry_id, values)

    def GetAirtableData(self, item):
        airtable_client = Api(self.airtable_key).table(
            item["base_id"], item["table_id"]
        )
        result = []
        selected_fields = []
        for field in item["select_field"]:
            selected_fields.append(field["name"])
        if "filter" in item:
            item["filter"]["operation"]
            formula = (
                "OR({"
                + item["filter"]["field"]
                + "}"
                + item["filter"]["operation"]
                + "'"
                + item["filter"]["value"][0]
                + "'"
            )
            for values in item["filter"]["value"][1:]:
                formula = (
                    formula
                    + ",{"
                    + item["filter"]["field"]
                    + "}"
                    + item["filter"]["operation"]
                    + "'"
                    + values
                    + "'"
                )
            formula = formula + ")"

            # formula = match({item["filter"]["field"]: item["filter"]["value"][0], item["filter"]["field"]: item["filter"]["value"][1]})
            tmp = airtable_client.all(formula=formula, fields=selected_fields)
            for j in tmp:
                for field in item["select_field"]:
                    if "get_id" in field:
                        if field["name"] in j["fields"]:
                            result.append(
                                {
                                    field["get_id"]: j["id"],
                                    field["name"]: j["fields"][field["name"]],
                                }
                            )
                        else:
                            result.append(
                                {
                                    field["get_id"]: j["id"],
                                    field["name"]: [],
                                }
                            )
                    elif field["name"] in j["fields"]:
                        if "split" in field:
                            for str in j["fields"][field["name"]].split(field["split"]):
                                result.append(str.replace(" ", ""))
                        else:
                            result.append(j["fields"][field["name"]])
        else:
            tmp = airtable_client.all(fields=selected_fields)
            for j in tmp:
                for field in item["select_field"]:
                    if field["name"] in j["fields"]:
                        if "split" in field:
                            for str in j["fields"][field["name"]].split(field["split"]):
                                result.append(str.replace(" ", ""))
                        else:
                            result.append(j["fields"][field["name"]])
        # print(json.dumps(result, indent=4))
        return result

    def GetOvhMailingList(self, item):
        ovh_subscribers = self.ovh_client.get(
            "/email/domain/{}/mailingList/".format(item["domain"])
        )
        #        print(json.dumps(ovh_subscribers, indent=4))
        return ovh_subscribers

    def GetOvhMailingListSub(self, item):
        ovh_subscribers = self.ovh_client.get(
            "/email/domain/{}/mailingList/{}/subscriber".format(
                item["domain"], item["name"]
            )
        )
        #       print(json.dumps(ovh_subscribers, indent=4))
        return ovh_subscribers

    def GetOvhAllMailingListSub(self, item):
        ovh_mailing_list = self.ovh_client.get(
            "/email/domain/{}/mailingList".format(item["domain"])
        )
        ovh_mailing_list_data = {}
        for list in ovh_mailing_list:
            ovh_subscribers = self.ovh_client.get(
                "/email/domain/{}/mailingList/{}/subscriber".format(
                    item["domain"], list
                )
            )
            ovh_mailing_list_data.update({list: ovh_subscribers})
        print(json.dumps(ovh_mailing_list_data, indent=4))
        return ovh_mailing_list_data

    def CheckMailingListUsers(self):
        data = []
        for item in self.conf["compare"]:
            if item["type"] == "airtable":
                data.append(self.GetAirtableData(item))
            elif item["type"] == "ovh":
                data.append(self.GetOvhMailingListSub(item["mailingList"]))

        print(json.dumps(data, indent=4))
        not_member = []
        member = []
        for item in data[1:]:
            for mail in item:
                if mail in data[0]:
                    if mail not in member:
                        member.append(mail)
                elif mail not in not_member:
                    not_member.append(mail)

        print("membre")
        print(json.dumps(member, indent=4))

        print("non membre")
        print(json.dumps(not_member, indent=4))

    def SyncAirtableGroup(self):
        data = self.GetAirtableData(self.conf["sync_airtable_group"])
        temp = {}
        for item in data:
            field_name = self.conf["sync_airtable_group"]["select_field"][0]["name"]
            if self.conf["sync_airtable_group"]["remove"]:
                if self.conf["sync_airtable_group"]["group_id"] in item[field_name]:
                    temp = {field_name: item[field_name]}
                    temp[field_name].remove(
                        self.conf["sync_airtable_group"]["group_id"]
                    )
            else:
                if self.conf["sync_airtable_group"]["group_id"] not in item[field_name]:
                    temp = {field_name: item[field_name]}
                    temp[field_name].append(
                        self.conf["sync_airtable_group"]["group_id"]
                    )

            self.UpdateAirtableData(
                self.conf["sync_airtable_group"]["base_id"],
                self.conf["sync_airtable_group"]["table_id"],
                item["id"],
                temp,
            )
        # print(json.dumps(data, indent=4))

    def ReconcileSubscribers(
        self, mailing_list, airtable_subscribers, ovh_subscribers, label=""
    ):
        """Aligne une liste de diffusion OVH sur Airtable, hors casse.

        Airtable et OVH ne s'accordent pas toujours sur la casse d'une même
        adresse : `Jean.Dupont@…` d'un côté, `jean.dupont@…` de l'autre. Comparées
        littéralement, chacune paraît absente de l'autre source : l'abonné est
        supprimé puis réajouté, et cela recommence à chaque passage du cron, tous
        les jours.

        La comparaison se fait donc sur la forme normalisée, les appels OVH sur la
        valeur d'origine.
        """
        connus_airtable = {normaliser_email(e) for e in airtable_subscribers}
        connus_ovh = {normaliser_email(e) for e in ovh_subscribers}

        for email in ovh_subscribers:
            if normaliser_email(email) not in connus_airtable:
                print("delete " + email + (" from " + label if label else ""))
                self._compteurs["suppressions"] += 1
                self.DeleteOvhMailinglistSubscriber(mailing_list, email)

        for email in airtable_subscribers:
            if normaliser_email(email) not in connus_ovh:
                print("add " + email + (" in " + label if label else ""))
                self._compteurs["ajouts"] += 1
                self.AddOvhMailingListSubscriber(mailing_list, email)

    def SyncMailingList(self):

        ovh_subscribers = []
        airtable_subscribers = []
        mailing_list = ""
        for item in self.conf["sync_mailing_list"]:
            if item["type"] == "airtable":
                airtable_subscribers.extend(self.GetAirtableData(item))
            elif item["type"] == "ovh":
                ovh_subscribers.extend(self.GetOvhMailingListSub(item["mailingList"]))
                mailing_list = item["mailingList"]

        print(json.dumps(ovh_subscribers, indent=4))
        print(json.dumps(airtable_subscribers, indent=4))

        self.ReconcileSubscribers(mailing_list, airtable_subscribers, ovh_subscribers)

    def AutoSyncMailingList(self):

        airtable_mailing_list = []

        mailing_list = ""
        airtable_mailing_list.extend(
            self.GetAirtableData(self.conf["auto_sync_mailing_list"])
        )
        print("E-mail,Groupe(s)")
        for item in airtable_mailing_list:
            ovh_subscribers = []
            airtable_subscribers = []

            tmp = self.conf["auto_sync_mailing_list"]
            tmp["select_field"] = [
                {
                    "name": self.conf["auto_sync_mailing_list"]["mail_field"],
                    #                    "split": ",",
                }
            ]
            tmp["filter"] = {
                "field": self.conf["auto_sync_mailing_list"]["label_field"],
                "value": [item],
                "operation": "=",
            }
            airtable_data = self.GetAirtableData(tmp)

            # Check if the data is not empty before extending airtable_subscribers
            if airtable_data and airtable_data[0]:
                airtable_subscribers.extend(airtable_data[0])
            # airtable_subscribers.extend(self.GetAirtableData(tmp)[0])
            mailing_list = {
                "name": item,
                "domain": self.conf["auto_sync_mailing_list"]["ovh_domain"],
            }
            self._compteurs["listes"] += 1
            try:
                ovh_subscribers.extend(self.GetOvhMailingListSub(mailing_list))
            except ovh.exceptions.ResourceNotFoundError as e:
                self._compteurs["erreurs"] += 1
                msg = "The mailing list {} does not exists".format(mailing_list)
                syslog.syslog(syslog.LOG_ERR, msg)
                print("ERROR: " + msg, file=sys.stderr)
            self.ReconcileSubscribers(
                mailing_list, airtable_subscribers, ovh_subscribers, label=item
            )
        # print(json.dumps(ovh_subscribers, indent=4))
        # print(json.dumps(airtable_subscribers, indent=4))

    def DeleteMailingListSubscriber(self):

        ovh_subscribers = self.GetOvhMailingListSub(
            self.conf["delete_mailing_list_subscriber"]["ovh"]["mailingList"]
        )
        airtable_subscribers = self.GetAirtableData(
            self.conf["delete_mailing_list_subscriber"]["airtable"]
        )
        # print(json.dumps(ovh_subscribers, indent=4))
        # print(json.dumps(airtable_subscribers, indent=4))

        for email in ovh_subscribers:
            if any(d == email for d in airtable_subscribers):
                print("delete " + email)
                self.DeleteOvhMailinglistSubscriber(
                    self.conf["delete_mailing_list_subscriber"]["ovh"]["mailingList"],
                    email,
                )

    # Class "entry point"
    def Run(self):
        """Le passage, encadré par sa ligne de vie.

        Sans elle, un passage sans rien à faire n'écrit aucune ligne, exactement
        comme un passage qui n'a pas eu lieu. C'est ce qui a permis à la liste
        `membres` de supprimer seize adresses par jour pendant des mois sans que
        personne ne le voie : le seul modèle de détection était la plainte d'un
        adhérent, et aucune n'est arrivée.
        """
        self._compteurs = dict(self.COMPTEURS_NEUFS)
        try:
            self._executer()
            self._compteurs["statut"] = "ok"
        finally:
            self._signaler_fin_de_passage()

    def _signaler_fin_de_passage(self):
        """Ligne de vie en syslog et sur stdout.

        Ici stdout est redirigé vers mailinglist.log par le cron : la ligne y a
        sa place, c'est le fichier qu'on ouvre pour savoir ce qui s'est passé, et
        une anomalie de volume (1730 suppressions pour 30 ajouts) y devient
        lisible d'un coup d'œil au lieu de se noyer.
        """
        ligne = (
            "mailinglist_extracter: passage terminé "
            "statut={statut} listes={listes} ajouts={ajouts} "
            "suppressions={suppressions} erreurs={erreurs}".format(**self._compteurs)
        )
        syslog.syslog(syslog.LOG_INFO, ligne)
        print(ligne)

    def _executer(self):
        if "list_mailing_list" in self.conf:
            self.GetOvhAllMailingListSub(self.conf["list_mailing_list"])
        if "compare" in self.conf:
            self.CheckMailingListUsers()
        if "sync_mailing_list" in self.conf:
            self.SyncMailingList()
        if "sync_airtable_group" in self.conf:
            self.SyncAirtableGroup()
        if "auto_sync_mailing_list" in self.conf:
            self.AutoSyncMailingList()
        if "delete_mailing_list_subscriber" in self.conf:
            self.DeleteMailingListSubscriber()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--conf", help="path to a config file")
    args = parser.parse_args(argv)

    try:
        app = CheckOvhMailinglist(args.conf)
        app.Run()
        heartbeat.signaler("HEARTBEAT_URL_MAILINGLIST", succes=True)
        return 0
    except Exception as e:
        # Surface failures via stderr so cron's MAILTO catches them.
        # Stdout is redirected to a log file by the cron command, so the
        # noisy success path stays out of the inbox.
        syslog.syslog(syslog.LOG_ERR, "mailinglist_extracter failed: {}".format(e))
        print("ERROR: mailinglist_extracter failed: {}".format(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        heartbeat.signaler("HEARTBEAT_URL_MAILINGLIST", succes=False)
        return 1


if __name__ == "__main__":
    sys.exit(main())
