import requests
import syslog
import ovh
from pyairtable import Api
from pyairtable.formulas import match
import json
import string
from datetime import datetime
import json
import argparse
import os


# Class to sync data from hello-asso to airtable using zapier automation with webhooks
class CheckOvhMailinglist:
    # init class loading config file value
    def __init__(self, config_path):
        self.conf_path = config_path
        try:
            with open(config_path, "r") as jsonfile:
                config = json.load(jsonfile)
                # store the wall config in this var to update the config file
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
        self.airtable_key = self.conf_global["credentials"]["airtable"]["token"]

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

        for email in ovh_subscribers:
            if not any(d == email for d in airtable_subscribers):
                print("delete " + email)
                self.DeleteOvhMailinglistSubscriber(mailing_list, email)

        for email in airtable_subscribers:
            if email not in ovh_subscribers:
                print("add " + email)
                self.AddOvhMailingListSubscriber(mailing_list, email)

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
            try:
                ovh_subscribers.extend(self.GetOvhMailingListSub(mailing_list))
            except ovh.exceptions.ResourceNotFoundError as e:
                syslog.syslog(
                    syslog.LOG_ERR,
                    "The mailing list {} does not exists".format(mailing_list),
                )
            for email in ovh_subscribers:
                if not any(d == email for d in airtable_subscribers):
                    print("delete " + email + " from " + item)
                    self.DeleteOvhMailinglistSubscriber(mailing_list, email)
            # print("Add to " + item + " :")
            for email in airtable_subscribers:
                if email not in ovh_subscribers:
                    # continue
                    print("add " + email + " in " + item)
                    self.AddOvhMailingListSubscriber(mailing_list, email)
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--conf", help="path to a config file")
    args = parser.parse_args()

    app = CheckOvhMailinglist(args.conf)

    app.Run()
#   standalone call to functio for testing purpose
#    helloAsso.UpdateDateConf()
