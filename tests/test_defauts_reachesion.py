"""Un défaut ne doit pas effacer ce qu'un adhérent a saisi.

Mesuré le 28/08/2026 sur le bac à sable, en rejouant une réadhésion avec la même
adresse : la seconde adhésion réécrivait `Genre` à « Non-précisé » et
`Partage de donnée autorisé` à « Non », par-dessus ce que l'adhérent venait de
corriger dans le formulaire de mise à jour.

La cause n'est pas un bug d'écriture, c'est un changement de contexte. Les
valeurs par défaut existaient pour les adhérents qui laissaient une question
blanche sur HelloAsso. Depuis que HelloAsso ne pose plus ces questions, **toute**
adhésion arrive avec ces défauts — et le parcours de mise à jour se serait défait
tout seul d'une année sur l'autre.
"""

from datetime import datetime
from unittest.mock import Mock, patch

from src.clients.airtable_client import AirtableClient
from src.models.user_subscription import UserSubscription


def item(reponses=None, email="a@x.fr"):
    return {
        "payer": {"email": email},
        "user": {"firstName": "Baptiste", "lastName": "Nominé"},
        "order": {"date": "2026-08-28T15:33:10"},
        "state": "Processed",
        "customFields": [{"name": n, "answer": a} for n, a in (reponses or {}).items()],
    }


DEFAUTS = {"Genre": "Non-précisé", "Structure": ""}


class TestOrigineDesValeurs:
    def test_une_question_sans_reponse_est_marquee_par_defaut(self):
        s = UserSubscription.from_hello_asso_item(
            item(), cotisation="Payé 2026", groupe="G", default_fields=DEFAUTS)
        assert s.colonnes_par_defaut() == {"Genre", "Structure(s)"}

    def test_une_question_repondue_ne_l_est_pas(self):
        """C'est la distinction qui porte tout : « Non-précisé » choisi par
        l'adhérent est une réponse, « Non-précisé » posé faute de question n'en
        est pas une."""
        s = UserSubscription.from_hello_asso_item(
            item({"Genre": "Masculin"}), cotisation="Payé 2026", groupe="G",
            default_fields=DEFAUTS)
        assert "Genre" not in s.colonnes_par_defaut()
        assert s.to_airtable_payload()["Genre"] == "Masculin"

    def test_sans_defauts_declares_rien_n_est_marque(self):
        s = UserSubscription.from_hello_asso_item(
            item({"Genre": "Masculin"}), cotisation="Payé 2026", groupe="G")
        assert s.colonnes_par_defaut() == set()


@patch("src.clients.airtable_client.syslog")
class TestEcriture:
    def client(self):
        c = AirtableClient(api_key="k", base_id="appX")
        c.create_record = Mock(side_effect=lambda f, **_: {"id": "recNEW", "fields": f})
        c.update_record = Mock(side_effect=lambda i, f, **_: {"id": i, "fields": f})
        return c

    def test_sur_une_fiche_neuve_le_defaut_est_ecrit(self, _s):
        """Un nouvel adhérent n'a rien à perdre : le défaut vaut mieux que rien."""
        c = self.client()
        c.find_record_by_email = Mock(return_value=None)

        c.upsert_record("a@x.fr", {"Genre": "Non-précisé", "Nom": "N"},
                        colonnes_par_defaut={"Genre"})

        assert c.create_record.call_args[0][0]["Genre"] == "Non-précisé"

    def test_sur_une_fiche_existante_le_defaut_est_retire(self, _s):
        c = self.client()
        c.find_record_by_email = Mock(return_value={"id": "recX", "fields": {}})

        c.upsert_record("a@x.fr", {"Genre": "Non-précisé", "Nom": "N"},
                        colonnes_par_defaut={"Genre"})

        ecrits = c.update_record.call_args[0][1]
        assert "Genre" not in ecrits
        assert ecrits["Nom"] == "N"

    def test_une_vraie_reponse_passe_sur_une_fiche_existante(self, _s):
        """Le retrait porte sur l'origine de la valeur, pas sur la colonne."""
        c = self.client()
        c.find_record_by_email = Mock(return_value={"id": "recX", "fields": {}})

        c.upsert_record("a@x.fr", {"Genre": "Masculin"}, colonnes_par_defaut=set())

        assert c.update_record.call_args[0][1]["Genre"] == "Masculin"

    def test_le_retrait_est_dit(self, syslog):
        c = self.client()
        c.find_record_by_email = Mock(return_value={"id": "recX", "fields": {}})

        c.upsert_record("a@x.fr", {"Genre": "Non-précisé"},
                        colonnes_par_defaut={"Genre"})

        dit = " ".join(str(a) for a, _ in syslog.syslog.call_args_list for a in a)
        assert "Genre" in dit

    def test_sans_declaration_le_comportement_ne_change_pas(self, _s):
        """Les appelants qui ne passent pas l'argument écrivent comme avant."""
        c = self.client()
        c.find_record_by_email = Mock(return_value={"id": "recX", "fields": {}})

        c.upsert_record("a@x.fr", {"Genre": "Non-précisé"})

        assert c.update_record.call_args[0][1]["Genre"] == "Non-précisé"
