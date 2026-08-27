"""Filet sur le canal chèque : détecter un adhérent à jour non rattaché au groupe.

Le 27/08/2026, on a découvert par hasard qu'Eric Gaillard avait adhéré le
18/02/2026 par chèque et n'avait été rattaché à aucun groupe : ni liste de
diffusion, ni rien, pendant six mois. Personne ne pouvait le voir, parce qu'une
absence ne fait pas de bruit.

La synchronisation HelloAsso, elle, ne rate personne : 85 fiches « Payé 2026 »,
85 rattachées. Le trou est le paiement par chèque, qui se saisit à la main dans
Airtable et court-circuite toute l'automatisation. Sur trois chèques, un est
passé à travers.

Ce contrôle compte, à chaque passage, les adhérents à jour de cotisation qui ne
sont rattachés à aucun groupe d'adhérents, et sort le compte dans la ligne de
vie. Il aurait affiché « non_rattachés=1 » tous les jours depuis février.

Deux propriétés non négociables, et ce sont celles que ces tests gardent :

- **l'année n'est pas écrite en dur** : elle se déduit de `cotisation_label`,
  sinon le contrôle devient faux au 1er janvier sans que personne ne le voie ;
- **le contrôle ne fait jamais échouer la synchronisation** qu'il surveille.
  Un filet qui fait tomber le trapéziste ne sert à rien.
"""

import json
from unittest.mock import Mock, patch

import pytest

from src.hello_asso_sync import SyncHelloAsso


@pytest.fixture
def config_file(tmp_path):
    config = {
        "credentials": {
            "helloAsso": {"id": "id", "secret": "secret"},
            "ovh": {"endpoint": "ovh-eu", "ak": "ak", "as": "as", "ck": "ck"},
            "airtable": {"api_key": "key", "base_id": "base"},
        },
        "conf": {
            "helloAsso": {
                "api_url": "https://api.helloasso.com",
                "organization_name": "org",
                "form_name": "Form",
                "subscription_after": "2024-01-01T00:00:00",
            },
            "cotisation_label": "Payé 2026",
            "groupe": "Adhérent·es la Coop des Communs",
            "airtable": {"table_name": "Annuaire"},
            "ovh": {"mailing_list": {"name": "membres", "domain": "test.org"}},
        },
    }
    chemin = tmp_path / "config.json"
    chemin.write_text(json.dumps(config), encoding="utf-8")
    return str(chemin)


@pytest.fixture
def sync(config_file):
    with patch.object(SyncHelloAsso, "_init_clients", lambda self: None):
        app = SyncHelloAsso(config_file)
    app.hello_asso_client = Mock()
    app.ovh_mailing_client = Mock()
    app.airtable_client = Mock()
    app.ovh_email_client = None
    app.logo_inline_images = None
    app.hello_asso_client.get_form_details.return_value = {
        "formType": "Membership",
        "formSlug": "slug",
    }
    app.hello_asso_client.get_form_items.return_value = []
    app.hello_asso_client.parse_items_to_subscriptions.return_value = []
    app.airtable_client.list_records.return_value = []
    return app


def formule(sync):
    return sync.airtable_client.list_records.call_args[1]["filter_by_formula"]


def ligne_de_fin(mock_syslog):
    for appel in mock_syslog.syslog.call_args_list:
        message = appel[0][-1]
        if "passage terminé" in message:
            return message
    return None


# --- 1. l'année se déduit, elle ne s'écrit pas ----------------------------


def test_l_annee_vient_de_cotisation_label(sync):
    """Écrite en dur, la formule deviendrait fausse au 1er janvier, en silence."""
    sync._compter_non_rattaches()

    f = formule(sync)
    assert "2026" in f
    assert "Cotisation LCDC" in f


def test_annee_suit_le_changement_de_label(sync):
    sync.conf["cotisation_label"] = "Payé 2027"

    sync._compter_non_rattaches()

    assert "2027" in formule(sync)
    assert "2026" not in formule(sync)


def test_le_groupe_vient_de_la_configuration(sync):
    sync._compter_non_rattaches()

    assert "Adhérent·es la Coop des Communs" in formule(sync)
    assert "Groupe(s)" in formule(sync)


def test_le_cheque_est_couvert_comme_le_paiement_en_ligne(sync):
    """La formule cherche l'année dans la cotisation, pas le libellé exact :
    « Payé 2026 » et « paiement par chèque 2026 » sont donc tous deux pris."""
    sync._compter_non_rattaches()

    f = formule(sync)
    assert "Payé 2026" not in f, "un libellé exact raterait les paiements par chèque"


# --- 2. le compteur remonte dans la ligne de vie --------------------------


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_le_compte_figure_dans_la_ligne_de_vie(mock_syslog, mock_heartbeat, sync):
    sync.airtable_client.list_records.return_value = [{"id": "rec1"}, {"id": "rec2"}]

    with patch.object(sync, "update_date_conf"):
        sync.run()

    assert "non_rattachés=2" in ligne_de_fin(mock_syslog)


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_zero_non_rattache_se_dit_aussi(mock_syslog, mock_heartbeat, sync):
    """Un zéro explicite vaut mieux qu'un silence : c'est tout le sujet."""
    with patch.object(sync, "update_date_conf"):
        sync.run()

    assert "non_rattachés=0" in ligne_de_fin(mock_syslog)


# --- 3. le filet ne fait pas tomber le trapéziste -------------------------


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_une_erreur_du_controle_ne_fait_pas_echouer_le_passage(
    mock_syslog, mock_heartbeat, sync
):
    sync.airtable_client.list_records.side_effect = RuntimeError("Airtable HS")

    with patch.object(sync, "update_date_conf"):
        sync.run()  # ne doit pas lever

    ligne = ligne_de_fin(mock_syslog)
    assert "statut=ok" in ligne
    assert "non_rattachés=?" in ligne, "l'inconnu doit se dire, pas se taire"
    mock_heartbeat.signaler.assert_called_once_with("HEARTBEAT_URL_SYNC", succes=True)


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_le_controle_ne_lit_que_lui_meme(mock_syslog, mock_heartbeat, sync):
    """Strictement en lecture : aucune écriture ne doit partir du contrôle."""
    with patch.object(sync, "update_date_conf"):
        sync.run()

    sync.airtable_client.create_record.assert_not_called()
    sync.airtable_client.update_record.assert_not_called()
