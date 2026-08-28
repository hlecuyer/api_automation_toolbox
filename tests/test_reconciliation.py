"""Tests de la réconciliation du formulaire de mise à jour de fiche.

Ce module écrit dans les fiches d'adhérents réels à partir de ce qu'ils ont
saisi. Ce qui est vérifié ici est donc d'abord **ce qu'il ne doit pas faire** :
effacer une donnée parce qu'une case a été laissée vide, faire échouer une
écriture entière sur une valeur inattendue, ou abandonner les autres réponses à
cause d'une seule.

Les trois défauts que ces tests décrivent ont tous été rencontrés sur ce projet
en août 2026, sur d'autres chemins de code. Ils ne sont pas hypothétiques.
"""

from unittest.mock import Mock, patch

import pytest

from src import reconciliation
from src.reconciliation import (
    CHAMP_DATE_MAJ,
    CHAMP_FICHE,
    CHAMP_SYNCHRONISE,
    Reconciliation,
    payload_depuis_reponse,
)


def reponse(fiche="recFICHE", quand="2026-08-28T09:00:00.000Z", **champs):
    fields = dict(champs)
    if fiche is not None:
        fields[CHAMP_FICHE] = fiche
    return {"id": "recREP", "createdTime": quand, "fields": fields}


class FauxAnnuaire:
    """Le client de l'Annuaire, sans réseau."""

    def __init__(self, refuse=()):
        self.refuse = set(refuse)
        self.ecritures = []
        self.normalized_fields = {}

    def normaliser_champs(self, fields):
        # Le vrai client ramène les variantes sur la valeur du référentiel.
        if "Genre" in fields and fields["Genre"] in ("H", "M"):
            fields["Genre"] = "Masculin"

    def update_record(self, record_id, fields, dry_run=False):
        if record_id in self.refuse:
            return None
        self.ecritures.append((record_id, dict(fields)))
        return {"id": record_id, "fields": fields}


class FauxReponses:
    def __init__(self, lignes, refuse_marquage=False):
        self.lignes = lignes
        self.refuse_marquage = refuse_marquage
        self.marquees = []
        self.formule = None

    def list_records(self, filter_by_formula=None, **_):
        self.formule = filter_by_formula
        return self.lignes

    def update_record(self, record_id, fields, dry_run=False):
        if self.refuse_marquage:
            return None
        self.marquees.append((record_id, fields))
        return {"id": record_id}


def passer(lignes, refuse=(), refuse_marquage=False, dry_run=False):
    annuaire = FauxAnnuaire(refuse)
    reponses = FauxReponses(lignes, refuse_marquage)
    compteurs = Reconciliation(annuaire, reponses).passer(dry_run=dry_run)
    return compteurs, annuaire, reponses


# --------------------------------------------------------------------------
# Ce qui est recopié, et ce qui ne l'est pas
# --------------------------------------------------------------------------

class TestPayload:
    def test_les_champs_techniques_ne_partent_pas(self):
        """`record_id` et `Synchronisé` décrivent la réponse, pas l'adhérent."""
        payload = payload_depuis_reponse(
            {CHAMP_FICHE: "recX", CHAMP_SYNCHRONISE: True, "Prénom": "Prosper"})
        assert payload == {"Prénom": "Prosper"}

    @pytest.mark.parametrize("vide", [None, "", [], {}])
    def test_une_reponse_vide_ne_touche_pas_la_colonne(self, vide):
        """Une case laissée blanche ne veut pas dire « efface ce que tu sais de
        moi ». C'est la règle la plus importante du module."""
        assert payload_depuis_reponse({"Téléphone": vide}) == {}

    def test_un_faux_booleen_est_une_reponse(self):
        """`False` dit quelque chose, contrairement à une chaîne vide."""
        assert payload_depuis_reponse({"Visible sur le site": False}) == {
            "Visible sur le site": False}

    def test_un_zero_est_une_reponse(self):
        assert payload_depuis_reponse({"code postal": 0}) == {"code postal": 0}

    def test_le_rapprochement_est_une_identite(self):
        """La table de réponses est dérivée du schéma de l'Annuaire : il n'y a
        pas de table de correspondance, donc rien qui puisse diverger."""
        champs = {"Prénom": "P", "Genre": "Féminin", "Structure(s)": ["recS"],
                  "Type": ["Chercheur·se"], CHAMP_FICHE: "recX"}
        assert payload_depuis_reponse(champs) == {
            "Prénom": "P", "Genre": "Féminin", "Structure(s)": ["recS"],
            "Type": ["Chercheur·se"]}


# --------------------------------------------------------------------------
# Le passage
# --------------------------------------------------------------------------

