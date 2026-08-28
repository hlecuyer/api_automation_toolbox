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

# Les libellés du formulaire sont des phrases : ils ne peuvent pas être passés
# en arguments nommés. Les quelques-uns dont ces tests ont besoin, écrits une
# fois — et écrits en dur, parce que c'est le contrat que le module tient.
Q_PRENOM = "Quel est votre prénom ?"
Q_GENRE = "Quel est votre genre ?"


def reponse(champs=None, fiche="recFICHE", quand="2026-08-28T09:00:00.000Z"):
    fields = dict(champs or {})
    if fiche is not None:
        fields[CHAMP_FICHE] = fiche
    return {"id": "recREP", "createdTime": quand, "fields": fields}


class FauxAnnuaire:
    """Le client de l'Annuaire, sans réseau."""

    def __init__(self, refuse=(), disparues=()):
        self.refuse = set(refuse)
        self.disparues = set(disparues)
        self.ecritures = []
        self.normalized_fields = {}

    def normaliser_champs(self, fields):
        # Le vrai client ramène les variantes sur la valeur du référentiel.
        if "Genre" in fields and fields["Genre"] in ("H", "M"):
            fields["Genre"] = "Masculin"

    def list_records(self, filter_by_formula=None, **_):
        # Une fiche refusée existe quand même : c'est un refus, pas une
        # disparition. Les fiches disparues sont déclarées séparément.
        return [] if any(d in (filter_by_formula or "") for d in self.disparues) else [{"id": "recX"}]

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


def passer(lignes, refuse=(), refuse_marquage=False, dry_run=False, disparues=()):
    annuaire = FauxAnnuaire(refuse, disparues)
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
            {CHAMP_FICHE: "recX", CHAMP_SYNCHRONISE: True, Q_PRENOM: "Prosper"})
        assert payload == {"Prénom": "Prosper"}

    @pytest.mark.parametrize("vide", [None, "", [], {}])
    def test_une_reponse_vide_ne_touche_pas_la_colonne(self, vide):
        """Une case laissée blanche ne veut pas dire « efface ce que tu sais de
        moi ». C'est la règle la plus importante du module."""
        assert payload_depuis_reponse(
            {"À quel numéro peut-on vous joindre ?": vide}) == {}

    def test_un_faux_booleen_est_une_reponse(self):
        """`False` dit quelque chose, contrairement à une chaîne vide."""
        assert payload_depuis_reponse(
            {"Souhaitez-vous que votre nom et votre prénom apparaissent sur le "
             "site de la Coop ?": False}) == {"Visible sur le site": False}

    def test_un_zero_est_une_reponse(self):
        assert payload_depuis_reponse(
            {"Quel est votre code postal ?": 0}) == {"code postal": 0}

    def test_les_libelles_sont_traduits_en_colonnes(self):
        """Le formulaire pose des questions lisibles ; l'Annuaire porte des noms
        de colonnes. La correspondance est déclarée une seule fois."""
        champs = {Q_PRENOM: "P",
                  "Dans quelle structure travaillez-vous ?": ["recS"],
                  "Vous êtes plutôt…": ["Chercheur·se"],
                  "Quelles sont les deux personnes que vous connaissez le mieux "
                  "à la Coop ?": "Nicole, Vera",
                  CHAMP_FICHE: "recX"}
        assert payload_depuis_reponse(champs) == {
            "Prénom": "P", "Structure(s)": ["recS"],
            "Type": ["Chercheur·se"], "2 personnes connues": "Nicole, Vera"}

    def test_un_libelle_inconnu_est_ignore(self):
        """Une question ajoutée au formulaire sans être déclarée ne doit pas
        faire échouer l'écriture des autres réponses : sans `typecast`, une
        colonne inexistante suffirait."""
        assert payload_depuis_reponse(
            {Q_PRENOM: "P", "Question ajoutée à la main": "oui"}) == {"Prénom": "P"}

    def test_toutes_les_colonnes_visees_sont_distinctes(self):
        """Deux questions qui viseraient la même colonne s'écraseraient l'une
        l'autre, selon l'ordre du dictionnaire — donc au hasard."""
        colonnes = [c for _, c, _ in reconciliation.CHAMPS_FORMULAIRE]
        assert len(colonnes) == len(set(colonnes))


# --------------------------------------------------------------------------
# Le passage
# --------------------------------------------------------------------------

