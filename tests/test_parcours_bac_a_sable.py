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
        "controle": set(),
        "formulaire": "Bac à sable adhésion test",
        "formulaire_production": "Adhésion année 2026",
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


class TestAdresseDeControle:
    """L'exception déclarée : une adresse nominative, qui peut vraiment recevoir."""

    def test_adresse_declaree_passe_et_la_breche_est_dite(self, capsys):
        c = cibles(adresse="hugo@dsi.coop", controle={"hugo@dsi.coop"})
        assert parcours.controler_cibles(c, FauxOvh()) == 0
        sortie = capsys.readouterr().out
        assert "elle PEUT recevoir" in sortie
        assert "ouvert" in sortie

    def test_adresse_declaree_mais_hors_liste_blanche_refusee(self, capsys):
        """Déclarer une exception ne suffit pas : le garde-fou d'envoi doit la
        connaître aussi, sinon le mail ne partirait pas et la démonstration
        échouerait sans qu'on sache pourquoi."""
        c = cibles(adresse="qui@ailleurs.fr", controle={"qui@ailleurs.fr"})
        assert parcours.controler_cibles(c, FauxOvh()) == 1
        assert "refusée par le garde-fou" in capsys.readouterr().out

    def test_une_adresse_reelle_non_declaree_reste_refusee(self, capsys):
        """La brèche est nominative : elle ne s'étend pas au domaine."""
        c = cibles(adresse="autre@dsi.coop", controle={"hugo@dsi.coop"})
        assert parcours.controler_cibles(c, FauxOvh()) == 1
        assert "n'est pas déclarée" in capsys.readouterr().out


class TestLivraison:
    def test_livraison_reussie_est_constatee(self, capsys):
        """Le mail part par la chaîne d'adhésion, à l'étape 4 : cette étape le
        constate, elle ne le provoque pas."""
        ecarts = parcours.etape_mail(client_mail(False), CONF, "Prosper", "hugo@dsi.coop",
                                     compteurs={"traitées": 1, "erreurs": 0}, livraison=True)
        assert ecarts == 0
        assert "réellement envoyé à hugo@dsi.coop" in capsys.readouterr().out

    def test_livraison_en_erreur_est_un_ecart(self, capsys):
        ecarts = parcours.etape_mail(client_mail(False), CONF, "Prosper", "hugo@dsi.coop",
                                     compteurs={"traitées": 1, "erreurs": 1}, livraison=True)
        assert ecarts == 1
        assert "n'est pas parti" in capsys.readouterr().out

    def test_la_ceinture_est_eprouvee_meme_en_livraison(self, capsys):
        """Le critère de recette ne se relâche pas parce qu'une exception
        existe : une adresse d'adhérent doit rester injoignable."""
        parcours.etape_mail(client_mail(True), CONF, "Prosper", "hugo@dsi.coop",
                            compteurs={"traitées": 1, "erreurs": 0}, livraison=True)
        sortie = capsys.readouterr().out
        assert "laissé passer" in sortie
        assert parcours.ADRESSE_TEMOIN_REFUS in sortie

    def test_le_temoin_de_refus_n_est_pas_l_adresse_du_parcours(self):
        """Sinon, en livraison, le témoin serait autorisé et ne prouverait rien."""
        client = client_mail(False)
        parcours.etape_mail(client, CONF, "Prosper", "hugo@dsi.coop",
                            compteurs={"traitées": 1, "erreurs": 0}, livraison=True)
        assert client.send_email.call_args.kwargs["to"] == [parcours.ADRESSE_TEMOIN_REFUS]


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

    def normaliser_champs(self, fields):
        """Le référentiel du vrai client. Ici, sans effet."""


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
        assert parcours.ADRESSE_TEMOIN_REFUS in sortie
        assert "refusé" in sortie

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
                            chemin_rendu=str(fichier))

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


# --------------------------------------------------------------------------
# Le parcours complet — l'adhésion vient de HelloAsso
# --------------------------------------------------------------------------

