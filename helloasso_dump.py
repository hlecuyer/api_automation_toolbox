import requests
import syslog
import ovh
import json
import string
import os
from datetime import datetime
import json
import argparse

# Class to sync data from hello-asso to airtable using zapier automation with webhooks
class SyncHelloAsso:
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
            syslog.syslog(syslog.LOG_ERR, 'Failed to load configuration: {}'.format(e))
            raise e
        # retreive api hello-asso api token to perform authenticate queries
        token = self.Authenticate()
        # set hearders with api token
        self.headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer '+token,
        }
        self.ovh_client = ovh.Client(
            endpoint='ovh-eu',
            application_key=self.conf_global["credentials"]["ovh"]["ak"],
            application_secret=self.conf_global["credentials"]["ovh"]["as"],
            consumer_key=self.conf_global["credentials"]["ovh"]["ck"]
        )

    # Call hello-asso authentication api end-point to retrieve api token
    def Authenticate(self):
        headers = {
          'content-type': 'application/x-www-form-urlencoded'
        }

        payload = {
            'grant_type': 'client_credentials',
            'client_id': self.conf_global["credentials"]["helloAsso"]["id"],
            'client_secret': self.conf_global["credentials"]["helloAsso"]["secret"]
        }

        url = '{}/oauth2/token'.format(self.conf["helloAsso"]["api_url"])
        r = requests.post(url, data=payload, headers=headers)

        try:
            access_token = r.json()["access_token"]
            return access_token
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, "Something went wrong while authenticating to helloasso: {}".format(e))
            exit(-1)

    # Find formular detail usig formular name (needed to get formular data using formType and formSlug avriables)
    def GetFormDetails(self, name):
        payload = {
            'pageSize': '100'
        }

        url = '{}/v5/organizations/{}/forms'.format(self.conf["helloAsso"]["api_url"],self.conf["helloAsso"]["organization_name"])
        r = requests.get(url, params=payload, headers=self.headers)

        data = r.json()["data"]

        for item in data:
            if item["title"] == name:
                return item
        return {}

    # retrieve formular data using formType and formSlug
    def GetFormData(self, formType, formSlug):
        data = []
        totalPages=2
        currentPage=1
        while totalPages>currentPage:
            payload = {
                'pageIndex': currentPage,
                'pageSize': '100'
            }
            url = '{}/v5/organizations/{}/forms/{}/{}/items'.format(self.conf["helloAsso"]["api_url"],self.conf["helloAsso"]["organization_name"],formType,formSlug)
            r = requests.get(url, params=payload, headers=self.headers)
            resp_json = r.json()
            data.extend(resp_json["data"])
            totalPages=resp_json["pagination"]["totalPages"]
            currentPage+=currentPage
        return data

    def UpdateOvhMailingList(self, mail):
        try:
            result = self.ovh_client.post('/email/domain/{}/mailingList/{}/subscriber'.format(self.conf["ovh"]["mailingList"]["domain"],self.conf["ovh"]["mailingList"]["name"]),
                email=mail
                )
            # print(result)
            # print(json.dumps(result, indent=4))
        except ovh.exceptions.ResourceConflictError as e:
            syslog.syslog(syslog.LOG_INFO, "The subscriber {} already exists in this mailing list. Details: {}".format(mail, e))

    # Extract email, first name and last name from hello asso data and send it
    # to airtable if subscription was made after "subscriptionAfter" variable value
    def SyncUserToAirtable(self, data, date="2000-01-01"):
        users = []
        headers = {
          'content-type': 'application/json'
        }

        for item in data:
            if item["state"] == "Processed":
                if item["payer"]["email"] not in users:
                    try:
                        print("customFields: {}".format(item["customFields"]))
                    except KeyError:
                        pass
                    tmp = { "email": item["payer"]["email"], "firstName":  item["user"]["firstName"], "lastName":  item["user"]["lastName"], "date": item["order"]["date"], "cotisation": self.conf["cotisation_label"] }

                    date_str = tmp["date"].split("+")[0].split(".")[0]
                    date_subscription = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                    date_filter = datetime.strptime(date, "%Y-%m-%dT%H:%M:%S")
                    if date_subscription >=  date_filter:
                        print("new record")
                        print(item)
                        r = requests.post(self.conf["webhook_url"], data=json.dumps(tmp),  headers=headers)
                        print(r)
                        if r.status_code != 200:
                           syslog.syslog(syslog.LOG_ERR, "Request to zapier failed with status code {}".format(r.status) )
                           exit(-1)
                        self.UpdateOvhMailingList(item["payer"]["email"])
                    users.append(tmp)

    # update subscriptionAfter field with today's date (to avoid syncing several
    # time the same user)
    def UpdateDateConf(self):
        try:
            with open(self.conf_path, "w", encoding='utf8') as jsonfile:
                self.conf_global["conf"]["helloAsso"]["subscriptionAfter"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                json.dump(self.conf_global, jsonfile, indent=2, ensure_ascii=False)
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR, "Failed to update config file with new date {}".format(e) )
            raise e


    # Class "entry point"
    def Run(self):
        formDetail = self.GetFormDetails(self.conf["helloAsso"]["formName"])
        formData = self.GetFormData(formDetail["formType"], formDetail["formSlug"])
        try:
            date = self.conf["helloAsso"]["subscriptionAfter"]
            self.SyncUserToAirtable(formData, date)
            self.UpdateDateConf()
        except KeyError:
            self.SyncUserToAirtable(formData)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--conf', help='path to a config file')
    args = parser.parse_args()

    helloAsso = SyncHelloAsso(args.conf)

    helloAsso.Run()
#   standalone call to functio for testing purpose
#    helloAsso.UpdateDateConf()