@patch("src.reconciliation.syslog")
class TestPassage:
    def test_cas_nominal(self, _syslog):
        compteurs, annuaire, reponses = passer([reponse(Prénom="Prosper")])

        assert compteurs == {"màj_reçues": 1, "màj_appliquées": 1, "erreurs": 0}
        fiche, champs = annuaire.ecritures[0]
        assert fiche == "recFICHE"
        assert champs["Prénom"] == "Prosper"
        assert reponses.marquees == [("recREP", {CHAMP_SYNCHRONISE: True})]

    def test_seules_les_reponses_non_synchronisees_sont_lues(self, _syslog):
        _, _, reponses = passer([])
        assert CHAMP_SYNCHRONISE in reponses.formule
        assert reponses.formule.startswith("NOT(")

    def test_la_date_de_suivi_part_avec_le_reste(self, _syslog):
        """Une écriture, pas deux : si elle échoue, la fiche n'est pas marquée à
        jour et la réponse sera retentée."""
        _, annuaire, _ = passer([reponse(quand="2026-08-28T09:00:00.000Z")])
        assert annuaire.ecritures[0][1][CHAMP_DATE_MAJ] == "2026-08-28"

    def test_le_referentiel_est_applique(self, _syslog):
        """Sans `typecast`, une valeur hors options fait échouer l'écriture
        entière. Le référentiel de l'Annuaire vaut donc aussi ici."""
        _, annuaire, _ = passer([reponse(Genre="H")])
        assert annuaire.ecritures[0][1]["Genre"] == "Masculin"

    def test_une_reponse_entierement_vide_est_quand_meme_un_acte(self, _syslog):
        """L'adhérent a ouvert le formulaire et validé sans rien changer : sa
        fiche est à jour, il ne doit plus être relancé."""
        compteurs, annuaire, reponses = passer([reponse()])

        assert compteurs["màj_appliquées"] == 1
        assert annuaire.ecritures[0][1] == {CHAMP_DATE_MAJ: "2026-08-28"}
        assert reponses.marquees


@patch("src.reconciliation.syslog")
class TestResistance:
    def test_une_reponse_sans_fiche_est_une_erreur_pas_une_panne(self, _syslog):
        compteurs, annuaire, reponses = passer([reponse(fiche=None, Prénom="P")])

        assert compteurs == {"màj_reçues": 1, "màj_appliquées": 0, "erreurs": 1}
        assert annuaire.ecritures == []
        assert reponses.marquees == []

    def test_une_ligne_fautive_n_arrete_pas_les_autres(self, _syslog):
        """Le défaut mesuré le 28/08 sur le cron des listes : une adresse
        refusée privait les 24 listes de synchronisation."""
        lignes = [
            {"id": "r1", "createdTime": "2026-08-28T09:00:00.000Z",
             "fields": {CHAMP_FICHE: "recA", "Prénom": "A"}},
            {"id": "r2", "createdTime": "2026-08-28T09:00:00.000Z",
             "fields": {"Prénom": "B"}},                      # sans record_id
            {"id": "r3", "createdTime": "2026-08-28T09:00:00.000Z",
             "fields": {CHAMP_FICHE: "recC", "Prénom": "C"}},
        ]
        compteurs, annuaire, _ = passer(lignes)

        assert compteurs == {"màj_reçues": 3, "màj_appliquées": 2, "erreurs": 1}
        assert [f for f, _ in annuaire.ecritures] == ["recA", "recC"]

    def test_une_exception_sur_une_ligne_laisse_passer_les_suivantes(self, _syslog):
        annuaire = FauxAnnuaire()
        annuaire.update_record = Mock(side_effect=[RuntimeError("boum"),
                                                   {"id": "recB"}])
        reponses = FauxReponses([
            {"id": "r1", "createdTime": "2026-08-28T09:00:00.000Z",
             "fields": {CHAMP_FICHE: "recA"}},
            {"id": "r2", "createdTime": "2026-08-28T09:00:00.000Z",
             "fields": {CHAMP_FICHE: "recB"}},
        ])
        compteurs = Reconciliation(annuaire, reponses).passer()

        assert compteurs == {"màj_reçues": 2, "màj_appliquées": 1, "erreurs": 1}

    def test_ecriture_refusee_la_reponse_reste_a_retenter(self, _syslog):
        """Ne pas marquer une réponse qu'on n'a pas su appliquer : le passage
        suivant la rejouera, et l'erreur reste visible dans la ligne de vie."""
        compteurs, _, reponses = passer([reponse(Prénom="P")], refuse={"recFICHE"})

        assert compteurs["erreurs"] == 1
        assert reponses.marquees == []

    def test_marquage_refuse_la_fiche_reste_a_jour(self, _syslog):
        """La fiche est écrite, la réponse sera rejouée : réécrire les mêmes
        valeurs est sans effet, donc rien n'est perdu."""
        compteurs, annuaire, _ = passer([reponse(Prénom="P")], refuse_marquage=True)

        assert compteurs["màj_appliquées"] == 1
        assert annuaire.ecritures[0][1]["Prénom"] == "P"

    def test_lecture_impossible_ne_leve_pas(self, _syslog):
        annuaire, reponses = FauxAnnuaire(), FauxReponses([])
        reponses.list_records = Mock(side_effect=RuntimeError("Airtable HS"))

        compteurs = Reconciliation(annuaire, reponses).passer()

        assert compteurs == {"màj_reçues": 0, "màj_appliquées": 0, "erreurs": 1}


@patch("src.reconciliation.syslog")
class TestSimulation:
    def test_le_dry_run_n_ecrit_rien(self, _syslog):
        compteurs, annuaire, reponses = passer([reponse(Prénom="P")], dry_run=True)

        assert compteurs["màj_appliquées"] == 1
        assert annuaire.ecritures == []
        assert reponses.marquees == []


class TestDate:
    def test_la_date_vient_de_createdTime(self):
        """Aucun champ ne stocke la date de soumission : Airtable la donne déjà.
        Une donnée qu'on n'a pas à tenir ne peut pas être fausse."""
        assert reconciliation._date_de(
            {"createdTime": "2026-08-28T09:13:20.000Z"}) == "2026-08-28"

    def test_sans_createdTime_on_prend_aujourd_hui(self):
        from datetime import datetime
        assert reconciliation._date_de({}) == datetime.now().strftime("%Y-%m-%d")