def item_helloasso(email, quand, questions=None):
    return {
        "payer": {"email": email},
        "user": {"firstName": "Hugo", "lastName": "L"},
        "order": {"date": quand},
        "state": "Processed",
        "customFields": questions or [],
    }


class FauxHelloAsso:
    def __init__(self, items, details=None):
        self.items = items
        self.details = ({"formType": "Membership", "formSlug": "bac-a-sable"}
                        if details is None else details)

    def __call__(self, **_):
        return self

    def get_form_details(self, titre):
        return self.details

    def get_form_items(self, form_type, form_slug):
        return self.items


@pytest.fixture
def helloasso(monkeypatch):
    monkeypatch.setenv("HELLOASSO_CLIENT_ID", "id")
    monkeypatch.setenv("HELLOASSO_CLIENT_SECRET", "secret")

    def brancher(items, details=None):
        faux = FauxHelloAsso(items, details)
        monkeypatch.setattr("src.clients.hello_asso_client.HelloAssoClient", faux)
        return faux

    return brancher


CONF_HA = dict(CONF, helloAsso=dict(CONF["helloAsso"], organization_name="org"))


class TestComplet:
    def test_la_plus_recente_est_retenue(self, helloasso, capsys):
        helloasso([item_helloasso("a@x.fr", "2026-08-01T10:00:00+02:00"),
                   item_helloasso("b@x.fr", "2026-08-28T10:00:00+02:00")])

        item = parcours.item_depuis_helloasso(CONF_HA, cibles())

        assert item["payer"]["email"] == "parcours-1@example.org"
        assert item["order"]["date"].startswith("2026-08-28")

    def test_l_adresse_du_payeur_ne_traverse_jamais(self, helloasso):
        """C'est le point de sécurité : le payeur d'une vraie soumission est une
        vraie personne, et le bac à sable n'accepte pas son adresse."""
        helloasso([item_helloasso("hugo@dsi.coop", "2026-08-28T10:00:00+02:00")])

        item = parcours.item_depuis_helloasso(CONF_HA, cibles())

        assert item["payer"]["email"] == "parcours-1@example.org"

    def test_filtre_sur_le_payeur(self, helloasso):
        helloasso([item_helloasso("a@x.fr", "2026-08-28T10:00:00+02:00"),
                   item_helloasso("b@x.fr", "2026-08-27T10:00:00+02:00")])

        item = parcours.item_depuis_helloasso(CONF_HA, cibles(), depuis="B@X.FR")

        assert item["order"]["date"].startswith("2026-08-27")

    def test_le_formulaire_de_production_est_refuse(self, helloasso):
        """Le lire rejouerait de vraies adhésions, adresses comprises, dans le
        bac à sable."""
        helloasso([item_helloasso("a@x.fr", "2026-08-28T10:00:00+02:00")])

        with pytest.raises(SystemExit) as e:
            parcours.item_depuis_helloasso(
                CONF_HA, cibles(formulaire="Adhésion année 2026"))
        assert "PRODUCTION" in str(e.value)

    def test_formulaire_introuvable_le_dit(self, helloasso):
        helloasso([], details={})
        with pytest.raises(SystemExit) as e:
            parcours.item_depuis_helloasso(CONF_HA, cibles())
        assert "introuvable" in str(e.value)

    def test_aucune_adhesion_demande_de_remplir_le_formulaire(self, helloasso):
        helloasso([])
        with pytest.raises(SystemExit) as e:
            parcours.item_depuis_helloasso(CONF_HA, cibles())
        assert "Remplir le formulaire" in str(e.value)

    def test_la_capture_ne_porte_pas_l_adresse_du_payeur(self, helloasso, tmp_path):
        """Un item capturé vit dans scripts/data/ et peut être rejoué des mois
        plus tard : il ne doit pas garder l'adresse de qui a rempli le
        formulaire."""
        import json
        helloasso([item_helloasso("hugo@dsi.coop", "2026-08-28T10:00:00+02:00")])
        fichier = tmp_path / "item.json"

        parcours.item_depuis_helloasso(CONF_HA, cibles(), capture=str(fichier))

        garde = json.loads(fichier.read_text(encoding="utf-8"))
        assert "dsi.coop" not in fichier.read_text(encoding="utf-8")
        assert garde["payer"]["email"].endswith("@example.org")

    def test_les_libelles_reels_traversent(self, helloasso, capsys):
        """Ce que le parcours complet apporte, et que l'item synthétique ne peut
        pas apporter : les libellés viennent du formulaire, pas du mappage."""
        helloasso([item_helloasso(
            "a@x.fr", "2026-08-28T10:00:00+02:00",
            [{"name": "Question que le code ignore", "answer": "Oui"}])])

        item = parcours.item_depuis_helloasso(CONF_HA, cibles())
        parcours.etape_adhesion(item, CONF)

        assert "que le code ne lit pas" in capsys.readouterr().out


