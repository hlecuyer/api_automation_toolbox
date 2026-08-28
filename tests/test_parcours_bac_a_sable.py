"""Tests du parcours d'adhésion rejoué dans le bac à sable.

Un parcours de répétition auquel on ne peut pas se fier est pire que pas de
parcours : il donne l'assurance d'avoir répété. Ce qui est vérifié ici est donc
d'abord **ce qui doit refuser** — la ceinture — puis le fait que chaque étape
constate au lieu de supposer.

Deux comportements méritent d'être lus comme des décisions et non comme des
détails :

- **Une opération OVH non encore appliquée n'est pas un écart.** L'abonnement
  est une tâche asynchrone ; compter l'attente comme un échec ferait chercher un
  bug là où il n'y en a pas, ce qui est exactement l'erreur de diagnostic faite
  pendant des mois sur la liste de production.
- **Un envoi qui passe est un écart.** Le critère de recette du bac à sable est
  qu'aucune adresse d'adhérent réel ne puisse être jointe ; il se prouve par un
  refus constaté, pas par une configuration qui a l'air juste.
"""

import importlib.util
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

CHEMIN = Path(__file__).parent.parent / "scripts" / "parcours_bac_a_sable.py"
_spec = importlib.util.spec_from_file_location("parcours_bac_a_sable", CHEMIN)
parcours = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parcours)

bac = parcours.bac

DOMAINE = "d.org"
LISTE = "bac-a-sable"


def regle(methode, chemin):
    return {"method": methode, "path": chemin}


def cibles(**remplacements):
    base = {
        "base": "appBAC",
        "base_production": "appPROD",
        "liste": LISTE,
        "liste_production": "membres",
        "domaine": DOMAINE,
        "adresse": "parcours-1@example.org",
        "formulaire": "Bac à sable adhésion test",
        "jeton_airtable_dedie": True,
    }
    base.update(remplacements)
    return base


class FauxOvh:
    """Un client OVH sans réseau. Sert les règles de la clé et note les suppressions."""

    def __init__(self, regles=None, abonnes=None):
        self.regles = regles if regles is not None else [
            regle("GET", "/email/domain/%s/mailingList/%s" % (DOMAINE, LISTE)),
            regle("POST", "/email/domain/%s/mailingList/%s/subscriber" % (DOMAINE, LISTE)),
        ]
        self.abonnes = list(abonnes or [])
        self.supprimes = []

    def get(self, chemin, **_):
        if chemin == "/auth/currentCredential":
            return {"rules": self.regles}
        return self.abonnes

    def delete(self, chemin, **_):
        self.supprimes.append(chemin)


@pytest.fixture(autouse=True)
def hors_production(monkeypatch):
    """Le conftest déclare déjà l'environnement « tests » ; on le rend explicite
    ici parce que plusieurs cas jouent sur cette variable."""
    monkeypatch.setenv(parcours.garde_fou_envoi.VARIABLE_ENVIRONNEMENT, "tests")


# --------------------------------------------------------------------------
# La ceinture
# --------------------------------------------------------------------------