@patch("src.reconciliation.syslog")
class TestPassage:
    def test_cas_nominal(self, _syslog):
        compteurs, annuaire, reponses = passer([reponse({Q_PRENOM: "Prosper"})])

        assert compteurs == {"màj_reçues": 1, "màj_appliquées": 1, "orphelines": 0, "erreurs": 0}
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
        _, annuaire, _ = passer([reponse({Q_GENRE: "H"})])
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
        compteurs, annuaire, reponses = passer([reponse({Q_PRENOM: "P"}, fiche=None)])

        assert compteurs == {"màj_reçues": 1, "màj_appliquées": 0, "orphelines": 0, "erreurs": 1}
        assert annuaire.ecritures == []
        assert reponses.marquees == []

    def test_une_ligne_fautive_n_arrete_pas_les_autres(self, _syslog):
        """Le défaut mesuré le 28/08 sur le cron des listes : une adresse
        refusée privait les 24 listes de synchronisation."""
        lignes = [
            {"id": "r1", "createdTime": "2026-08-28T09:00:00.000Z",
             "fields": {CHAMP_FICHE: "recA", Q_PRENOM: "A"}},
            {"id": "r2", "createdTime": "2026-08-28T09:00:00.000Z",
             "fields": {Q_PRENOM: "B"}},                      # sans record_id
            {"id": "r3", "createdTime": "2026-08-28T09:00:00.000Z",
             "fields": {CHAMP_FICHE: "recC", Q_PRENOM: "C"}},
        ]
        compteurs, annuaire, _ = passer(lignes)

        assert compteurs == {"màj_reçues": 3, "màj_appliquées": 2, "orphelines": 0, "erreurs": 1}
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

        assert compteurs == {"màj_reçues": 2, "màj_appliquées": 1, "orphelines": 0, "erreurs": 1}

    def test_ecriture_refusee_la_reponse_reste_a_retenter(self, _syslog):
        """Ne pas marquer une réponse qu'on n'a pas su appliquer : le passage
        suivant la rejouera, et l'erreur reste visible dans la ligne de vie."""
        compteurs, _, reponses = passer([reponse({Q_PRENOM: "P"})], refuse={"recFICHE"})

        assert compteurs["erreurs"] == 1
        assert reponses.marquees == []

    def test_marquage_refuse_la_fiche_reste_a_jour(self, _syslog):
        """La fiche est écrite, la réponse sera rejouée : réécrire les mêmes
        valeurs est sans effet, donc rien n'est perdu."""
        compteurs, annuaire, _ = passer([reponse({Q_PRENOM: "P"})], refuse_marquage=True)

        assert compteurs["màj_appliquées"] == 1
        assert annuaire.ecritures[0][1]["Prénom"] == "P"

    def test_lecture_impossible_ne_leve_pas(self, _syslog):
        annuaire, reponses = FauxAnnuaire(), FauxReponses([])
        reponses.list_records = Mock(side_effect=RuntimeError("Airtable HS"))

        compteurs = Reconciliation(annuaire, reponses).passer()

        assert compteurs == {"màj_reçues": 0, "màj_appliquées": 0, "orphelines": 0, "erreurs": 1}


@patch("src.reconciliation.syslog")
class TestSimulation:
    def test_le_dry_run_n_ecrit_rien(self, _syslog):
        compteurs, annuaire, reponses = passer([reponse({Q_PRENOM: "P"})], dry_run=True)

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


@patch("src.reconciliation.syslog")
class TestOrphelines:
    """Une réponse qui désigne une fiche supprimée.

    Elle ne s'appliquera jamais. La compter comme une erreur à chaque passage
    ferait un compteur d'erreurs perpétuellement non nul — donc un compteur que
    plus personne ne lit, et une sentinelle qui crie au loup toutes les heures.
    Constaté le 28/08/2026 en supprimant une fiche témoin dont le formulaire
    venait d'être rempli.
    """

    def test_elle_est_comptee_a_part(self, _syslog):
        compteurs, _, _ = passer([reponse({Q_PRENOM: "P"})],
                                 refuse={"recFICHE"}, disparues={"recFICHE"})

        assert compteurs["orphelines"] == 1
        assert compteurs["erreurs"] == 0

    def test_elle_n_est_pas_marquee_synchronisee(self, _syslog):
        """Le dire appliqué serait un mensonge : rien n'a été écrit."""
        _, _, reponses = passer([reponse({Q_PRENOM: "P"})],
                                refuse={"recFICHE"}, disparues={"recFICHE"})
        assert reponses.marquees == []

    def test_un_refus_passager_reste_une_erreur(self, _syslog):
        """La distinction porte sur l'existence de la fiche, pas sur l'échec."""
        compteurs, _, _ = passer([reponse({Q_PRENOM: "P"})], refuse={"recFICHE"})

        assert compteurs["erreurs"] == 1
        assert compteurs["orphelines"] == 0

    def test_un_airtable_injoignable_ne_condamne_pas_la_reponse(self, _syslog):
        """En cas de doute, la réponse reste à retenter : mieux vaut réessayer
        pour rien que perdre ce qu'un adhérent a saisi."""
        annuaire = FauxAnnuaire(refuse={"recFICHE"})
        annuaire.list_records = Mock(side_effect=RuntimeError("Airtable HS"))
        reponses = FauxReponses([reponse({Q_PRENOM: "P"})])

        compteurs = Reconciliation(annuaire, reponses).passer()

        assert compteurs["erreurs"] == 1
        assert compteurs["orphelines"] == 0