# --------------------------------------------------------------------------
# La mise à jour de fiche — la seconde moitié du parcours cible
# --------------------------------------------------------------------------

class FauxTableReponses(FauxClientAirtable):
    """La table « Mise à jour fiche », sans réseau."""

    base_url = "https://api.airtable.com/v0/appBAC/Mise%20a%20jour%20fiche"

    def __init__(self, depot_refuse=False, synchronise=True):
        super().__init__()
        self.depot_refuse = depot_refuse
        self.synchronise = synchronise
        self.deposees = []

    def create_record(self, fields, dry_run=False):
        if self.depot_refuse:
            return None
        self.deposees.append(fields)
        return {"id": "recREP", "fields": fields}

    def list_records(self, filter_by_formula=None, **_):
        return [{"id": "recREP", "fields": {parcours.CHAMP_SYNCHRONISE: self.synchronise}}]


def monter_mise_a_jour(monkeypatch, table, fiche_relue):
    """Branche le client de la table de réponses et l'Annuaire relu."""
    monkeypatch.setattr("src.clients.airtable_client.AirtableClient",
                        lambda **_: table)
    annuaire = FauxClientAirtable(fiche=fiche_relue)
    sync = faux_sync(annuaire)
    monkeypatch.setattr(parcours, "Reconciliation",
                        lambda a, r: Mock(passer=Mock(return_value={
                            "màj_reçues": 1, "màj_appliquées": 1, "erreurs": 0})))
    return sync


CREDS = {"airtable": {"api_key": "clé", "base_id": "appBAC"}}
FICHE = {"id": "recFICHE", "fields": {"E-mail": "x@example.org"}}