class TestCeinture:
    def test_cas_nominal_passe(self, capsys):
        assert parcours.controler_cibles(cibles(), FauxOvh()) == 0
        assert "❌" not in capsys.readouterr().out

    def test_environnement_production_refuse(self, monkeypatch, capsys):
        """Le parcours écrirait sur les données du client et enverrait de vrais
        mails : c'est le seul cas où il ne doit même pas commencer."""
        monkeypatch.setenv(parcours.garde_fou_envoi.VARIABLE_ENVIRONNEMENT, "production")
        assert parcours.controler_cibles(cibles(), FauxOvh()) == 1
        assert "ENVIRONNEMENT=production" in capsys.readouterr().out

    def test_base_de_production_refusee(self, capsys):
        assert parcours.controler_cibles(cibles(base="appPROD"), FauxOvh()) == 1
        assert "base de production" in capsys.readouterr().out

    def test_liste_de_production_refusee(self, capsys):
        assert parcours.controler_cibles(cibles(liste="membres"), FauxOvh()) == 1
        assert "celle de production" in capsys.readouterr().out

    def test_adresse_a_domaine_reel_refusee(self, capsys):
        """L'invariant du bac à sable : toute adresse est à un domaine réservé
        RFC 2606, donc sans MX, donc structurellement incapable de recevoir."""
        assert parcours.controler_cibles(
            cibles(adresse="quelquun@coopdescommuns.org"), FauxOvh()) == 1
        assert "RFC 2606" in capsys.readouterr().out

    def test_cle_ovh_debordante_refusee(self, capsys):
        """Le cas réel du 27/08/2026 : la clé du bac à sable était celle de la
        production, autorisée sur la seule liste des 144 adhérents."""
        large = FauxOvh([regle("POST", "/email/domain/%s/mailingList/membres/*" % DOMAINE)])
        assert parcours.controler_cibles(cibles(), large) == 1
        sortie = capsys.readouterr().out
        assert "déborde" in sortie

    def test_cle_ovh_sans_regle_refusee(self, capsys):
        assert parcours.controler_cibles(cibles(), FauxOvh([])) == 1
        assert "aucune règle" in capsys.readouterr().out

    def test_liste_voisine_ne_passe_pas_pour_la_liste_visee(self, capsys):
        """« bac-a-sable-autre » n'est pas « bac-a-sable » : la comparaison porte
        sur le préfixe suivi d'un slash."""
        voisine = FauxOvh([
            regle("POST", "/email/domain/%s/mailingList/bac-a-sable-autre/*" % DOMAINE)
        ])
        assert parcours.controler_cibles(cibles(), voisine) == 1

    def test_jeton_airtable_non_confine_est_dit_sans_bloquer(self, capsys):
        """Il n'existe pas encore de jeton Airtable restreint au bac à sable :
        la garantie est ici une vérification, pas un credential. Ça se dit."""
        assert parcours.controler_cibles(
            cibles(jeton_airtable_dedie=False), FauxOvh()) == 0
        assert "non confinée" in capsys.readouterr().out


# --------------------------------------------------------------------------
# L'item rejoué
# --------------------------------------------------------------------------

class TestItem:
    def test_toutes_les_questions_du_mapping_sont_posees(self):
        item = parcours.item_synthetique("x@example.org", ["Masculin"])
        poses = {q["name"] for q in item["customFields"]}
        assert poses == set(parcours.CHAMPS_HELLOASSO_VERS_AIRTABLE)

    def test_genre_tire_des_options_de_la_base(self):
        """Jamais écrit en dur : sans `typecast`, une valeur hors options fait
        échouer l'écriture entière et l'adhésion est perdue."""
        item = parcours.item_synthetique("x@example.org", ["Féminin", "Masculin"])
        reponses = {q["name"]: q["answer"] for q in item["customFields"]}
        assert reponses["Genre"] == "Féminin"

    def test_genre_sans_schema_lisible_retombe_sur_une_option_universelle(self):
        item = parcours.item_synthetique("x@example.org", [])
        reponses = {q["name"]: q["answer"] for q in item["customFields"]}
        assert reponses["Genre"] == "Non-précisé"

    def test_aucune_reponse_vide(self):
        """Une valeur vide est écartée par `to_airtable_payload` : la colonne ne
        serait jamais exercée, et l'étape passerait au vert sans rien prouver."""
        item = parcours.item_synthetique("x@example.org", ["Masculin"])
        assert all(q["answer"] for q in item["customFields"])

    def test_item_capture_est_readresse(self, tmp_path):
        """Le point de sécurité : un item capturé porte l'adresse de qui a rempli
        le formulaire, et elle ne doit jamais atteindre le bac à sable."""
        import json
        fichier = tmp_path / "item.json"
        fichier.write_text(json.dumps({
            "payer": {"email": "vraie.personne@coopdescommuns.org"},
            "user": {"firstName": "A", "lastName": "B"},
            "order": {"date": "2026-08-28T10:00:00+02:00"},
            "state": "Processed",
            "customFields": [],
        }), encoding="utf-8")

        item = parcours.item_depuis_fichier(str(fichier), "parcours-1@example.org")
        assert item["payer"]["email"] == "parcours-1@example.org"


