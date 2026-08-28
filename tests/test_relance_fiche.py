"""Tests de la relance des fiches non mises à jour.

Ce module écrit à de vraies personnes. Ce qui est vérifié ici est donc d'abord
**ce qu'il ne doit pas faire** : écrire à quelqu'un qui s'est désinscrit, écrire
à quelqu'un qui a déjà répondu, envoyer un lien vide, ou renvoyer trois fois la
même relance parce qu'un cron a tourné trois fois.
"""

from datetime import date, timedelta
from unittest.mock import Mock, patch

import pytest

from src.lien_formulaire import CHAMP_LIEN, CHAMP_LIEN_ENVOYE
from src.reconciliation import CHAMP_DATE_MAJ
from src.relance_fiche import (CHAMP_ADRESSE, CHAMP_DERNIERE_RELANCE,
                               CHAMP_DESINSCRIT, PALIERS, Relance, a_relancer,
                               palier_du)

AUJOURDHUI = date(2026, 9, 1)
LIEN = "https://airtable.com/appX/shrY?prefill_record_id=recZ"


def champs(jours_depuis_envoi=20, **extra):
    base = {
        CHAMP_ADRESSE: "adherent@example.org",
        CHAMP_LIEN: LIEN,
        CHAMP_LIEN_ENVOYE: (AUJOURDHUI - timedelta(days=jours_depuis_envoi)).isoformat(),
    }
    base.update(extra)
    return base


def fiche(ident="recF", **kw):
    return {"id": ident, "fields": champs(**kw)}


class FauxAnnuaire:
    def __init__(self, lignes=(), refuse=False):
        self.lignes = list(lignes)
        self.refuse = refuse
        self.majs = []
        self.formule = None

    def list_records(self, filter_by_formula=None, **_):
        self.formule = filter_by_formula
        return self.lignes

    def update_record(self, record_id, fields, dry_run=False):
        if self.refuse:
            return None
        self.majs.append((record_id, fields))
        return {"id": record_id}


def passer(lignes, envoi=True, **kw):
    annuaire = FauxAnnuaire(lignes)
    envoyes = []

    def envoyer(destinataire, prenom, lien, palier):
        envoyes.append((destinataire, prenom, lien, palier))
        return envoi

    compteurs = Relance(annuaire, envoyer, aujourdhui=AUJOURDHUI).passer(**kw)
    return compteurs, annuaire, envoyes


# --------------------------------------------------------------------------
# Quel palier, et quand
# --------------------------------------------------------------------------

class TestPalier:
    @pytest.mark.parametrize("jours,attendu",
                             [(0, None), (14, None), (15, 15), (29, 15),
                              (30, 30), (59, 30), (60, 60), (400, 60)])
    def test_le_palier_est_le_plus_grand_atteint(self, jours, attendu):
        """Le plus grand et non le plus proche : un cron resté muet trois
        semaines doit rattraper la relance manquée, pas la sauter."""
        assert palier_du(AUJOURDHUI - timedelta(days=jours), AUJOURDHUI) == attendu

    def test_sans_date_d_envoi_aucun_palier(self):
        assert palier_du(None, AUJOURDHUI) is None

    def test_les_paliers_sont_ceux_annonces(self):
        assert PALIERS == (15, 30, 60)


class TestSelection:
    def test_le_cas_nominal(self):
        assert a_relancer(champs(jours_depuis_envoi=20), AUJOURDHUI) == 15

    def test_un_desinscrit_n_est_jamais_relance(self):
        """Sans exception : c'est la seule règle du module qui n'a pas de « sauf
        si »."""
        assert a_relancer(champs(**{CHAMP_DESINSCRIT: True}), AUJOURDHUI) is None

    def test_une_fiche_deja_mise_a_jour_n_est_pas_relancee(self):
        assert a_relancer(champs(**{CHAMP_DATE_MAJ: "2026-08-28"}),
                          AUJOURDHUI) is None

    def test_sans_lien_pas_de_relance(self):
        """Un rappel qui ne mène nulle part est pire que pas de rappel."""
        assert a_relancer(champs(**{CHAMP_LIEN: ""}), AUJOURDHUI) is None

    def test_sans_adresse_pas_de_relance(self):
        assert a_relancer(champs(**{CHAMP_ADRESSE: None}), AUJOURDHUI) is None

    def test_sans_date_d_envoi_pas_de_relance(self):
        """On ne relance pas quelqu'un sur un message qu'il n'a pas reçu."""
        assert a_relancer(champs(**{CHAMP_LIEN_ENVOYE: None}), AUJOURDHUI) is None

    def test_avant_le_premier_palier_rien_ne_part(self):
        assert a_relancer(champs(jours_depuis_envoi=14), AUJOURDHUI) is None

    def test_le_meme_palier_ne_part_pas_deux_fois(self):
        """Deux passages le même jour, ou dix : la question se pose en dates."""
        c = champs(jours_depuis_envoi=20,
                   **{CHAMP_DERNIERE_RELANCE: (AUJOURDHUI - timedelta(days=4)).isoformat()})
        assert a_relancer(c, AUJOURDHUI) is None

    def test_le_palier_suivant_part_malgre_le_precedent(self):
        c = champs(jours_depuis_envoi=31,
                   **{CHAMP_DERNIERE_RELANCE: (AUJOURDHUI - timedelta(days=16)).isoformat()})
        assert a_relancer(c, AUJOURDHUI) == 30

    def test_apres_le_dernier_palier_plus_rien(self):
        """Quelqu'un qui n'a pas répondu trois fois a répondu."""
        c = champs(jours_depuis_envoi=200,
                   **{CHAMP_DERNIERE_RELANCE: (AUJOURDHUI - timedelta(days=139)).isoformat()})
        assert a_relancer(c, AUJOURDHUI) is None

    def test_une_date_illisible_ne_leve_pas(self):
        assert a_relancer(champs(**{CHAMP_LIEN_ENVOYE: "pas une date"}),
                          AUJOURDHUI) is None