class TestMiseAJour:
    def relue(self, **champs):
        """La fiche telle qu'elle doit être relue après réconciliation.

        Les corrections sont indexées par **libellé de question** ; la fiche,
        elle, porte des noms de colonnes. La traduction passe par la même
        correspondance que le code, sinon ce test validerait sa propre idée du
        rapprochement plutôt que celle du module.
        """
        base = {"E-mail": "x@example.org", parcours.CHAMP_DATE_MAJ: "2026-08-28"}
        base.update({parcours.CORRESPONDANCE[libelle]: valeur
                     for libelle, valeur in parcours.CORRECTIONS.items()})
        base.update(champs)
        return {"id": "recFICHE", "fields": base}

    def test_cas_nominal(self, monkeypatch, capsys):
        table = FauxTableReponses()
        sync = monter_mise_a_jour(monkeypatch, table, self.relue())

        ecarts, reponse = parcours.etape_mise_a_jour(sync, CREDS, cibles(), FICHE, CONF)

        assert ecarts == 0
        assert reponse == (table, "recREP")
        assert table.deposees[0][parcours.CHAMP_FICHE] == "recFICHE"

    def test_la_reponse_designe_la_fiche_sans_passer_par_l_adresse(self, monkeypatch):
        """Un rapprochement par adresse raterait les 7 fiches qui en portent
        plusieurs dans « Mail optionnel »."""
        table = FauxTableReponses()
        sync = monter_mise_a_jour(monkeypatch, table, self.relue())

        parcours.etape_mise_a_jour(sync, CREDS, cibles(), FICHE, CONF)

        assert parcours.CHAMP_FICHE in table.deposees[0]

    def test_sans_fiche_l_etape_est_un_ecart(self, monkeypatch):
        table = FauxTableReponses()
        sync = monter_mise_a_jour(monkeypatch, table, None)

        ecarts, reponse = parcours.etape_mise_a_jour(sync, CREDS, cibles(), None, CONF)

        assert (ecarts, reponse) == (1, None)

    def test_table_absente_le_dit(self, monkeypatch, capsys):
        table = FauxTableReponses(depot_refuse=True)
        sync = monter_mise_a_jour(monkeypatch, table, self.relue())

        ecarts, reponse = parcours.etape_mise_a_jour(sync, CREDS, cibles(), FICHE, CONF)

        assert (ecarts, reponse) == (1, None)
        assert "creer_table_mise_a_jour.py" in capsys.readouterr().out

    def test_une_correction_non_appliquee_est_un_ecart(self, monkeypatch, capsys):
        table = FauxTableReponses()
        sync = monter_mise_a_jour(monkeypatch, table,
                                  self.relue(**{"Fonction (structure)": "ancienne"}))

        ecarts, _ = parcours.etape_mise_a_jour(sync, CREDS, cibles(), FICHE, CONF)

        assert ecarts == 1
        assert "Fonction (structure)" in capsys.readouterr().out

    def test_suivi_non_renseigne_est_un_ecart(self, monkeypatch, capsys):
        """Sans la date, l'adhérent serait relancé alors qu'il a répondu."""
        table = FauxTableReponses()
        sync = monter_mise_a_jour(monkeypatch, table,
                                  self.relue(**{parcours.CHAMP_DATE_MAJ: None}))

        ecarts, _ = parcours.etape_mise_a_jour(sync, CREDS, cibles(), FICHE, CONF)

        assert ecarts == 1
        assert "le suivi ne sait pas" in capsys.readouterr().out

    def test_reponse_non_marquee_est_signalee_sans_etre_un_ecart(self, monkeypatch, capsys):
        """Elle sera rejouée, et réécrire les mêmes valeurs est sans effet."""
        table = FauxTableReponses(synchronise=False)
        sync = monter_mise_a_jour(monkeypatch, table, self.relue())

        ecarts, _ = parcours.etape_mise_a_jour(sync, CREDS, cibles(), FICHE, CONF)

        assert ecarts == 0
        assert "sera rejouée" in capsys.readouterr().out


class TestDerniereReponse:
    """Quelle réponse on relit quand la fiche en porte plusieurs.

    Airtable rend les enregistrements dans l'ordre de la vue, pas dans celui de
    leur création. Le 28/08/2026, le second essai a relu la réponse du premier :
    le parcours vérifiait autre chose que ce qui venait d'être saisi, et le
    disait vert.
    """

    class Table:
        def __init__(self, lignes):
            self.lignes = lignes
            self.formule = None

        def list_records(self, filter_by_formula=None, **_):
            self.formule = filter_by_formula
            return self.lignes

    def ligne(self, ident, quand):
        return {"id": ident, "createdTime": quand, "fields": {}}

    def test_la_plus_recente_gagne_quel_que_soit_l_ordre_rendu(self):
        table = self.Table([self.ligne("recVIEILLE", "2026-08-28T13:38:44.000Z"),
                            self.ligne("recNEUVE", "2026-08-28T13:46:03.000Z")])
        assert parcours.derniere_reponse(table, "recF")["id"] == "recNEUVE"

        table.lignes.reverse()
        assert parcours.derniere_reponse(table, "recF")["id"] == "recNEUVE"

    def test_la_recherche_passe_par_le_record_id(self):
        table = self.Table([self.ligne("recA", "2026-08-28T13:00:00.000Z")])
        parcours.derniere_reponse(table, "recF")
        assert parcours.CHAMP_FICHE in table.formule and "recF" in table.formule

    def test_aucune_reponse_rend_rien(self):
        assert parcours.derniere_reponse(self.Table([]), "recF") is None