# --------------------------------------------------------------------------
# L'adhésion et son payload
# --------------------------------------------------------------------------

CONF = {
    "cotisation_label": "Payé 2026",
    "groupe": "Adhérent·es la Coop des Communs",
    "helloAsso": {
        "first_sub_field": "Est-ce votre première adhésion à la coop des communs ?",
        "name_field": "Nom",
        "default": {},
    },
    "airtable": {
        "linked_records": {"Groupe(s)": {}, "Structure(s)": {}},
        "computed_fields": {"new_member": {"field": "Nouvel adhérent"}},
        "normalized_fields": {"Genre": {}},
    },
}


class TestAdhesion:
    def test_le_payload_vise_les_colonnes_du_mapping(self, capsys):
        item = parcours.item_synthetique("x@example.org", ["Masculin"])
        adhesion, payload = parcours.etape_adhesion(item, CONF)

        assert adhesion.email == "x@example.org"
        assert payload["Cotisation LCDC"] == "Payé 2026"
        assert payload["Groupe(s)"] == "Adhérent·es la Coop des Communs"
        assert payload["Genre"] == "Masculin"

    def test_une_question_que_le_code_ne_lit_pas_est_signalee(self, capsys):
        """La forme exacte du défaut de consentement : aucune erreur, aucune
        trace, une colonne vide pour toujours."""
        item = parcours.item_synthetique("x@example.org", ["Masculin"])
        item["customFields"].append(
            {"name": "J'accepte les règles de confidentialité de …", "answer": "Oui"})

        parcours.etape_adhesion(item, CONF)
        sortie = capsys.readouterr().out
        assert "que le code ne lit pas" in sortie

    def test_un_libelle_avec_espace_finale_est_quand_meme_lu(self, capsys):
        """Les libellés sont rognés à l'entrée depuis le 27/08/2026 : une espace
        de trop ne doit plus faire perdre une réponse."""
        item = parcours.item_synthetique("x@example.org", ["Masculin"])
        for question in item["customFields"]:
            if question["name"] == "Genre":
                question["name"] = " Genre "

        _, payload = parcours.etape_adhesion(item, CONF)
        assert payload["Genre"] == "Masculin"
        assert "que le code ne lit pas" not in capsys.readouterr().out


# --------------------------------------------------------------------------
# Airtable
# --------------------------------------------------------------------------

class FauxClientAirtable:
    base_url = "https://api.airtable.com/v0/appBAC/Annuaire"
    headers = {"Authorization": "Bearer x"}

    def __init__(self, fiche=None, refusees=()):
        self.fiche = fiche
        self.refusees = set(refusees)
        self.creees = []
        self.majs = []

    def find_record_by_email(self, email, dry_run=False):
        return self.fiche

    def create_record(self, fields, dry_run=False):
        self.creees.append(fields)
        return {"id": "recESSAI", "fields": fields}

    def update_record(self, record_id, fields, dry_run=False):
        self.majs.append(fields)
        if set(fields) & self.refusees:
            return None
        return {"id": record_id, "fields": fields}


def faux_sync(client):
    sync = Mock()
    sync.airtable_client = client
    sync._compteurs = {"traitées": 0, "erreurs": 0}
    return sync


