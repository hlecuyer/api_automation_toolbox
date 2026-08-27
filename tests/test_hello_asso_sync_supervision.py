"""Tests du signal de vie de hello_asso_sync.

Le défaut que ces tests décrivent : aujourd'hui, une journée sans nouvelle
adhésion et une journée où le script n'a pas tourné du tout produisent
exactement le même log, c'est-à-dire rien. `run()` écrit une ligne par adhésion
traitée et une par erreur, mais rien à la fin du passage. Le seul signal de vie
est le curseur `subscription_after` dans `config.json`, que personne ne va lire.

C'est cet angle mort qui a laissé la liste `membres` supprimer seize adresses
par jour pendant des mois sans que personne ne le voie.

Deux contraintes de forme, et elles ne sont pas cosmétiques :

- La ligne part en syslog et **jamais sur stdout**. Le cron de ce script ne
  redirige pas stdout et `MAILTO` est configuré : un `print()` deviendrait un
  mail quotidien, qu'on cesserait de lire en deux semaines. Le silence
  reviendrait par la fenêtre.
- La ligne sort dans un `finally`, donc aussi quand `run()` part par le retour
  anticipé du formulaire introuvable ou par une exception. Un passage qui plante
  doit se distinguer d'un passage sain, sinon le voyant vert ment.
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.hello_asso_sync import SyncHelloAsso
from src.models.user_subscription import UserSubscription


CURSEUR = "2024-01-01T00:00:00"


@pytest.fixture
def config_file(tmp_path):
    config = {
        "credentials": {
            "helloAsso": {"id": "test_id", "secret": "test_secret"},
            "ovh": {
                "endpoint": "ovh-eu",
                "ak": "test_ak",
                "as": "test_as",
                "ck": "test_ck",
            },
            "airtable": {"api_key": "test_airtable_key", "base_id": "test_base_id"},
        },
        "conf": {
            "helloAsso": {
                "api_url": "https://api.helloasso.com",
                "organization_name": "test_org",
                "form_name": "Test Form",
                "subscription_after": CURSEUR,
            },
            "cotisation_label": "test_label",
            "groupe": "test_group",
            "airtable": {"table_name": "Annuaire"},
            "ovh": {"mailing_list": {"name": "test_list", "domain": "test.org"}},
        },
    }
    chemin = tmp_path / "config.json"
    chemin.write_text(json.dumps(config), encoding="utf-8")
    return str(chemin)


@pytest.fixture
def sync(config_file):
    """Un SyncHelloAsso monté sans client réel : on teste la supervision,
    pas les intégrations, déjà couvertes ailleurs."""
    with patch.object(SyncHelloAsso, "_init_clients", lambda self: None):
        app = SyncHelloAsso(config_file)
    app.hello_asso_client = Mock()
    app.ovh_mailing_client = Mock()
    app.airtable_client = Mock()
    app.ovh_email_client = None
    app.logo_inline_images = None

    app.hello_asso_client.get_form_details.return_value = {
        "formType": "Membership",
        "formSlug": "test-slug",
    }
    app.hello_asso_client.get_form_items.return_value = []
    app.hello_asso_client.parse_items_to_subscriptions.return_value = []
    app.airtable_client.upsert_record.return_value = {"id": "rec123"}
    return app


def adhesion(email, annee=2024):
    return UserSubscription(
        email=email,
        first_name="Jean",
        last_name="Dupont",
        subscription_date=datetime(annee, 6, 15, 10, 30),
        cotisation="test_label",
        groupe="test_group",
    )


def ligne_de_fin(mock_syslog):
    """Retrouve la ligne de fin de passage parmi les appels syslog."""
    for appel in mock_syslog.syslog.call_args_list:
        message = appel[0][-1]
        if "passage terminé" in message:
            return message
    return None


# --- 1. le défaut décrit : zéro adhésion doit quand même laisser une trace ---


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_zero_adhesion_la_ligne_sort_quand_meme(mock_syslog, mock_heartbeat, sync):
    """Le test qui porte tout le sujet : sans lui, rien ne distingue une journée
    calme d'un script mort."""
    with patch.object(sync, "update_date_conf"):
        sync.run()

    ligne = ligne_de_fin(mock_syslog)
    assert ligne is not None
    assert "statut=ok" in ligne
    assert "vues=0" in ligne
    assert "traitées=0" in ligne


