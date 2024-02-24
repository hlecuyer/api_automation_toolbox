"""Module pushing data from helloasso to a (zapier) webhook"""

from datetime import datetime
import json
import sys
import syslog
import argparse
import requests
import ovh

# Class to sync data from hello-asso to airtable using zapier automation with webhooks


class SyncHelloAsso:
    """Class to handle helloasso data"""

    # init class loading config file value

    def __init__(self, config_path):
        self.conf_path = config_path
        try:
            with open(config_path, "r", encoding="utf-8") as jsonfile:
                config = json.load(jsonfile)
                # store the wall config in this var to update the config file
                self.conf_global = config
                self.conf = config["conf"]
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, f"Failed to load configuration: {e}")
            raise e
        # retreive api hello-asso api token to perform authenticate queries
        token = self.__authenticate()
        # set hearders with api token
        self.headers = {
            "Accept": "application/json",
            "Authorization": "Bearer " + token,
        }
        self.ovh_client = ovh.Client(
            endpoint="ovh-eu",
            application_key=self.conf_global["credentials"]["ovh"]["ak"],
            application_secret=self.conf_global["credentials"]["ovh"]["as"],
            consumer_key=self.conf_global["credentials"]["ovh"]["ck"],
        )

    # Call hello-asso authentication api end-point to retrieve api token
    def __authenticate(self):
        """Function authenticating helloasso client."""

        headers = {"content-type": "application/x-www-form-urlencoded"}

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.conf_global["credentials"]["helloAsso"]["id"],
            "client_secret": self.conf_global["credentials"]["helloAsso"]["secret"],
        }

        url = "{}/oauth2/token".format(self.conf["helloAsso"]["api_url"])
        r = requests.post(url, data=payload, headers=headers, timeout=10)

        try:
            access_token = r.json()["access_token"]
            return access_token
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                "Something went wrong while authenticating to helloasso: {}".format(e),
            )
            raise e

    def get_form_details(self, name):
        """Find formular detail usig formular name (needed to get
        formular data using form_type and form_slug avriables)"""

        payload = {"pageSize": "100"}

        url = "{}/v5/organizations/{}/forms".format(
            self.conf["helloAsso"]["api_url"],
            self.conf["helloAsso"]["organization_name"],
        )
        r = requests.get(url, params=payload, headers=self.headers, timeout=10)

        data = r.json()["data"]

        for item in data:
            if item["title"] == name:
                return item
        return {}

    def get_form_data(self, form_type, form_slug):
        """Function retrieve formular data using form_type and form_slug"""

        data = []
        total_pages = 2
        current_page = 1
        while total_pages > current_page:
            payload = {
                "pageIndex": current_page,
                "pageSize": "100",
                "withDetails": True,
            }
            url = "{}/v5/organizations/{}/forms/{}/{}/items".format(
                self.conf["helloAsso"]["api_url"],
                self.conf["helloAsso"]["organization_name"],
                form_type,
                form_slug,
            )
            r = requests.get(url, params=payload, headers=self.headers, timeout=10)
            resp_json = r.json()
            data.extend(resp_json["data"])
            total_pages = resp_json["pagination"]["totalPages"]
            current_page += current_page
        return data

    def update_ovh_mailing_list(self, mail):
        """Function to add a subscriber to ovh mailing list"""
        try:
            self.ovh_client.post(
                "/email/domain/{}/mailingList/{}/subscriber".format(
                    self.conf["ovh"]["mailing_list"]["domain"],
                    self.conf["ovh"]["mailing_list"]["name"],
                ),
                email=mail,
            )
            # print(result)
            # print(json.dumps(result, indent=4))
        except ovh.exceptions.ResourceConflictError as e:
            syslog.syslog(
                syslog.LOG_INFO,
                "The subscriber {} already exists in this mailing list. Details: {}".format(
                    mail, e
                ),
            )

    def sync_user_to_airtable(self, data, date="2000-01-01T00:00:00"):
        """Function that Extract email, first name and last name from hello asso data and send it
        to airtable if subscription was made after "subscription_after" variable value
        """
        users = []
        headers = {"content-type": "application/json"}

        for item in data:
            if item["state"] == "Processed":
                if item["payer"]["email"] not in users:
                    tmp = {
                        "email": item["payer"]["email"],
                        "firstName": item["user"]["firstName"],
                        "lastName": item["user"]["lastName"],
                        "date": item["order"]["date"],
                        "cotisation": self.conf["cotisation_label"],
                    }
                    # print(tmp)

                    for fields in item["customFields"]:
                        tmp[fields["name"]] = fields["answer"]

                    for key, value in self.conf["helloAsso"]["default"].items():
                        if key not in tmp:
                            tmp[key] = value

                    date_str = tmp["date"].split("+")[0].split(".")[0]
                    date_subscription = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                    if self.conf["helloAsso"]["first_sub_field"] in tmp:
                        if tmp[self.conf["helloAsso"]["first_sub_field"]] == "Oui":
                            tmp[self.conf["helloAsso"]["first_sub_field"]] = (
                                date_subscription.strftime("%Y")
                            )
                    if self.conf["helloAsso"]["name_field"] in tmp:
                        tmp[self.conf["helloAsso"]["name_field"]] = tmp[
                            self.conf["helloAsso"]["name_field"]
                        ].upper()

                    date_filter = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S")
                    if date_subscription >= date_filter:
                        print("new record")
                        print(json.dumps(tmp))
                        r = requests.post(
                            self.conf["webhook_url"],
                            data=json.dumps(tmp),
                            headers=headers,
                            timeout=10,
                        )
                        print(r)
                        if r.status_code != 200:
                            syslog.syslog(
                                syslog.LOG_ERR,
                                "Request to zapier failed with status code {}".format(
                                    r.status
                                ),
                            )
                            sys.exit(-1)
                        self.update_ovh_mailing_list(item["payer"]["email"])
                    users.append(tmp)

    # update subscription_after field with today's date (to avoid syncing several
    # time the same user)
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
        """Class "entry point" """
        form_detail = self.get_form_details(self.conf["helloAsso"]["form_name"])
        form_data = self.get_form_data(form_detail["formType"], form_detail["formSlug"])
        try:
            date = self.conf["helloAsso"]["subscription_after"]
            self.sync_user_to_airtable(form_data, date)
            self.update_date_conf()
        except KeyError:
            self.sync_user_to_airtable(form_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--conf", help="path to a config file")
    args = parser.parse_args()

    helloAsso = SyncHelloAsso(args.conf)

    helloAsso.run()
#   standalone call to functio for testing purpose
#    helloAsso.UpdateDateConf()