class TestAirtable:
    def test_simulation_n_ecrit_rien(self, capsys):
        client = FauxClientAirtable()
        sync = faux_sync(client)
        fiche, ecarts = parcours.etape_airtable(
            sync, Mock(email="x@example.org"), {"E-mail": "x@example.org"}, CONF, False)

        assert (fiche, ecarts) == (None, 0)
        sync.sync_subscriptions.assert_not_called()
        assert "simulation" in capsys.readouterr().out

    def test_fiche_relue_et_comparee(self, capsys):
        client = FauxClientAirtable(
            fiche={"id": "rec1", "fields": {"E-mail": "x@example.org", "Prénom": "Prosper"}})
        sync = faux_sync(client)
        sync._compteurs = {"traitées": 1, "erreurs": 0}
        adhesion = Mock(email="x@example.org", subscription_date=datetime(2026, 8, 28))

        fiche, ecarts = parcours.etape_airtable(
            sync, adhesion, {"E-mail": "x@example.org", "Prénom": "Prosper"}, CONF, True)

        assert ecarts == 0
        assert fiche["id"] == "rec1"
        sync.sync_subscriptions.assert_called_once()

    def test_colonne_vide_est_un_ecart(self, capsys):
        client = FauxClientAirtable(fiche={"id": "rec1", "fields": {"E-mail": "x@example.org"}})
        sync = faux_sync(client)
        adhesion = Mock(email="x@example.org", subscription_date=datetime(2026, 8, 28))

        _, ecarts = parcours.etape_airtable(
            sync, adhesion, {"E-mail": "x@example.org", "Genre": "Masculin"}, CONF, True)

        assert ecarts == 1
        assert "Genre" in capsys.readouterr().out

    def test_la_date_de_filtre_ne_doit_pas_ecarter_l_adhesion(self):
        """Sinon `sync_subscriptions` ne fait rien et l'étape passerait au vert
        sans avoir rien écrit — un faux positif indétectable."""
        client = FauxClientAirtable(fiche={"id": "rec1", "fields": {}})
        sync = faux_sync(client)
        quand = datetime(2026, 8, 28, 12, 0, 0)
        adhesion = Mock(email="x@example.org", subscription_date=quand)

        parcours.etape_airtable(sync, adhesion, {}, CONF, True)

        _, filtre = sync.sync_subscriptions.call_args[0]
        assert filtre < quand

    def test_absence_de_fiche_declenche_le_diagnostic(self, capsys, monkeypatch):
        monkeypatch.setattr(parcours, "diagnostiquer_colonnes", Mock())
        client = FauxClientAirtable(fiche=None)
        sync = faux_sync(client)
        adhesion = Mock(email="x@example.org", subscription_date=datetime(2026, 8, 28))

        fiche, ecarts = parcours.etape_airtable(sync, adhesion, {}, CONF, True)

        assert (fiche, ecarts) == (None, 1)
        parcours.diagnostiquer_colonnes.assert_called_once()


class TestDiagnostic:
    def test_nomme_la_colonne_fautive(self, capsys, monkeypatch):
        """Le cas qui a motivé ce diagnostic : « Règles de Confidentialité » est
        une case à cocher et le code y écrit la chaîne « Oui ». Sans `typecast`,
        c'est toute l'écriture qui échoue, donc toute l'adhésion."""
        monkeypatch.setattr("requests.delete", Mock())
        client = FauxClientAirtable(refusees={"Règles de Confidentialité"})
        sync = faux_sync(client)
        payload = {"E-mail": "x@example.org", "Prénom": "P", "Nom": "R",
                   "Genre": "Masculin", "Règles de Confidentialité": "Oui"}

        parcours.diagnostiquer_colonnes(sync, payload, CONF)

        sortie = capsys.readouterr().out
        assert "Règles de Confidentialité" in sortie
        assert "refusée" in sortie
        assert "1 colonne(s) à traiter" in sortie

    def test_ecarte_les_colonnes_liees(self, capsys, monkeypatch):
        """Elles attendent des identifiants d'enregistrement, pas le texte du
        payload : les tester ici les accuserait à tort."""
        monkeypatch.setattr("requests.delete", Mock())
        client = FauxClientAirtable()
        payload = {"E-mail": "x@example.org", "Prénom": "P", "Nom": "R",
                   "Groupe(s)": "Adhérent·es la Coop des Communs"}

        parcours.diagnostiquer_colonnes(faux_sync(client), payload, CONF)

        assert "Groupe(s)" not in [list(m)[0] for m in client.majs]
        assert "non testées ici" in capsys.readouterr().out

    def test_retire_la_fiche_d_essai(self, monkeypatch):
        """L'espace Airtable de la Coop a dépassé sa limite d'enregistrements :
        un diagnostic qui laisse des fiches derrière lui aggrave le problème."""
        supprime = Mock()
        monkeypatch.setattr("requests.delete", supprime)
        parcours.diagnostiquer_colonnes(
            faux_sync(FauxClientAirtable()), {"E-mail": "x@example.org"}, CONF)

        assert supprime.call_count == 1
        assert "recESSAI" in supprime.call_args[0][0]


