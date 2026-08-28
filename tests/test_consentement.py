"""Tests du consentement « Règles de Confidentialité ».

Le défaut, trouvé le 27/08/2026 et corrigé le 28 : le code lisait les réponses
HelloAsso par le libellé exact de la question, et la clé du mappage était
« Règles de Confidentialité » — un nom de colonne Airtable, pas une question. Le
formulaire pose « J'accepte les règles de confidentialité … ». Les deux ne se
rencontraient jamais : **84 consentements de l'année 2026 non enregistrés, sans
un message d'erreur.**

Le correctif a deux moitiés qui doivent voyager ensemble, et c'est ce que ces
tests garantissent :

1. le libellé du mappage est celui que le formulaire pose ;
2. la valeur est convertie en booléen, parce que la colonne Airtable est une
   **case à cocher**.

Faire la première sans la seconde serait pire que le défaut : le code écrirait
la chaîne « Oui » dans une case à cocher, Airtable refuserait **l'écriture
entière** (le code n'utilise pas `typecast`) et `hello_asso_sync` abandonnerait
l'adhésion complète — fiche, liste de diffusion et mail de bienvenue compris —
pour un champ secondaire. Mesuré dans le bac à sable le 28/08/2026 :
`INVALID_VALUE_FOR_COLUMN — Field "Règles de Confidentialité" cannot accept the
provided value`.
"""

from datetime import datetime

import pytest

from src.models.user_subscription import (
    CHAMPS_BOOLEENS_AIRTABLE,
    CHAMPS_HELLOASSO_VERS_AIRTABLE,
    UserSubscription,
)

LIBELLE = ("J'accepte les règles de confidentialité de La Coop des Communs, "
           "disponibles à cette adresse : https://coopdescommuns.org/fr/confidentialite/")


def item(reponse, libelle=LIBELLE):
    return {
        "payer": {"email": "x@example.org"},
        "user": {"firstName": "Prosper", "lastName": "Répétition"},
        "order": {"date": "2026-08-28T10:00:00+02:00"},
        "state": "Processed",
        "customFields": [{"name": libelle, "answer": reponse}],
    }


def payload(reponse, libelle=LIBELLE):
    adhesion = UserSubscription.from_hello_asso_item(
        item(reponse, libelle), cotisation="Payé 2026", groupe="Adhérent·es")
    return adhesion.to_airtable_payload()


class TestLibelle:
    def test_le_mappage_porte_le_libelle_du_formulaire(self):
        """Une clé qui est un nom de colonne au lieu d'une question ne rencontre
        jamais rien, et ne lève jamais."""
        assert LIBELLE in CHAMPS_HELLOASSO_VERS_AIRTABLE
        assert CHAMPS_HELLOASSO_VERS_AIRTABLE[LIBELLE] == "Règles de Confidentialité"

    def test_l_ancienne_cle_n_est_plus_la(self):
        assert "Règles de Confidentialité" not in CHAMPS_HELLOASSO_VERS_AIRTABLE

    def test_une_espace_finale_ne_fait_pas_perdre_la_reponse(self):
        """Le formulaire de production pose le libellé avec une espace finale ;
        sa copie dupliquée l'avait perdue. Deux formulaires censés être
        identiques, deux comportements — rogné à l'entrée depuis le 27/08."""
        assert payload("Oui", LIBELLE + " ")["Règles de Confidentialité"] is True


class TestConversionBooleenne:
    def test_oui_devient_vrai(self):
        assert payload("Oui")["Règles de Confidentialité"] is True

    @pytest.mark.parametrize("reponse", ["oui", "OUI", " Oui ", "yes", "true", "1"])
    def test_les_variantes_de_oui_sont_reconnues(self, reponse):
        assert payload(reponse)["Règles de Confidentialité"] is True

    def test_non_devient_faux(self):
        """« Non » est une chaîne non vide : sans conversion, elle partirait
        telle quelle et ferait échouer l'écriture entière."""
        assert payload("Non")["Règles de Confidentialité"] is False

    def test_une_reponse_inattendue_laisse_la_case_decochee(self):
        """Un consentement ne se devine pas. Le sens prudent est « non donné »."""
        assert payload("peut-être")["Règles de Confidentialité"] is False

    def test_une_reponse_vide_ne_touche_pas_la_colonne(self):
        """Ne pas écrire False sur une fiche existante parce que HelloAsso n'a
        rien renvoyé : ce serait retirer un consentement déjà donné."""
        assert "Règles de Confidentialité" not in payload("")

    def test_la_valeur_reste_une_chaine_pour_les_autres_oui_non(self):
        """« Visible sur le site » et « Partage de donnée autorisé » ne sont pas
        des cases à cocher : elles acceptent la chaîne, vérifié sur la base."""
        assert CHAMPS_BOOLEENS_AIRTABLE == {"Règles de Confidentialité"}
        adhesion = UserSubscription(
            email="x@example.org", first_name="P", last_name="R",
            subscription_date=datetime(2026, 8, 28), cotisation="Payé 2026",
            groupe="Adhérent·es",
            custom_fields={"Je souhaite que mon Nom et Prénom soient partagés sur le "
                           "site web de l'association dans la liste des adhérent·es": "Oui"})
        assert adhesion.to_airtable_payload()["Visible sur le site"] == "Oui"
