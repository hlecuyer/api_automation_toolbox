"""Tests de l'outillage du bac à sable.

Un détecteur de dérive auquel on ne peut pas se fier est pire que pas de
détecteur : il produit de la fausse tranquillité. Ce qui est vérifié ici, c'est
qu'il **voit** les trois formes d'écart qui comptent — champ manquant, type
changé, option de liste déroulante absente — et qu'il ne se laisse pas piéger
par les deux irrégularités réelles de cette base : deux champs portant le même
nom dans une table, et plusieurs adresses dans une même cellule.
"""

import importlib.util
from pathlib import Path

import pytest

CHEMIN = Path(__file__).parent.parent / "scripts" / "bac_a_sable.py"
_spec = importlib.util.spec_from_file_location("bac_a_sable", CHEMIN)
bac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bac)


def champ(nom, type_, options=None):
    c = {"name": nom, "type": type_}
    if options is not None:
        c["options"] = {"choices": [{"name": o} for o in options]}
    return c


def table(nom, champs):
    return {"name": nom, "id": "tbl" + nom[:6], "fields": champs}


class FauxAirtable:
    """Sert deux schémas sans réseau."""

    def __init__(self, schemas):
        self.schemas = schemas

    def schema(self, base):
        return self.schemas[base]


@pytest.fixture(autouse=True)
def perimetre_reduit(monkeypatch):
    """Les cas synthétiques ne parlent que de l'Annuaire.

    Sans ça, les cinq autres tables du périmètre réel manqueraient dans les deux
    schémas et compteraient comme des écarts : tous les tests passeraient au
    vert pour la mauvaise raison.
    """
    monkeypatch.setattr(bac, "TABLES_UTILES", ["Annuaire"])


def comparer(ref_tables, bac_tables, capsys):
    at = FauxAirtable({"appREF": ref_tables, "appBAC": bac_tables})
    code = bac.comparer(at, "appREF", "appBAC")
    return code, capsys.readouterr().out


class TestAdresses:
    """« Mail optionnel » peut contenir plusieurs adresses séparées par des virgules."""

    def test_champ_multiple_decoupe(self):
        fiche = {"Mail optionnel": "a@x.fr, b@x.fr ; c@x.fr"}
        assert bac._adresses(fiche) == ["a@x.fr", "b@x.fr", "c@x.fr"]

    def test_les_trois_champs_sont_lus(self):
        fiche = {"E-mail": "A@X.FR", "Mail optionnel": "b@x.fr",
                 "Ancien courriel": "c@x.fr"}
        assert bac._adresses(fiche) == ["a@x.fr", "b@x.fr", "c@x.fr"]

    def test_valeurs_absentes_ou_non_textuelles(self):
        assert bac._adresses({}) == []
        assert bac._adresses({"E-mail": None, "Mail optionnel": ["a@x.fr"]}) == []


class TestNomsDupliques:
    """La production a deux champs « Annuaire copy » dans la même table."""

    def test_les_deux_sont_conserves(self):
        t = table("T", [champ("doublon", "singleLineText"),
                        champ("doublon", "multipleRecordLinks")])
        index = bac._par_nom(t)
        assert sorted(c["type"] for c in index["doublon"]) == [
            "multipleRecordLinks", "singleLineText"]

    def test_un_doublon_manquant_est_vu_comme_ecart_de_type(self, capsys):
        ref = [table("Annuaire", [champ("doublon", "singleLineText"),
                                  champ("doublon", "multipleRecordLinks")])]
        cible = [table("Annuaire", [champ("doublon", "singleLineText")])]
        code, sortie = comparer(ref, cible, capsys)
        assert code == 1
        assert "type" in sortie and "doublon" in sortie