# --------------------------------------------------------------------------
# Le groupe
# --------------------------------------------------------------------------

class FauxAirtableBrut:
    def __init__(self, groupes):
        self.groupes = groupes

    def enregistrements(self, base, table, champs=None):
        return self.groupes


GROUPE_ADHERENTS = {"id": "grp1",
                    "fields": {"Nom": "Adhérent·es la Coop des Communs",
                               "Label": "bac-a-sable"}}


class TestGroupe:
    def test_rattachement_constate(self, capsys):
        fiche = {"id": "rec1", "fields": {"Groupe(s)": ["grp1"]}}
        at = FauxAirtableBrut([GROUPE_ADHERENTS])

        assert parcours.etape_groupe(at, fiche, CONF, cibles()) == 0
        assert "rattachée à" in capsys.readouterr().out

    def test_absence_de_rattachement_est_un_ecart(self, capsys):
        """on_missing=warn laisse tomber le champ sans faire échouer
        l'écriture : l'adhérent n'est dans aucun groupe, et rien ne le dit."""
        fiche = {"id": "rec1", "fields": {}}
        assert parcours.etape_groupe(FauxAirtableBrut([]), fiche, CONF, cibles()) == 1
        assert "aucun groupe" in capsys.readouterr().out

    def test_label_hors_prefixe_est_un_ecart(self, capsys):
        """Le danger symétrique du bac à sable : l'extracteur prend le Label pour
        nom de liste OVH et aligne cette liste sur Airtable, en supprimant tout
        abonné absent. Un label « membres » ici viderait la vraie liste."""
        groupe = {"id": "grp1", "fields": {"Nom": "Adhérent·es la Coop des Communs",
                                           "Label": "membres"}}
        fiche = {"id": "rec1", "fields": {"Groupe(s)": ["grp1"]}}

        assert parcours.etape_groupe(FauxAirtableBrut([groupe]), fiche, CONF, cibles()) == 1
        assert "membres" in capsys.readouterr().out

    def test_sans_fiche_l_etape_est_un_ecart(self):
        assert parcours.etape_groupe(FauxAirtableBrut([]), None, CONF, cibles()) == 1


# --------------------------------------------------------------------------
# La liste de diffusion
# --------------------------------------------------------------------------

class TestListe:
    def test_abonnement_constate(self, capsys, monkeypatch):
        monkeypatch.setattr(bac, "_attendre", lambda *a, **k: True)
        fiche = {"id": "rec1", "fields": {}}

        assert parcours.etape_liste(FauxOvh(), cibles(), "x@example.org", fiche) == 0
        assert "est abonnée" in capsys.readouterr().out

    def test_tache_non_encore_appliquee_n_est_pas_un_ecart(self, capsys, monkeypatch):
        """Un POST OVH rend une tâche, pas un abonné. Compter l'attente comme un
        échec ferait chercher un bug là où il n'y en a pas."""
        monkeypatch.setattr(bac, "_attendre", lambda *a, **k: False)
        fiche = {"id": "rec1", "fields": {}}

        assert parcours.etape_liste(FauxOvh(), cibles(), "x@example.org", fiche) == 0
        assert "pas encore appliqué" in capsys.readouterr().out

    def test_sans_fiche_l_abonnement_n_a_pas_ete_demande(self):
        assert parcours.etape_liste(FauxOvh(), cibles(), "x@example.org", None) == 1