# --- 2. les compteurs ------------------------------------------------------


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_passage_nominal_compte_les_adhesions(mock_syslog, mock_heartbeat, sync):
    sync.hello_asso_client.parse_items_to_subscriptions.return_value = [
        adhesion("a@x.fr"),
        adhesion("b@x.fr"),
    ]

    with patch.object(sync, "update_date_conf"):
        sync.run()

    ligne = ligne_de_fin(mock_syslog)
    assert "statut=ok" in ligne
    assert "vues=2" in ligne
    assert "traitées=2" in ligne
    assert "erreurs=0" in ligne


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_adhesions_hors_date_comptees_en_vues_pas_en_traitees(
    mock_syslog, mock_heartbeat, sync
):
    sync.hello_asso_client.parse_items_to_subscriptions.return_value = [
        adhesion("recent@x.fr", annee=2024),
        adhesion("vieille@x.fr", annee=2020),  # antérieure au curseur
    ]

    with patch.object(sync, "update_date_conf"):
        sync.run()

    ligne = ligne_de_fin(mock_syslog)
    assert "vues=2" in ligne
    assert "traitées=1" in ligne


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_echec_airtable_compte_une_erreur_sans_faire_echouer_le_passage(
    mock_syslog, mock_heartbeat, sync
):
    """Le voyant dit « le passage a eu lieu », pas « tout est parfait ».
    Le compteur porte le reste."""
    sync.hello_asso_client.parse_items_to_subscriptions.return_value = [
        adhesion("ok@x.fr"),
        adhesion("ko@x.fr"),
    ]
    sync.airtable_client.upsert_record.side_effect = [{"id": "rec1"}, False]

    with patch.object(sync, "update_date_conf"):
        sync.run()

    ligne = ligne_de_fin(mock_syslog)
    assert "statut=ok" in ligne
    assert "traitées=1" in ligne
    assert "erreurs=1" in ligne
    mock_heartbeat.signaler.assert_called_once_with(
        "HEARTBEAT_URL_SYNC", succes=True
    )


# --- 3. le curseur, seul signal de vie existant, devient lisible ------------


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_le_curseur_figure_dans_la_ligne(mock_syslog, mock_heartbeat, sync):
    """Pour ne pas avoir à ouvrir config.json sur le serveur pour savoir
    jusqu'où la synchro est allée."""
    with patch.object(sync, "update_date_conf"):
        sync.run()

    assert f"curseur={CURSEUR}" in ligne_de_fin(mock_syslog)


# --- 4. un passage qui plante ne ressemble pas à un passage sain ------------


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_formulaire_introuvable_statut_echec(mock_syslog, mock_heartbeat, sync):
    """Retour anticipé de run() : la ligne doit sortir malgré tout."""
    sync.hello_asso_client.get_form_details.return_value = None

    sync.run()

    ligne = ligne_de_fin(mock_syslog)
    assert ligne is not None
    assert "statut=échec" in ligne
    mock_heartbeat.signaler.assert_called_once_with(
        "HEARTBEAT_URL_SYNC", succes=False
    )


@patch("src.hello_asso_sync.heartbeat")
@patch("src.hello_asso_sync.syslog")
def test_exception_statut_echec_et_exception_propagee(
    mock_syslog, mock_heartbeat, sync
):
    """L'exception doit continuer de remonter : c'est elle qui donne à cron
    son mail et son code retour non nul."""
    sync.hello_asso_client.get_form_items.side_effect = RuntimeError("API HS")

    with pytest.raises(RuntimeError):
        sync.run()

    ligne = ligne_de_fin(mock_syslog)
    assert ligne is not None
    assert "statut=échec" in ligne
    mock_heartbeat.signaler.assert_called_once_with(
        "HEARTBEAT_URL_SYNC", succes=False
    )


# --- 5. jamais sur stdout --------------------------------------------------


@patch("src.hello_asso_sync.heartbeat")
def test_rien_sur_stdout(mock_heartbeat, sync, capsys):
    """Le cron de ce script ne redirige pas stdout et MAILTO est configuré :
    une ligne sur stdout deviendrait un mail par jour."""
    with patch.object(sync, "update_date_conf"):
        sync.run()

    assert capsys.readouterr().out == ""