class TestDerive:
    def test_table_absente(self, capsys):
        ref = [table("Annuaire", [champ("E-mail", "email")])]
        code, sortie = comparer(ref, [], capsys)
        assert code == 1
        assert "« Annuaire » absente du bac à sable" in sortie

    def test_champ_manquant(self, capsys):
        ref = [table("Annuaire", [champ("E-mail", "email"), champ("Prénom", "singleLineText")])]
        cible = [table("Annuaire", [champ("E-mail", "email")])]
        code, sortie = comparer(ref, cible, capsys)
        assert code == 1
        assert "manquant" in sortie and "Prénom" in sortie

    def test_champ_calcule_manquant_est_signale_comme_manuel(self, capsys):
        """L'API ne sait pas les créer : le dire évite de chercher pourquoi ça échoue."""
        ref = [table("Annuaire", [champ("record_id", "formula")])]
        code, sortie = comparer(ref, [table("Annuaire", [])], capsys)
        assert "à poser à la main" in sortie

    def test_type_different(self, capsys):
        """Le cas réel : un champ lié devenu du texte simple."""
        ref = [table("Annuaire", [champ("Groupe(s)", "multipleRecordLinks")])]
        cible = [table("Annuaire", [champ("Groupe(s)", "singleLineText")])]
        code, sortie = comparer(ref, cible, capsys)
        assert code == 1
        assert "multipleRecordLinks" in sortie and "singleLineText" in sortie

    def test_option_de_select_absente(self, capsys):
        """Sans typecast, une option manquante fait échouer l'écriture entière."""
        ref = [table("Annuaire", [champ("Genre", "singleSelect", ["Masculin", "Féminin"])])]
        cible = [table("Annuaire", [champ("Genre", "singleSelect", ["Masculin"])])]
        code, sortie = comparer(ref, cible, capsys)
        assert code == 1
        assert "options" in sortie and "Féminin" in sortie

    def test_option_en_trop_signalee_sans_confondre(self, capsys):
        ref = [table("Annuaire", [champ("Genre", "singleSelect", ["Masculin"])])]
        cible = [table("Annuaire", [champ("Genre", "singleSelect", ["Masculin", "H"])])]
        code, sortie = comparer(ref, cible, capsys)
        assert "en trop : H" in sortie

    def test_aucun_ecart(self, capsys):
        t = [table("Annuaire", [champ("E-mail", "email"),
                                champ("Genre", "singleSelect", ["Masculin"])])]
        code, sortie = comparer(t, t, capsys)
        assert code == 0
        assert "aucun écart" in sortie

    def test_les_vestiges_sont_nommes_pas_tus(self, capsys):
        """Un écart tu deviendrait une surprise ; celui-là est annoncé."""
        ref = [table("Annuaire", []), table("Vote AG 2023", [])]
        code, sortie = comparer(ref, [table("Annuaire", [])], capsys)
        assert "Hors périmètre" in sortie and "Vote AG 2023" in sortie


class TestPerimetre:
    def test_le_perimetre_reel_couvre_ce_que_le_code_touche(self, monkeypatch):
        """Annuaire et ses tables liées, plus celles que la Coop utilise.

        Écrit en dur ici pour qu'un rétrécissement du périmètre soit un choix
        visible en revue, jamais un effet de bord.
        """
        monkeypatch.undo()
        assert bac.TABLES_UTILES == [
            "Annuaire", "Liste des groupes", "Structures", "Liste Diffusion",
            "Ajout à un groupe", "Partenaires",
        ]


class TestOptions:
    def test_non_select_rend_none(self):
        assert bac._options(champ("E-mail", "email")) is None

    def test_select_sans_options(self):
        assert bac._options({"name": "x", "type": "singleSelect"}) == []


