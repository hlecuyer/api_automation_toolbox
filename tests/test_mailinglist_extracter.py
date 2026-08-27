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
    _mock_ovh_client, env_credentials, config_path, capsys
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
    # The non-fatal "list does not exist" warning must reach stderr so
    # cron's MAILTO surfaces it (syslog alone is invisible to the operator).
    assert "ERROR" in capsys.readouterr().err


def test_main_returns_nonzero_on_failure(tmp_path, capsys):
    """Top-level catch-all: any exception → stderr message + non-zero exit."""
    from src.mailinglist_extracter import main

    bogus = str(tmp_path / "does-not-exist.json")
    rc = main(["-c", bogus])

    assert rc == 1
    assert "ERROR" in capsys.readouterr().err


# --- Signal de vie ---------------------------------------------------------
#
# Le défaut : un passage sans rien à faire n'écrit aucune ligne, exactement
# comme un passage qui n'a pas eu lieu. C'est ce qui a permis à la liste
# `membres` de supprimer seize adresses par jour pendant des mois sans que
# personne ne le voie : le seul modèle de détection était la plainte d'un
# adhérent, et aucune n'est arrivée.
#
# Ici, contrairement à hello_asso_sync, stdout est redirigé vers
# mailinglist.log par le cron. La ligne y va donc aussi : c'est le fichier
# qu'on ouvre quand on cherche ce qui s'est passé, et une anomalie de volume
# (1730 delete pour 30 add) y devient lisible d'un coup d'œil.


def ligne_de_fin(mock_syslog):
    for appel in mock_syslog.syslog.call_args_list:
        message = appel[0][-1]
        if "passage terminé" in message:
            return message
    return None


@patch("src.mailinglist_extracter.heartbeat")
@patch("src.mailinglist_extracter.syslog")
@patch("src.mailinglist_extracter.ovh.Client")
def test_ligne_de_fin_compte_ajouts_et_suppressions(
    mock_ovh_client, mock_syslog, mock_heartbeat, env_credentials, config_path, capsys
):
    app = CheckOvhMailinglist(config_path)
    app.GetAirtableData = MagicMock(side_effect=[["listeA"], [["garde@x.fr"]]])
    app.GetOvhMailingListSub = MagicMock(
        return_value=["garde@x.fr", "aretirer@x.fr", "aussi@x.fr"]
    )
    app.AddOvhMailingListSubscriber = MagicMock()
    app.DeleteOvhMailinglistSubscriber = MagicMock()

    app.Run()

    ligne = ligne_de_fin(mock_syslog)
    assert ligne is not None
    assert "statut=ok" in ligne
    assert "listes=1" in ligne
    assert "ajouts=0" in ligne
    assert "suppressions=2" in ligne
    assert "erreurs=0" in ligne
    # stdout est redirigé vers mailinglist.log : la ligne doit y figurer aussi
    assert "passage terminé" in capsys.readouterr().out


@patch("src.mailinglist_extracter.heartbeat")
@patch("src.mailinglist_extracter.syslog")
@patch("src.mailinglist_extracter.ovh.Client")
def test_liste_absente_compte_une_erreur(
    mock_ovh_client, mock_syslog, mock_heartbeat, env_credentials, config_path
):
    """Le passage va au bout, mais il ne s'est pas passé ce qu'on croyait."""
    import ovh as ovh_module

    app = CheckOvhMailinglist(config_path)
    app.GetAirtableData = MagicMock(side_effect=[["listeA"], [["x@y.fr"]]])
    app.GetOvhMailingListSub = MagicMock(
        side_effect=ovh_module.exceptions.ResourceNotFoundError("no such list")
    )
    app.AddOvhMailingListSubscriber = MagicMock()
    app.DeleteOvhMailinglistSubscriber = MagicMock()

    app.Run()

    ligne = ligne_de_fin(mock_syslog)
    assert "erreurs=1" in ligne


@patch("src.mailinglist_extracter.heartbeat")
@patch("src.mailinglist_extracter.ovh.Client")
def test_main_succes_ping_le_heartbeat(
    mock_ovh_client, mock_heartbeat, env_credentials, config_path
):
    from src.mailinglist_extracter import main

    with patch.object(CheckOvhMailinglist, "Run", lambda self: None):
        rc = main(["-c", config_path])

    assert rc == 0
    mock_heartbeat.signaler.assert_called_once_with(
        "HEARTBEAT_URL_MAILINGLIST", succes=True
    )


@patch("src.mailinglist_extracter.heartbeat")
def test_main_echec_ping_le_heartbeat_en_echec(mock_heartbeat, tmp_path, capsys):
    """Un passage qui plante ne doit pas ressembler à un passage sain."""
    from src.mailinglist_extracter import main

    rc = main(["-c", str(tmp_path / "does-not-exist.json")])

    assert rc == 1
    mock_heartbeat.signaler.assert_called_once_with(
        "HEARTBEAT_URL_MAILINGLIST", succes=False
    )
