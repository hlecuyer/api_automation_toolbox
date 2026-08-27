"""Tests du bug « champ genre » — variantes d'un champ à choix fermé.

Symptôme remonté par la Coop : le champ Genre de l'Annuaire contient à la fois
`M`/`F` et `masculin`/`féminin`. HelloAsso a livré les deux jeux au fil des
versions du formulaire, et `custom_field_mapping` recopiait la valeur telle
quelle. Airtable les garde comme des options distinctes : un filtre sur
« féminin » rate les fiches en « F », et les compteurs sont faux.

Le référentiel vit dans la configuration et non dans le code : les options que
la Coop décide de garder sont sa décision, pas la nôtre, et elle doit pouvoir en
changer sans redéploiement.

Règle de fond : une valeur inattendue n'est jamais jetée en silence. Par défaut
elle passe telle quelle et un avertissement part dans syslog. La donnée d'un
adhérent vaut mieux qu'une colonne propre.
"""

from unittest.mock import Mock, patch

import pytest

from src.clients.airtable_client import AirtableClient, _cle_normalisee

REFERENTIEL = {
    "Genre": {
        "values": {
            "M": "Masculin",
            "F": "Féminin",
            "masculin": "Masculin",
            "féminin": "Féminin",
            "homme": "Masculin",
            "femme": "Féminin",
            "non-précisé": "Non-précisé",
        },
        "on_unknown": "keep",
    }
}


@pytest.fixture
def client():
    return AirtableClient(
        api_key="test", base_id="test", table_name="Annuaire",
        normalized_fields=REFERENTIEL,
    )


def normalise(client, valeur):
    fields = {"Genre": valeur, "Nom": "Dupont"}
    client._apply_normalized_fields(fields)
    return fields


# --- le cas remonté --------------------------------------------------------


@pytest.mark.parametrize(
    "livre_par_helloasso,attendu",
    [
        ("M", "Masculin"),
        ("F", "Féminin"),
        ("masculin", "Masculin"),
        ("féminin", "Féminin"),
        ("Masculin", "Masculin"),
        ("Féminin", "Féminin"),
    ],
)
def test_les_deux_jeux_de_valeurs_convergent(client, livre_par_helloasso, attendu):
    assert normalise(client, livre_par_helloasso)["Genre"] == attendu


@pytest.mark.parametrize("variante", ["f", "F", " f ", "Feminin", "féminin", "FÉMININ"])
def test_la_reconnaissance_ignore_casse_accents_et_espaces(client, variante):
    """`Feminin` sans accent est la même réponse que `féminin` : une saisie, pas une option."""
    assert normalise(client, variante)["Genre"] == "Féminin"


def test_les_autres_champs_ne_sont_pas_touches(client):
    assert normalise(client, "F")["Nom"] == "Dupont"


def test_un_champ_absent_du_payload_n_est_pas_invente(client):
    fields = {"Nom": "Dupont"}
    client._apply_normalized_fields(fields)
    assert "Genre" not in fields


# --- ce qui n'est pas au référentiel --------------------------------------


@patch("src.clients.airtable_client.syslog.syslog")
def test_une_valeur_inconnue_est_conservee_et_signalee(mock_syslog, client):
    """Ne jamais jeter la réponse d'un adhérent parce qu'elle sort de la liste."""
    assert normalise(client, "non-binaire")["Genre"] == "non-binaire"
    assert mock_syslog.called
    message = mock_syslog.call_args[0][1]
    assert "non-binaire" in message and "Genre" in message


@patch("src.clients.airtable_client.syslog.syslog")
def test_le_repli_ne_s_applique_que_s_il_est_demande(mock_syslog):
    client = AirtableClient(
        api_key="t", base_id="t",
        normalized_fields={
            "Genre": {
                "values": {"M": "Masculin"},
                "on_unknown": "fallback",
                "fallback_value": "Non-précisé",
            }
        },
    )
    fields = {"Genre": "non-binaire"}
    client._apply_normalized_fields(fields)
    assert fields["Genre"] == "Non-précisé"
    assert mock_syslog.called