class TestIdentitesFictives:
    def test_accents_retires_pour_l_adresse(self):
        assert bac._sans_accent("Élodie") == "Elodie"
        assert bac._sans_accent("Gaëlle") == "Gaelle"

    def test_les_domaines_fictifs_sont_reserves(self):
        """RFC 2606 : ces domaines n'ont pas de MX, donc rien ne peut être délivré."""
        for domaine in bac.DOMAINES_FICTIFS:
            assert domaine.startswith("example.")

    def test_assez_d_identites_distinctes(self):
        assert len(bac.PRENOMS) * len(bac.NOMS) >= 400

    def test_le_groupe_reel_est_le_premier(self):
        """Le code cherche ce groupe par son nom : le bac à sable doit le porter."""
        assert bac.GROUPES[0]["Nom"] == "Adhérent·es la Coop des Communs"

    def test_les_labels_sont_prefixes(self):
        """Un label est un nom de liste OVH, et l'extracteur vide ce qu'il aligne.

        Un label de bac à sable qui coïnciderait avec une vraie liste OVH ferait
        supprimer ses abonnés réels au profit d'adresses fictives.
        """
        for groupe in bac.GROUPES:
            if "Label" in groupe:
                assert groupe["Label"].startswith("bac-a-sable")

    def test_un_seul_groupe_reclame_une_liste_ovh(self):
        """Label absent = groupe ignoré par l'extracteur, donc pas d'erreur à vide."""
        assert sum(1 for g in bac.GROUPES if g.get("Label")) == 1


class FauxClientHelloAsso:
    """Sert des définitions de formulaire sans réseau."""

    def __init__(self, formulaires):
        self.formulaires = formulaires

    def get_form_details(self, titre):
        if titre not in self.formulaires:
            return {}
        return {"formType": "Membership", "formSlug": titre}

    def get_public_form(self, form_type, form_slug):
        return {"tiers": [{"customFields": [
            {"label": l, "type": "TextInput"} for l in self.formulaires[form_slug]]}]}


class TestContratDuFormulaire:
    """Un libellé qui diffère d'un caractère ne lève rien : la réponse est ignorée."""

    @pytest.fixture
    def contrat(self, monkeypatch):
        from src.models import user_subscription
        monkeypatch.setattr(user_subscription, "CHAMPS_HELLOASSO_VERS_AIRTABLE",
                            {"Genre": "Genre", "Consentement": "Règles"})

    def lancer(self, contrat, formulaires, reference, test, capsys):
        client = FauxClientHelloAsso(formulaires)
        code = bac.formulaire(client, reference, test)
        return code, capsys.readouterr().out

    def test_contrat_honore(self, contrat, capsys):
        f = {"prod": ["Genre", "Consentement"], "test": ["Genre", "Consentement"]}
        code, sortie = self.lancer(contrat, f, "prod", "test", capsys)
        assert code == 0
        assert "honoré de bout en bout" in sortie

    def test_libelle_absent_de_la_reference_est_signale(self, contrat, capsys):
        """Le cas réel : le code attend un libellé que le formulaire ne pose pas."""
        f = {"prod": ["Genre", "Consentement aux règles de confidentialité"]}
        code, sortie = self.lancer(contrat, f, "prod", None, capsys)
        assert code == 1
        assert "absent de la RÉFÉRENCE" in sortie

    def test_le_libelle_proche_est_proposé(self, contrat, capsys):
        """Nommer le candidat évite d'avoir à le deviner dans l'interface."""
        f = {"prod": ["Genre", "Consentement aux règles de confidentialité "]}
        code, sortie = self.lancer(contrat, f, "prod", None, capsys)
        assert "candidat publié" in sortie
        assert repr("Consentement aux règles de confidentialité ") in sortie

    def test_libelle_absent_du_formulaire_de_test(self, contrat, capsys):
        f = {"prod": ["Genre", "Consentement"], "test": ["Genre"]}
        code, sortie = self.lancer(contrat, f, "prod", "test", capsys)
        assert code == 1
        assert "du formulaire de TEST" in sortie

    def test_question_en_trop_dans_le_test_est_seulement_notée(self, contrat, capsys):
        f = {"prod": ["Genre", "Consentement"], "test": ["Genre", "Consentement", "Bonus"]}
        code, sortie = self.lancer(contrat, f, "prod", "test", capsys)
        assert code == 0
        assert "posée dans le test seulement" in sortie

    def test_formulaire_introuvable(self, contrat, capsys):
        with pytest.raises(SystemExit):
            self.lancer(contrat, {"prod": ["Genre"]}, "absent", None, capsys)