# --------------------------------------------------------------------------
# Le mail
# --------------------------------------------------------------------------

def client_mail(passe):
    client = Mock()
    client.send_email.return_value = passe
    return client


class TestMail:
    def test_rendu_et_refus_du_garde_fou(self, capsys):
        ecarts = parcours.etape_mail(client_mail(False), CONF, "Prosper",
                                     "x@example.org")
        assert ecarts == 0
        sortie = capsys.readouterr().out
        assert "signature substituée" in sortie
        assert "refusé par le garde-fou" in sortie

    def test_un_envoi_qui_passe_est_un_ecart(self, capsys):
        """Le critère de recette du bac à sable, et il se démontre par un refus
        constaté : « aucune adresse d'adhérent réel ne peut être jointe »."""
        assert parcours.etape_mail(client_mail(True), CONF, "Prosper",
                                   "x@example.org") == 1
        assert "laissé passer" in capsys.readouterr().out

    def test_sentinelle_de_signature_non_substituee_est_un_ecart(self, capsys, monkeypatch):
        """Le mail partirait avec « @@SIG_NAME@@ » en toutes lettres."""
        monkeypatch.setattr(parcours.welcome_email, "render",
                            lambda prenom: ("Bonjour Prosper @@SIG_NAME@@", "<p>Prosper</p>"))
        assert parcours.etape_mail(client_mail(False), CONF, "Prosper",
                                   "x@example.org") == 1
        assert "@@SIG_NAME@@" in capsys.readouterr().out

    def test_rendu_qui_leve_est_un_ecart(self, capsys, monkeypatch):
        """Le défaut trouvé le 26/08/2026 : une accolade dans une valeur de
        signature levait KeyError, donc mail non parti et adhésion en échec."""
        def render_qui_leve(prenom):
            raise KeyError("sig")
        monkeypatch.setattr(parcours.welcome_email, "render", render_qui_leve)

        assert parcours.etape_mail(client_mail(False), CONF, "Prosper",
                                   "x@example.org") == 1
        assert "KeyError" in capsys.readouterr().out

    def test_rendu_ecrit_sur_demande_avec_l_avertissement(self, tmp_path, capsys):
        fichier = tmp_path / "rendu.html"
        parcours.etape_mail(client_mail(False), CONF, "Prosper", "x@example.org",
                            str(fichier))

        assert fichier.read_text(encoding="utf-8")
        assert "données" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Ménage
# --------------------------------------------------------------------------

class TestMenage:
    def test_retire_fiche_et_abonnement(self, monkeypatch, capsys):
        supprime = Mock(return_value=Mock(ok=True))
        monkeypatch.setattr("requests.delete", supprime)
        ovh = FauxOvh()
        sync = faux_sync(FauxClientAirtable())

        parcours.etape_menage(sync, ovh, cibles(), {"id": "rec1"}, "x@example.org", False)

        assert supprime.call_count == 1
        assert ovh.supprimes == [
            "/email/domain/%s/mailingList/%s/subscriber/x@example.org" % (DOMAINE, LISTE)]

    def test_garder_ne_touche_a_rien(self, monkeypatch):
        supprime = Mock()
        monkeypatch.setattr("requests.delete", supprime)
        ovh = FauxOvh()

        parcours.etape_menage(faux_sync(FauxClientAirtable()), ovh, cibles(),
                              {"id": "rec1"}, "x@example.org", True)

        assert supprime.call_count == 0
        assert ovh.supprimes == []

    def test_desabonnement_refuse_ne_fait_pas_echouer(self, monkeypatch, capsys):
        """La tâche d'ajout est asynchrone : la demande de retrait peut la
        précéder, et ce n'est pas une anomalie."""
        monkeypatch.setattr("requests.delete", Mock(return_value=Mock(ok=True)))
        ovh = FauxOvh()
        ovh.delete = Mock(side_effect=RuntimeError("pas encore abonné"))

        parcours.etape_menage(faux_sync(FauxClientAirtable()), ovh, cibles(),
                              {"id": "rec1"}, "x@example.org", False)

        assert "n'est pas encore appliqué" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Le montage de la configuration
