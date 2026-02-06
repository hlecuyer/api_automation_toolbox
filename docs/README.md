# HelloAsso Automation Tool

The HelloAsso Automation Tool is a Python application that extracts data from the HelloAsso API and syncs it directly to Airtable. It also updates an OVH mailing list using the OVH API.

## Description

The HelloAsso Automation Tool queries the HelloAsso API to retrieve subscribers who have completed payment on the form specified in the configuration file. It then sends subscriber information directly to an Airtable database.

If passing data to Airtable succeeds, the script then updates an OVH mailing list using the OVH API.

## Architecture

The project follows a clean architecture pattern with separation of concerns:

- **Models** (`src/models/`): Typed data classes
  - `UserSubscription`: Represents a user subscription with all fields from HelloAsso

- **Clients** (`src/clients/`):
  - `HelloAssoClient`: Handles HelloAsso API authentication and data retrieval
  - `OVHMailingClient`: Manages OVH mailing list subscriptions
  - `AirtableClient`: Direct integration with Airtable API for user directory management
  - `OVHEmailClient`: Sends confirmation emails via OVH

- **Orchestrator** (`src/hello_asso_sync.py`): Coordinates all clients to execute the full workflow   

## Requirements

To use the HelloAsso Automation Tool, you must have the following Python packages installed:

- requests
- ovh

These packages can be installed using your package manager or (evil) pip. You can find ovh package [here](https://github.com/ovh/python-ovh/releases/)

You need to retrieve your HelloAsso and Ovh api credentials.

## Installation

To install the HelloAsso Automation Tool, follow these steps:

1. Clone the repository: `git clone https://github.com/chadek/helloasso_automation_tool.git`
2. Change to the repository directory: `cd helloasso_automation_tool`
3. Install required Python packages (requests, ovh)

## Configuration

The HelloAsso Automation Tool uses a configuration file to specify the parameters needed to connect to the HelloAsso and OVH APIs. A sample of the configuration file is stored at [https://github.com/chadek/helloasso_automation_tool/blob/main/hello-asso-automation-conf.json](https://github.com/chadek/helloasso_automation_tool/blob/main/hello-asso-automation-conf.json).

The following parameters are stored in the configuration file:

### Credentials

| Parameter | Description |
|-----------|-------------|
| `helloAsso` -> `secret`  | Your HelloAsso API key |
| `helloAsso` -> `id` | The ID of your HelloAsso association |
| `ovh` -> `ak` | Your OVH API application key |
| `ovh` -> `as` | Your OVH API application secret |
| `ovh` -> `ac` | Your OVH API consumer key |
| `ovh` -> `endpoint` | The endpoint for your OVH API |

### Conf

| Parameter | Description |
|-----------|-------------|
| `helloAsso` -> `api_url` | The HelloAsso api URL |
| `helloAsso` -> `organization_name` | The HelloAsso organisation name you want to work with |
| `helloAsso` -> `formName` | The HelloAsso the formular name you want to extract |
| `helloAsso` -> `subscriptionAfter` | (Optional, default value: 2000-01-01) Date after which the script will start to search for new HelloAsso subscribers   |
| `cotisation_label` | A label to add to user data sent to zapier |
| `ovh` -> `mailingList` -> `name` | The ovh mailing list name to update with new subcribers mail |
| `ovh` -> `mailingList` -> `domain` | The ovh domain name of the mailing list |

## Running

To run the HelloAsso Automation Tool, execute the module from the repository root:

```bash
python -m src.hello_asso_sync path/to/hello-asso-automation-conf.json
```

Or using the virtual environment:

```bash
.venv/bin/python -m src.hello_asso_sync hello-asso-automation-conf.json
```

This will:
1. Authenticate with HelloAsso API
2. Retrieve new subscriptions from the specified form
3. Sync each subscription directly to Airtable
4. Add subscribers to the OVH mailing list
5. Update the configuration file with the latest sync date
