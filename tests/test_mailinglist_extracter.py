"""Regression-safety tests for CheckOvhMailinglist (mailinglist_extracter).

Tests assert on boundary library calls (ovh.Client constructor, the
AddOvh/DeleteOvh helpers) so they are insensitive to whether credentials
arrive through the JSON config or via environment variables. Post-refactor,
credentials live in .env and the JSON config holds only the operational
`conf` block.
"""

import json

import pytest
from unittest.mock import patch, MagicMock

from src.mailinglist_extracter import CheckOvhMailinglist


@pytest.fixture
def env_credentials(monkeypatch):
    """Inject credentials into the environment as the production deploy does."""
    monkeypatch.setenv("OVH_APP_KEY", "ak_test")
    monkeypatch.setenv("OVH_APP_SECRET", "as_test")
    monkeypatch.setenv("OVH_CONSUMER_KEY", "ck_test")
    monkeypatch.setenv("AIRTABLE_API_KEY", "tok_test")


@pytest.fixture
def config_path(tmp_path):
    """Operational config without credentials (creds come from env)."""
    config = {
        "conf": {
            "auto_sync_mailing_list": {
                "base_id": "appBASE",
                "table_id": "tblTABLE",
                "ovh_domain": "example.org",
                "label_field": "Groupe",
                "mail_field": "Email",
                "select_field": [{"name": "Groupe"}],
            }
        }
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))
    return str(p)


@patch("src.mailinglist_extracter.ovh.Client")
def test_init_creates_ovh_client_with_credentials(
    mock_ovh_client, env_credentials, config_path
):
    CheckOvhMailinglist(config_path)
    mock_ovh_client.assert_called_once_with(
        endpoint="ovh-eu",
        application_key="ak_test",
        application_secret="as_test",
        consumer_key="ck_test",
    )


@patch("src.mailinglist_extracter.ovh.Client")
def test_init_stores_airtable_token(_mock_ovh_client, env_credentials, config_path):
    app = CheckOvhMailinglist(config_path)
    assert app.airtable_key == "tok_test"


@patch("src.mailinglist_extracter.ovh.Client")
def test_auto_sync_adds_missing_subscribers(
    _mock_ovh_client, env_credentials, config_path
):
    app = CheckOvhMailinglist(config_path)
    app.GetAirtableData = MagicMock(side_effect=[["A"], [["x@y", "z@y"]]])
    app.GetOvhMailingListSub = MagicMock(return_value=["x@y"])
    app.AddOvhMailingListSubscriber = MagicMock()
    app.DeleteOvhMailinglistSubscriber = MagicMock()

    app.AutoSyncMailingList()

    app.AddOvhMailingListSubscriber.assert_called_once_with(
        {"name": "A", "domain": "example.org"}, "z@y"
    )
    app.DeleteOvhMailinglistSubscriber.assert_not_called()


@patch("src.mailinglist_extracter.ovh.Client")
def test_auto_sync_removes_extra_subscribers(
    _mock_ovh_client, env_credentials, config_path
):
    app = CheckOvhMailinglist(config_path)
    app.GetAirtableData = MagicMock(side_effect=[["A"], [["x@y"]]])
    app.GetOvhMailingListSub = MagicMock(return_value=["x@y", "z@y"])
    app.AddOvhMailingListSubscriber = MagicMock()
    app.DeleteOvhMailinglistSubscriber = MagicMock()

    app.AutoSyncMailingList()

    app.DeleteOvhMailinglistSubscriber.assert_called_once_with(
        {"name": "A", "domain": "example.org"}, "z@y"
    )
    app.AddOvhMailingListSubscriber.assert_not_called()


@patch("src.mailinglist_extracter.ovh.Client")
def test_auto_sync_handles_missing_ovh_list_gracefully(
    _mock_ovh_client, env_credentials, config_path
):
    import ovh as ovh_module

    app = CheckOvhMailinglist(config_path)
    app.GetAirtableData = MagicMock(side_effect=[["A"], [["x@y"]]])
    app.GetOvhMailingListSub = MagicMock(
        side_effect=ovh_module.exceptions.ResourceNotFoundError("no such list")
    )
    app.AddOvhMailingListSubscriber = MagicMock()
    app.DeleteOvhMailinglistSubscriber = MagicMock()

    app.AutoSyncMailingList()  # must not raise

    app.AddOvhMailingListSubscriber.assert_called_once_with(
        {"name": "A", "domain": "example.org"}, "x@y"
    )
    app.DeleteOvhMailinglistSubscriber.assert_not_called()
