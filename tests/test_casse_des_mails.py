"""Tests du bug « casse des mails » — doublons de contacts et valse sur la liste OVH.

Symptôme remonté par la Coop : une majuscule dans une adresse crée un contact en
double. Deux endroits du code, une seule cause — des adresses comparées
littéralement, alors que la casse n'a aucune valeur sémantique dans une adresse
mail.

1. `AirtableClient.find_record_by_email` filtrait sur `{E-mail}='…'`. Le `=`
   d'Airtable distingue la casse : `Jean.Dupont@x.fr` ne retrouvait pas un
   enregistrement stocké en `jean.dupont@x.fr`, et `upsert_record` créait un
   doublon au lieu de mettre à jour.

2. `CheckOvhMailinglist` comparait les abonnés OVH et Airtable avec `==` et `in`.
   Si les deux sources ne s'accordaient pas sur la casse, l'adresse paraissait
   absente des deux côtés à la fois : supprimée de la liste puis réajoutée, et
   ainsi de suite à chaque passage du cron, tous les jours.

Aucune adresse n'est réécrite : la normalisation ne sert qu'à comparer.
"""

from unittest.mock import Mock, patch

import pytest

from src.clients.airtable_client import AirtableClient, _escape_formula_value
from src.mailinglist_extracter import normaliser_email


@pytest.fixture
def airtable_client():
    return AirtableClient(
        api_key="test_api_key", base_id="test_base_id", table_name="Test Table"
    )


def formule_utilisee(mock_get):
    return mock_get.call_args[1]["params"]["filterByFormula"]


# --- 1. recherche Airtable insensible à la casse --------------------------


@pytest.mark.parametrize(
    "saisie",
    ["jean.dupont@x.fr", "Jean.Dupont@x.fr", "JEAN.DUPONT@X.FR", "  Jean.Dupont@x.fr"],
)
@patch("src.clients.airtable_client.requests.get")
def test_la_recherche_ignore_la_casse(mock_get, airtable_client, saisie):
    """Quatre écritures de la même adresse doivent produire la même requête."""
    reponse = Mock()
    reponse.json.return_value = {"records": []}
    reponse.raise_for_status = Mock()
    mock_get.return_value = reponse

    airtable_client.find_record_by_email(saisie.strip())

    assert formule_utilisee(mock_get) == "LOWER({E-mail})='jean.dupont@x.fr'"


@patch("src.clients.airtable_client.requests.get")
def test_la_comparaison_porte_sur_le_champ_normalise(mock_get, airtable_client):
    """LOWER() doit envelopper le champ, sinon un stockage en majuscules échappe encore."""
    reponse = Mock()
    reponse.json.return_value = {"records": []}
    reponse.raise_for_status = Mock()
    mock_get.return_value = reponse

    airtable_client.find_record_by_email("Jean.Dupont@x.fr")

    assert formule_utilisee(mock_get).startswith("LOWER({E-mail})=")


@patch("src.clients.airtable_client.requests.get")
def test_une_adresse_absente_reste_absente(mock_get, airtable_client):
    reponse = Mock()
    reponse.json.return_value = {"records": []}
    reponse.raise_for_status = Mock()
    mock_get.return_value = reponse

    assert airtable_client.find_record_by_email("inconnu@x.fr") is None


@patch("src.clients.airtable_client.requests.get")
def test_une_adresse_vide_ne_declenche_aucun_appel(mock_get, airtable_client):
    """Sans ce garde-fou, la formule deviendrait LOWER({E-mail})='' et matcherait."""
    assert airtable_client.find_record_by_email("") is None
    assert airtable_client.find_record_by_email(None) is None
    mock_get.assert_not_called()


# --- 2. échappement de la formule ----------------------------------------


