"""Tests du dead man's switch (src/heartbeat.py).

Une ligne de log « ça a tourné » ne détecte rien toute seule : personne ne va la
lire. Ce qui détecte, c'est un service externe qui s'alarme quand le ping de fin
de passage n'arrive pas. C'est le seul mécanisme qui voit aussi la machine
éteinte, le cron supprimé et le réseau coupé.

Deux propriétés comptent plus que le reste, et ce sont celles qui font échouer
les monitorings mal écrits :

1. Sans URL configurée, aucun appel réseau. C'est ce qui garde les tests et le
   poste de dev silencieux, et ce qui rend la fonction inerte par défaut.
2. Un ping qui échoue ne fait jamais tomber la synchro qu'il surveille. Le
   monitoring est subordonné au travail, pas l'inverse.
"""

from unittest.mock import patch

import pytest
import requests

from src.heartbeat import signaler


URL = "https://hc.example.org/ping/8f2c1d4e"


# --- 1. inerte tant que rien n'est configuré ------------------------------


@patch("src.heartbeat.requests.get")
def test_sans_variable_environnement_aucun_appel(mock_get, monkeypatch):
    monkeypatch.delenv("HEARTBEAT_URL_SYNC", raising=False)

    signaler("HEARTBEAT_URL_SYNC")

    mock_get.assert_not_called()


@patch("src.heartbeat.requests.get")
def test_variable_vide_aucun_appel(mock_get, monkeypatch):
    monkeypatch.setenv("HEARTBEAT_URL_SYNC", "")

    signaler("HEARTBEAT_URL_SYNC")

    mock_get.assert_not_called()


# --- 2. le ping lui-même ---------------------------------------------------


@patch("src.heartbeat.requests.get")
def test_succes_ping_url_exacte_avec_timeout(mock_get, monkeypatch):
    monkeypatch.setenv("HEARTBEAT_URL_SYNC", URL)

    signaler("HEARTBEAT_URL_SYNC")

    mock_get.assert_called_once_with(URL, timeout=5)


@patch("src.heartbeat.requests.get")
def test_echec_ping_url_suffixee_fail(mock_get, monkeypatch):
    """Un passage qui plante ne doit pas ressembler à un passage sain :
    sinon on a construit un voyant vert qui ment."""
    monkeypatch.setenv("HEARTBEAT_URL_SYNC", URL)

    signaler("HEARTBEAT_URL_SYNC", succes=False)

    mock_get.assert_called_once_with(URL + "/fail", timeout=5)


# --- 3. le monitoring ne fait jamais tomber ce qu'il surveille -------------


@patch("src.heartbeat.syslog")
@patch("src.heartbeat.requests.get", side_effect=requests.Timeout("trop long"))
def test_timeout_navale_lexception_et_trace(mock_get, mock_syslog, monkeypatch):
    monkeypatch.setenv("HEARTBEAT_URL_SYNC", URL)

    signaler("HEARTBEAT_URL_SYNC")  # ne doit pas lever

    assert mock_syslog.syslog.called
    niveau, message = mock_syslog.syslog.call_args[0]
    assert niveau is mock_syslog.LOG_WARNING
    assert "heartbeat" in message.lower()


@patch("src.heartbeat.syslog")
@patch(
    "src.heartbeat.requests.get",
    side_effect=requests.ConnectionError("dns mort"),
)
def test_erreur_reseau_navale_lexception(mock_get, mock_syslog, monkeypatch):
    monkeypatch.setenv("HEARTBEAT_URL_SYNC", URL)

    signaler("HEARTBEAT_URL_SYNC")  # ne doit pas lever

    assert mock_syslog.syslog.called


@patch("src.heartbeat.requests.get")
def test_reponse_500_navale_lexception(mock_get, monkeypatch):
    """Le service de monitoring peut être en panne. Ça ne regarde pas la synchro."""
    monkeypatch.setenv("HEARTBEAT_URL_SYNC", URL)
    mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("500")

    signaler("HEARTBEAT_URL_SYNC")  # ne doit pas lever


# --- 4. chaque script a sa propre clé -------------------------------------


@patch("src.heartbeat.requests.get")
def test_cle_environnement_respectee(mock_get, monkeypatch):
    monkeypatch.setenv("HEARTBEAT_URL_SYNC", URL)
    monkeypatch.setenv("HEARTBEAT_URL_MAILINGLIST", "https://hc.example.org/ping/autre")

    signaler("HEARTBEAT_URL_MAILINGLIST")

    mock_get.assert_called_once_with("https://hc.example.org/ping/autre", timeout=5)
