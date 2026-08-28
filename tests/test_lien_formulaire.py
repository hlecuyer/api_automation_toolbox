"""Tests du lien prérempli vers le formulaire de mise à jour.

Ce que ces tests gardent : le `record_id` voyage toujours et reste masqué (sans
lui la réponse ne désigne aucune fiche), un champ vide n'occupe pas l'URL, et
une colonne liée non résolue n'expose pas un `recXXX` à l'adhérent.
"""

import urllib.parse

import pytest

from src import lien_formulaire
from src.lien_formulaire import CHAMP_FICHE, formule, url

BASE = "appBAC"
FORM = "shrFORM"


def parametres(lien):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(lien).query))


def fiche(**champs):
    return {"id": "recFICHE", "fields": champs}


class TestUrl:
    def test_la_fiche_voyage_et_reste_masquee(self):
        p = parametres(url(BASE, FORM, fiche()))
        assert p["prefill_" + CHAMP_FICHE] == "recFICHE"
        assert p["hide_" + CHAMP_FICHE] == "true"

    def test_le_lien_pointe_le_bon_formulaire(self):
        assert url(BASE, FORM, fiche()).startswith(
            "https://airtable.com/appBAC/shrFORM?")

    def test_une_adresse_complete_est_reprise_telle_quelle(self):
        """Le constructeur récent d'Airtable donne une adresse en `pagXXX`, pas
        un `shrXXX`. On colle ce que donne le bouton « Partager » plutôt que
        d'aller deviner un identifiant."""
        collee = "https://airtable.com/appAUTRE/pag45WWd/form"
        assert url(BASE, collee, fiche()).startswith(collee + "?")

    def test_une_adresse_collee_avec_ses_parametres_est_nettoyee(self):
        assert url(BASE, "https://airtable.com/appX/pagY/form?deja=1",
                   fiche()).count("?") == 1

    def test_une_valeur_est_preremplie_sous_sa_question(self):
        p = parametres(url(BASE, FORM, fiche(Prénom="Prosper")))
        assert p["prefill_Quel est votre prénom ?"] == "Prosper"

    @pytest.mark.parametrize("vide", [None, "", []])
    def test_un_champ_vide_n_occupe_pas_l_url(self, vide):
        """Le lien part par mail : chaque paramètre inutile rapproche de la
        limite au-delà de laquelle certains clients le coupent."""
        assert "prefill_Quel est votre prénom ?" not in parametres(
            url(BASE, FORM, fiche(Prénom=vide)))

    def test_une_liste_de_choix_est_recollee(self):
        p = parametres(url(BASE, FORM, fiche(**{"Type": ["Praticien·ne",
                                                         "Chercheur·se"]})))
        assert p["prefill_Vous êtes plutôt…"] == "Praticien·ne,Chercheur·se"

    def test_une_colonne_liee_non_resolue_est_ecartee(self):
        """Le formulaire attend le nom de la structure ; l'Annuaire porte son
        identifiant. Préremplir avec « rec4LRb… » ne dirait rien à l'adhérent."""
        lien = url(BASE, FORM, fiche(**{"Structure(s)": ["recSTRUCTURE1234"]}))
        assert "prefill_Dans quelle structure" not in urllib.parse.unquote(lien)

    def test_une_colonne_liee_resolue_est_preremplie(self):
        p = parametres(url(BASE, FORM, fiche(**{"Structure(s)": ["recX"]}),
                           liens={"Structure(s)": ["La Coop des Communs"]}))
        assert p["prefill_Dans quelle structure travaillez-vous ?"] == \
            "La Coop des Communs"


class TestFormule:
    def test_elle_porte_le_record_id_et_le_masque(self):
        f = formule(BASE, FORM)
        assert "RECORD_ID()" in f
        assert "hide_%s=true" % CHAMP_FICHE in f

    def test_chaque_question_a_sa_ligne(self):
        f = formule(BASE, FORM)
        assert f.count("ENCODE_URL_COMPONENT") == len(
            lien_formulaire.CHAMPS_FORMULAIRE)

    def test_un_champ_vide_n_ajoute_pas_son_parametre(self):
        assert formule(BASE, FORM).count("IF({") == len(
            lien_formulaire.CHAMPS_FORMULAIRE)

    def test_les_questions_sont_encodees(self):
        """Un « ? » ou un espace non encodé couperait la chaîne de paramètres."""
        f = formule(BASE, FORM)
        assert "prefill_Quel%20est%20votre%20pr%C3%A9nom%20%3F" in f
        assert "prefill_Quel est votre prénom ?" not in f

    def test_la_date_est_ramenee_au_jour(self):
        assert "DATETIME_FORMAT({date de naissance}, 'YYYY-MM-DD')" in \
            formule(BASE, FORM)

    def test_elle_vise_les_colonnes_de_l_annuaire(self):
        """La formule vit dans l'Annuaire : elle lit des colonnes, pas des
        questions."""
        f = formule(BASE, FORM)
        assert "{Partage de donnée autorisé}" in f
        assert "{Souhaitez-vous partager" not in f
