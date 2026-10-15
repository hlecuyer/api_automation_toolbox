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

    Sans ça, les sept autres tables du périmètre réel manqueraient dans les deux
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


class TestEcartsDeclares:
    def test_ecart_declare_nomme_sans_sortir_en_rouge(self, capsys, monkeypatch):
        """Un écart assumé reste annoncé à chaque passage, mais ne sonne plus l'alarme."""
        monkeypatch.setattr(bac, "ECARTS_CONNUS", {("Annuaire", "Vestige"): "raison assumée"})
        ref = [table("Annuaire", [champ("E-mail", "email")])]
        cible = [table("Annuaire", [champ("E-mail", "email"),
                                    champ("Vestige", "singleLineText")])]
        code, sortie = comparer(ref, cible, capsys)
        assert code == 0
        assert "déclaré" in sortie and "Vestige" in sortie and "raison assumée" in sortie

    def test_ecart_nouveau_sur_la_meme_table_sort_toujours_en_rouge(self, capsys, monkeypatch):
        monkeypatch.setattr(bac, "ECARTS_CONNUS", {("Annuaire", "Vestige"): "raison assumée"})
        ref = [table("Annuaire", [champ("E-mail", "email"), champ("Prénom", "singleLineText")])]
        cible = [table("Annuaire", [champ("E-mail", "email"), champ("Vestige", "singleLineText")])]
        code, sortie = comparer(ref, cible, capsys)
        assert code == 1
        assert "manquant" in sortie and "Prénom" in sortie

    def test_declaration_obsolete_est_signalee(self, capsys, monkeypatch):
        """Une déclaration qui ne mord plus doit se retirer, sinon elle pourrit le filtre."""
        monkeypatch.setattr(bac, "ECARTS_CONNUS", {("Annuaire", "Fantôme"): "raison oubliée"})
        t = [table("Annuaire", [champ("E-mail", "email")])]
        code, sortie = comparer(t, t, capsys)
        assert code == 0
        assert "à retirer" in sortie and "Fantôme" in sortie


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
            "Mise à jour fiche", "Centres d'intérêt",
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


class FauxOvh:
    """Sert des règles d'accès et des abonnés, sans réseau."""

    def __init__(self, regles, abonnes=None, refuse_delete=False):
        self.regles = regles
        self.abonnes = list(abonnes or [])
        self.refuse_delete = refuse_delete
        self.supprimes = []

    def get(self, chemin):
        if chemin == "/auth/currentCredential":
            return {"status": "validated", "rules": self.regles}
        return list(self.abonnes)

    def delete(self, chemin):
        if self.refuse_delete:
            raise RuntimeError("This call has not been granted")
        adresse = chemin.rsplit("/", 1)[-1]
        self.supprimes.append(adresse)
        self.abonnes = [a for a in self.abonnes if a.lower() != adresse.lower()]


class FauxClientListe:
    def __init__(self, ovh, accepte=True):
        self.ovh, self.accepte, self.ajoutes = ovh, accepte, []

    def add_subscriber(self, email):
        if not self.accepte:
            return False
        self.ajoutes.append(email)
        self.ovh.abonnes.append(email)
        return True


def regles(*chemins, methode="GET"):
    return [{"method": methode, "path": c} for c in chemins]


CONFINEE = regles(
    "/email/domain/d.org/mailingList/bac-a-sable",
    "/email/domain/d.org/mailingList/bac-a-sable/*",
)