# --------------------------------------------------------------------------
# Le passage
# --------------------------------------------------------------------------

@patch("src.relance_fiche.syslog")
class TestPassage:
    def test_la_formule_ecarte_deja_les_desinscrits(self, _s):
        _, annuaire, _ = passer([])
        assert CHAMP_DESINSCRIT in annuaire.formule
        assert CHAMP_LIEN_ENVOYE in annuaire.formule

    def test_envoi_et_marquage(self, _s):
        compteurs, annuaire, envoyes = passer([fiche()], dry_run=False)

        assert compteurs == {"relances_dues": 1, "relances_envoyées": 1, "erreurs": 0}
        assert envoyes == [("adherent@example.org", None, LIEN, 15)]
        assert annuaire.majs == [("recF", {CHAMP_DERNIERE_RELANCE: "2026-09-01"})]

    def test_la_simulation_n_envoie_ni_n_ecrit(self, _s):
        compteurs, annuaire, envoyes = passer([fiche()], dry_run=True)

        assert compteurs["relances_envoyées"] == 1
        assert envoyes == [] and annuaire.majs == []

    def test_la_simulation_est_le_defaut(self, _s):
        annuaire = FauxAnnuaire([fiche()])
        envoi = Mock(return_value=True)

        Relance(annuaire, envoi, aujourdhui=AUJOURDHUI).passer()

        assert not envoi.called

    def test_la_limite_borne_les_envois_pas_le_comptage(self, _s):
        """Le nombre de relances dues doit rester visible même quand on n'en
        envoie qu'une partie : c'est lui qui dit si la sélection déraille."""
        lignes = [fiche("rec%d" % i) for i in range(5)]
        compteurs, _, envoyes = passer(lignes, dry_run=False, limite=2)

        assert compteurs["relances_dues"] == 5
        assert compteurs["relances_envoyées"] == 2
        assert len(envoyes) == 2

    def test_le_mode_test_redirige_et_ne_marque_pas(self, _s):
        """Un essai ne doit pas consommer la relance de quelqu'un d'autre."""
        compteurs, annuaire, envoyes = passer([fiche()], dry_run=False,
                                              test="moi@dsi.coop")

        assert envoyes[0][0] == "moi@dsi.coop"
        assert annuaire.majs == []
        assert compteurs["relances_envoyées"] == 1

    def test_un_envoi_refuse_laisse_la_fiche_a_relancer(self, _s):
        compteurs, annuaire, _ = passer([fiche()], envoi=False, dry_run=False)

        assert compteurs["erreurs"] == 1
        assert annuaire.majs == []

    def test_un_marquage_refuse_est_signale(self, syslog):
        """Le mail est parti : la relance repartira au passage suivant. Un
        doublon vaut mieux qu'un silence, mais ça doit se voir."""
        annuaire = FauxAnnuaire([fiche()], refuse=True)
        compteurs = Relance(annuaire, lambda *a: True,
                            aujourdhui=AUJOURDHUI).passer(dry_run=False)

        assert compteurs["relances_envoyées"] == 1
        assert syslog.syslog.called

    def test_une_fiche_fautive_n_arrete_pas_les_autres(self, _s):
        annuaire = FauxAnnuaire([fiche("recA"), fiche("recB"), fiche("recC")])
        envoi = Mock(side_effect=[True, RuntimeError("boum"), True])

        compteurs = Relance(annuaire, envoi, aujourdhui=AUJOURDHUI).passer(dry_run=False)

        assert compteurs == {"relances_dues": 3, "relances_envoyées": 2, "erreurs": 1}

    def test_lecture_impossible_ne_leve_pas(self, _s):
        annuaire = FauxAnnuaire()
        annuaire.list_records = Mock(side_effect=RuntimeError("Airtable HS"))

        compteurs = Relance(annuaire, lambda *a: True).passer()

        assert compteurs == {"relances_dues": 0, "relances_envoyées": 0, "erreurs": 1}


class TestGabarit:
    def test_le_lien_est_dans_les_deux_versions(self):
        from src.templates import relance_email
        texte, html = relance_email.render(LIEN, "Prosper")
        assert LIEN in texte and 'href="%s"' % LIEN in html
        assert "Prosper" in texte and "Prosper" in html

    def test_sans_prenom_le_mail_reste_lisible(self):
        from src.templates import relance_email
        texte, _ = relance_email.render(LIEN)
        assert "Bonjour à vous" in texte

    def test_la_signature_est_substituee(self):
        from src.templates import relance_email
        texte, html = relance_email.render(LIEN, "Prosper")
        assert "@@SIG_" not in texte and "@@SIG_" not in html