def test_une_valeur_vide_reste_vide(client):
    """Vide veut dire « pas répondu », pas « valeur inattendue »."""
    assert normalise(client, "")["Genre"] == ""
    assert normalise(client, None)["Genre"] is None


# --- sans configuration, rien ne change -----------------------------------


def test_sans_referentiel_la_valeur_passe_intacte():
    client = AirtableClient(api_key="t", base_id="t")
    fields = {"Genre": "M"}
    client._apply_normalized_fields(fields)
    assert fields["Genre"] == "M"


@patch("src.clients.airtable_client.AirtableClient.create_record")
@patch("src.clients.airtable_client.AirtableClient.find_record_by_email")
def test_upsert_normalise_avant_d_ecrire(mock_find, mock_create, client):
    """Le branchement compte autant que la règle : sans lui, rien ne s'applique."""
    mock_find.return_value = None
    mock_create.return_value = {"id": "rec1"}

    client.upsert_record("jean@x.fr", {"Genre": "F", "E-mail": "jean@x.fr"})

    envoyes = mock_create.call_args[0][0]
    assert envoyes["Genre"] == "Féminin"


# --- la clé de rapprochement ----------------------------------------------


@pytest.mark.parametrize(
    "entree,attendu",
    [("Féminin", "feminin"), ("  M  ", "m"), ("Non-Précisé", "non-precise"), ("", "")],
)
def test_cle_normalisee(entree, attendu):
    assert _cle_normalisee(entree) == attendu


def test_cle_normalisee_tolere_autre_chose_qu_une_chaine():
    assert _cle_normalisee(None) == ""
    assert _cle_normalisee(42) == ""


class TestLibellesRognes:
    """Une espace en trop dans un libellé ne doit plus faire perdre la réponse.

    Le 27/08/2026, le formulaire de production posait la question de consentement
    avec une espace finale et le formulaire de test, créé par duplication, sans
    elle. Deux formulaires censés être identiques, deux comportements : un bac à
    sable qui ne rejoue pas la production ne prouve rien.
    """

    @staticmethod
    def _item(libelle, reponse):
        return {
            "payer": {"email": "a@example.org"},
            "user": {"firstName": "A", "lastName": "B"},
            "order": {"date": "2026-08-27T10:00:00"},
            "state": "Processed",
            "customFields": [{"name": libelle, "answer": reponse}],
        }

    @pytest.mark.parametrize("libelle", ["Genre", " Genre", "Genre ", "  Genre  "])
    def test_la_reponse_est_lue_quelle_que_soit_l_espace(self, libelle):
        from src.models.user_subscription import UserSubscription

        sub = UserSubscription.from_hello_asso_item(
            self._item(libelle, "Masculin"), cotisation="Payé 2026", groupe="G")
        assert sub.to_airtable_payload()["Genre"] == "Masculin"

    def test_le_champ_de_configuration_aussi(self):
        """first_sub_field vient de l'inventaire, recopié à la main lui aussi."""
        from src.models.user_subscription import UserSubscription

        sub = UserSubscription.from_hello_asso_item(
            self._item("Première adhésion ?", "Oui"),
            cotisation="Payé 2026", groupe="G",
            first_sub_field="  Première adhésion ? ")
        assert sub.custom_fields["Première adhésion ?"] == "2026"

    def test_les_valeurs_ne_sont_pas_rognees(self):
        """Le rognage sert à rapprocher deux libellés, jamais à écrire."""
        from src.models.user_subscription import UserSubscription

        sub = UserSubscription.from_hello_asso_item(
            self._item("Structure", " Coop du Pont "), cotisation="c", groupe="G")
        assert sub.to_airtable_payload()["Structure(s)"] == " Coop du Pont "