class TestOvh:
    """La clé est le seul contrôle qui porte sur une garantie, pas sur un état."""

    @pytest.fixture(autouse=True)
    def sans_attente(self, monkeypatch):
        monkeypatch.setattr(bac, "RELECTURES", 1)
        monkeypatch.setattr(bac, "ATTENTE", 0)

    def lancer(self, ovh, capsys, liste_prod=None, appliquer=False, client=None):
        code = bac.verifier_ovh(ovh, client or FauxClientListe(ovh), "d.org",
                                "bac-a-sable", liste_prod, appliquer)
        return code, capsys.readouterr().out

    def test_regle_trop_large_refusee(self, capsys):
        """Une règle sur /mailingList/* couvre aussi la liste des adhérents réels."""
        o = FauxOvh(regles("/email/domain/d.org/mailingList/*"))
        code, sortie = self.lancer(o, capsys)
        assert code == 1
        assert "déborde" in sortie and "la ceinture n'en est pas une" in sortie

    def test_une_liste_au_nom_voisin_ne_passe_pas(self, capsys):
        """« bac-a-sable-autre » ne doit pas passer pour « bac-a-sable »."""
        o = FauxOvh(regles("/email/domain/d.org/mailingList/bac-a-sable-autre/*"))
        code, _ = self.lancer(o, capsys)
        assert code == 1

    def test_liste_de_production_refusee(self, capsys):
        o = FauxOvh(CONFINEE)
        code, sortie = self.lancer(o, capsys, liste_prod="bac-a-sable")
        assert code == 1
        assert "EST celle de production" in sortie

    def test_le_refus_arrete_avant_de_lire(self, capsys):
        """Rien ne doit être tenté avec une clé dont on sait qu'elle déborde."""
        o = FauxOvh(regles("/email/domain/d.org/mailingList/*"), abonnes=["x@example.org"])
        code, sortie = self.lancer(o, capsys, appliquer=True)
        assert code == 1
        assert "2. La liste" not in sortie
        assert o.supprimes == []

    def test_adresse_reelle_signalee(self, capsys):
        o = FauxOvh(CONFINEE, abonnes=["vrai@gmail.com", "faux@example.org"])
        code, sortie = self.lancer(o, capsys)
        assert code == 1
        assert "domaine réel" in sortie

    def test_lecture_seule_sans_appliquer(self, capsys):
        o = FauxOvh(CONFINEE, abonnes=["faux@example.org"])
        code, sortie = self.lancer(o, capsys)
        assert code == 0
        assert "écriture non prouvée" in sortie
        assert o.supprimes == []

    def test_aller_retour_complet(self, capsys):
        o = FauxOvh(CONFINEE)
        client = FauxClientListe(o)
        code, sortie = self.lancer(o, capsys, appliquer=True, client=client)
        assert code == 0
        assert client.ajoutes == ["temoin-bac-a-sable@example.org"]
        assert o.supprimes == ["temoin-bac-a-sable@example.org"]
        assert o.abonnes == []
        assert "état trouvé" in sortie

    def test_abonnement_refuse(self, capsys):
        o = FauxOvh(CONFINEE)
        code, sortie = self.lancer(o, capsys, appliquer=True,
                                   client=FauxClientListe(o, accepte=False))
        assert code == 1
        assert "abonnement refusé" in sortie

    def test_suppression_refusee(self, capsys):
        o = FauxOvh(CONFINEE, abonnes=["temoin-bac-a-sable@example.org"], refuse_delete=True)
        code, sortie = self.lancer(o, capsys, appliquer=True)
        assert code == 1
        assert "suppression refusée" in sortie

    def test_le_temoin_deja_present_ne_provoque_pas_de_doublon(self, capsys):
        """Il prouve au passage que l'ajout du passage précédent s'est appliqué."""
        o = FauxOvh(CONFINEE, abonnes=["temoin-bac-a-sable@example.org"])
        client = FauxClientListe(o)
        code, sortie = self.lancer(o, capsys, appliquer=True, client=client)
        assert code == 0
        assert client.ajoutes == []
        assert "l'ajout s'applique bien" in sortie


class TestConfinement:
    @pytest.mark.parametrize("chemin,attendu", [
        ("/email/domain/d.org/mailingList/bac-a-sable", True),
        ("/email/domain/d.org/mailingList/bac-a-sable/subscriber", True),
        ("/email/domain/d.org/mailingList/bac-a-sable/*", True),
        ("/email/domain/d.org/mailingList/*", False),
        ("/email/domain/d.org/mailingList/membres/*", False),
        ("/email/domain/d.org/mailingList/bac-a-sable-autre/*", False),
        ("/*", False),
    ])
    def test_confinee(self, chemin, attendu):
        assert bac._confinee(chemin, "d.org", "bac-a-sable") is attendu