# --------------------------------------------------------------------------

class TestConfiguration:
    def ecrire(self, tmp_path):
        import json
        chemin = tmp_path / "conf.json"
        chemin.write_text(json.dumps({"conf": {
            "cotisation_label": "Payé 2026",
            "groupe": "Adhérent·es la Coop des Communs",
            "helloAsso": {"organization_name": "org", "form_name": "Adhésion année 2026"},
            "ovh": {"mailing_list": {"name": "membres", "domain": "coopdescommuns.org"},
                    "email": {"from": "presidente@coopdescommuns.org"}},
            "airtable": {"table_name": "Annuaire", "linked_records": {"Groupe(s)": {}}},
        }}), encoding="utf-8")
        return str(chemin)

    def test_les_cibles_sont_remplacees(self, tmp_path):
        conf = parcours._conf_bac_a_sable(self.ecrire(tmp_path), cibles())
        assert conf["ovh"]["mailing_list"]["name"] == LISTE
        assert conf["ovh"]["mailing_list"]["domain"] == DOMAINE
        assert conf["helloAsso"]["form_name"] == "Bac à sable adhésion test"

    def test_l_expediteur_de_production_est_remplace(self, tmp_path):
        """Un envoi qui partirait malgré tout ne doit pas pouvoir se réclamer de
        l'association, ni porter l'adresse d'une personne."""
        conf = parcours._conf_bac_a_sable(self.ecrire(tmp_path), cibles())
        assert conf["ovh"]["email"]["from"].endswith("@example.org")

    def test_le_comportement_est_conserve(self, tmp_path):
        """C'est lui qu'on répète : des cibles isolées avec un comportement
        amputé donnent une répétition qui passe sans rien garantir."""
        conf = parcours._conf_bac_a_sable(self.ecrire(tmp_path), cibles())
        assert conf["airtable"]["linked_records"] == {"Groupe(s)": {}}
        assert conf["cotisation_label"] == "Payé 2026"

    def test_configuration_absente_le_dit(self, tmp_path):
        with pytest.raises(SystemExit) as e:
            parcours._conf_bac_a_sable(str(tmp_path / "absent.json"), cibles())
        assert "introuvable" in str(e.value)

    def test_blocs_de_comportement_manquants_signales(self, capsys):
        parcours.controler_configuration({"airtable": {}})
        sortie = capsys.readouterr().out
        assert sortie.count("⚠") == 3

    def test_blocs_de_comportement_presents_valides(self, capsys):
        parcours.controler_configuration(CONF)
        assert "⚠" not in capsys.readouterr().out


class TestCredentialsForces:
    def test_les_identifiants_du_bac_a_sable_ecrasent_l_environnement(self, monkeypatch):
        """Sur ce poste, `AIRTABLE_BASE_ID` a déjà désigné la mauvaise base
        pendant des semaines. On ne négocie pas avec l'environnement."""
        instance = parcours.SyncBacASable.__new__(parcours.SyncBacASable)
        instance._credentials_bac_a_sable = {"airtable": {"base_id": "appBAC"}}
        instance.conf_global = {"credentials": {
            "airtable": {"api_key": "clé", "base_id": "appPROD"},
            "smtp": {"host": "ssl0.ovh.net"},
        }}
        appels = []
        monkeypatch.setattr(parcours.SyncHelloAsso, "_init_clients",
                            lambda self: appels.append(True))
        instance._init_clients()

        assert instance.conf_global["credentials"]["airtable"]["base_id"] == "appBAC"
        # Le reste est conservé : on remplace les cibles, pas la configuration.
        assert instance.conf_global["credentials"]["airtable"]["api_key"] == "clé"
        assert instance.conf_global["credentials"]["smtp"]["host"] == "ssl0.ovh.net"
        assert appels == [True]