@patch("src.clients.airtable_client.requests.get")
def test_une_apostrophe_ne_casse_plus_la_formule(mock_get, airtable_client):
    """`o'brien@x.fr` est une adresse valide qui fermait la chaîne littérale."""
    reponse = Mock()
    reponse.json.return_value = {"records": []}
    reponse.raise_for_status = Mock()
    mock_get.return_value = reponse

    airtable_client.find_record_by_email("O'Brien@x.fr")

    assert formule_utilisee(mock_get) == "LOWER({E-mail})='o\\'brien@x.fr'"


def test_l_echappement_traite_aussi_l_antislash():
    assert _escape_formula_value("a\\b") == "a\\\\b"
    assert _escape_formula_value("o'brien") == "o\\'brien"
    assert _escape_formula_value("simple") == "simple"


# --- 3. réconciliation de la liste OVH ------------------------------------


class ListeFactice:
    """Un CheckOvhMailinglist réduit à ce que ReconcileSubscribers appelle."""

    def __init__(self):
        from src.mailinglist_extracter import CheckOvhMailinglist

        self.supprimes = []
        self.ajoutes = []
        # ReconcileSubscribers compte les appels OVH réellement émis : c'est de
        # là que sort la ligne de vie du passage.
        self._compteurs = dict(CheckOvhMailinglist.COMPTEURS_NEUFS)

    def DeleteOvhMailinglistSubscriber(self, mailing_list, email):
        self.supprimes.append(email)

    def AddOvhMailingListSubscriber(self, mailing_list, email):
        self.ajoutes.append(email)


def reconcilier(airtable, ovh, label=""):
    from src.mailinglist_extracter import CheckOvhMailinglist

    faux = ListeFactice()
    CheckOvhMailinglist.ReconcileSubscribers(faux, {}, airtable, ovh, label)
    return faux


def test_meme_adresse_casse_differente_ne_bouge_plus():
    """Le cœur du bug : la valse quotidienne suppression puis réajout."""
    resultat = reconcilier(["Jean.Dupont@x.fr"], ["jean.dupont@x.fr"])
    assert resultat.supprimes == []
    assert resultat.ajoutes == []


def test_un_abonne_absent_d_airtable_est_bien_supprime():
    resultat = reconcilier(["garde@x.fr"], ["garde@x.fr", "parti@x.fr"])
    assert resultat.supprimes == ["parti@x.fr"]
    assert resultat.ajoutes == []


def test_un_adherent_absent_d_ovh_est_bien_ajoute():
    resultat = reconcilier(["deja@x.fr", "nouveau@x.fr"], ["deja@x.fr"])
    assert resultat.supprimes == []
    assert resultat.ajoutes == ["nouveau@x.fr"]


def test_la_valeur_transmise_a_ovh_reste_celle_d_origine():
    """On compare en minuscules, on n'écrit pas en minuscules."""
    resultat = reconcilier(["Nouveau.Contact@x.fr"], [])
    assert resultat.ajoutes == ["Nouveau.Contact@x.fr"]


def test_les_espaces_parasites_ne_creent_pas_de_faux_ecart():
    resultat = reconcilier([" jean@x.fr "], ["jean@x.fr"])
    assert resultat.supprimes == []
    assert resultat.ajoutes == []


def test_le_libelle_de_liste_est_repris_dans_les_traces(capsys):
    reconcilier(["nouveau@x.fr"], [], label="membres")
    assert "add nouveau@x.fr in membres" in capsys.readouterr().out


def test_sans_libelle_la_trace_reste_celle_d_avant(capsys):
    reconcilier([], ["parti@x.fr"])
    assert "delete parti@x.fr" in capsys.readouterr().out


# --- 4. la normalisation elle-même ---------------------------------------


@pytest.mark.parametrize(
    "entree,attendu",
    [
        ("Jean.Dupont@x.fr", "jean.dupont@x.fr"),
        ("  jean@x.fr  ", "jean@x.fr"),
        ("JEAN@X.FR", "jean@x.fr"),
        ("", ""),
    ],
)
def test_normaliser_email(entree, attendu):
    assert normaliser_email(entree) == attendu


def test_normaliser_email_laisse_passer_ce_qui_n_est_pas_une_chaine():
    assert normaliser_email(None) is None