# --------------------------------------------------------------------------
# L'exception déclarée — une adresse qui peut vraiment recevoir
# --------------------------------------------------------------------------
#
# Prouver qu'un mail de bienvenue arrive demande une adresse capable de
# recevoir, ce qu'aucun domaine réservé ne peut être. L'invariant « aucune
# adresse réelle » s'ouvre donc, mais de la façon la plus étroite possible :
# nominative, déclarée, et nommée à chaque passage. Ce qui est testé ici est
# surtout ce qui doit rester fermé.


class FauxAirtableAvecFiches(FauxAirtable):
    def __init__(self, schemas, fiches):
        super().__init__(schemas)
        self.fiches = fiches

    def enregistrements(self, base, table, champs=None):
        return self.fiches


def annuaire(adresses):
    return {"appBAC": [table("Annuaire", [champ("E-mail", "email")])]}, [
        {"id": "rec%d" % i, "fields": {"E-mail": a}} for i, a in enumerate(adresses)
    ]


class TestAdressesDeControle:
    def test_lues_dans_l_environnement(self, monkeypatch):
        monkeypatch.setenv(bac.VARIABLE_ADRESSES_DE_CONTROLE, "Hugo@DSI.coop , a@b.fr")
        assert bac.adresses_de_controle() == {"hugo@dsi.coop", "a@b.fr"}

    def test_l_argument_prime_sur_l_environnement(self, monkeypatch):
        monkeypatch.setenv(bac.VARIABLE_ADRESSES_DE_CONTROLE, "a@b.fr")
        assert bac.adresses_de_controle(["c@d.fr"]) == {"c@d.fr"}

    @pytest.mark.parametrize("motif", ["*@dsi.coop", "*", "*@*", "dsi.coop"])
    def test_un_motif_est_refuse(self, motif, monkeypatch, capsys):
        """Un motif rouvrirait l'invariant à un domaine entier, et la première
        adresse d'adhérent qui y atterrirait passerait inaperçue."""
        monkeypatch.delenv(bac.VARIABLE_ADRESSES_DE_CONTROLE, raising=False)
        assert bac.adresses_de_controle([motif]) == set()
        assert "ignorée" in capsys.readouterr().err

    def test_rien_de_declare_par_defaut(self, monkeypatch):
        monkeypatch.delenv(bac.VARIABLE_ADRESSES_DE_CONTROLE, raising=False)
        assert bac.adresses_de_controle() == set()


class TestVerifierAvecException:
    def lancer(self, adresses, controle, capsys):
        schemas, fiches = annuaire(adresses)
        code = bac.verifier(FauxAirtableAvecFiches(schemas, fiches), "appBAC",
                            controle=controle)
        return code, capsys.readouterr().out

    def test_une_adresse_declaree_ne_fait_pas_echouer(self, capsys):
        code, sortie = self.lancer(["a@example.org", "hugo@dsi.coop"],
                                   {"hugo@dsi.coop"}, capsys)
        assert code == 0
        assert "adresse(s) de contrôle déclarée(s)" in sortie

    def test_elle_est_nommee_a_chaque_passage(self, capsys):
        """Une brèche silencieuse cesse d'être une brèche pour devenir un trou."""
        _, sortie = self.lancer(["hugo@dsi.coop"], {"hugo@dsi.coop"}, capsys)
        assert "hugo@dsi.coop" in sortie
        assert "À retirer quand la démonstration est faite" in sortie

    def test_une_adresse_reelle_non_declaree_fait_toujours_echouer(self, capsys):
        code, sortie = self.lancer(["a@example.org", "adherent@coopdescommuns.org"],
                                   {"hugo@dsi.coop"}, capsys)
        assert code == 1
        assert "domaine réel" in sortie

    def test_l_exception_ne_s_etend_pas_au_domaine(self, capsys):
        code, _ = self.lancer(["autre@dsi.coop"], {"hugo@dsi.coop"}, capsys)
        assert code == 1

    def test_sans_exception_le_comportement_est_inchange(self, capsys):
        code, sortie = self.lancer(["a@example.org"], set(), capsys)
        assert code == 0
        assert "adresse(s) de contrôle" not in sortie
