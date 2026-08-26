"""Tests de non-régression sur la signature du mail de bienvenue.

La signature (nom, fonction, téléphone, adresse de la présidente) est sortie du
code le 24/08/2026 et vit désormais dans l'environnement. Le rendu du mail est
donc devenu dépendant de la configuration : c'est du code qui part chez des
adhérents et que rien ne couvrait.

Ce que ces tests garantissent :
  - toutes les sentinelles sont substituées, aucune ne fuit dans un mail envoyé ;
  - le repli fonctionne sans configuration, sans lever et sans donnée personnelle ;
  - la substitution a lieu AVANT le `.format()`, donc une valeur de signature
    contenant des accolades ne fait pas échouer le rendu.

Aucune valeur réelle ici : le dépôt est public, les tests utilisent des valeurs
fictives.
"""

import pytest

from src.templates import signature, welcome_email

SENTINELLES = ("@@SIG_NAME@@", "@@SIG_ROLE@@", "@@SIG_PHONE@@", "@@SIG_EMAIL@@")

FICTIF = {
    "SIGNATURE_NAME": "Prénom NOM",
    "SIGNATURE_ROLE": "Fonction",
    "SIGNATURE_PHONE": "+33 (0)6 00 00 00 00",
    "SIGNATURE_EMAIL": "prenom.nom@example.org",
}


@pytest.fixture
def signature_configuree(monkeypatch):
    """L'environnement tel que le `.env` généré par Ansible le fournit en prod."""
    for cle, valeur in FICTIF.items():
        monkeypatch.setenv(cle, valeur)
    return FICTIF


@pytest.fixture
def signature_absente(monkeypatch):
    """Aucune clé SIGNATURE_* : le cas d'un déploiement incomplet."""
    for cle in FICTIF:
        monkeypatch.delenv(cle, raising=False)
    # L'avertissement syslog n'est émis qu'une fois par processus ; le remettre
    # à zéro pour que le test qui l'observe ne dépende pas de l'ordre d'exécution.
    monkeypatch.setattr(signature, "_avertissement_emis", False)


# --- appliquer -------------------------------------------------------------


def test_appliquer_substitue_les_quatre_sentinelles(signature_configuree):
    rendu = signature.appliquer("\n".join(SENTINELLES))
    assert rendu.splitlines() == [
        FICTIF["SIGNATURE_NAME"],
        FICTIF["SIGNATURE_ROLE"],
        FICTIF["SIGNATURE_PHONE"],
        FICTIF["SIGNATURE_EMAIL"],
    ]


def test_appliquer_replie_sans_configuration(signature_absente):
    rendu = signature.appliquer("@@SIG_NAME@@|@@SIG_PHONE@@")
    assert rendu == "La Coop des Communs|"


def test_repli_ne_contient_aucune_donnee_personnelle(signature_absente):
    valeurs = signature.valeurs()
    assert valeurs["@@SIG_PHONE@@"] == ""
    assert valeurs["@@SIG_NAME@@"] == "La Coop des Communs"
    assert "@" in valeurs["@@SIG_EMAIL@@"]


def test_appliquer_laisse_passer_ce_qui_n_est_pas_une_chaine(signature_configuree):
    assert signature.appliquer(None) is None
    assert signature.appliquer(42) == 42


def test_appliquer_dict_descend_dans_les_structures(signature_configuree):
    catalogue = {"mail": {"texte": ["Bonjour", "@@SIG_NAME@@"], "objet": "@@SIG_ROLE@@"}}
    rendu = signature.appliquer_dict(catalogue)
    assert rendu["mail"]["texte"][1] == FICTIF["SIGNATURE_NAME"]
    assert rendu["mail"]["objet"] == FICTIF["SIGNATURE_ROLE"]


# --- rendu du mail de bienvenue -------------------------------------------


@pytest.mark.parametrize("prenom", ["Camille", "", None, "Zoé"])
def test_aucune_sentinelle_ne_survit_au_rendu(signature_configuree, prenom):
    """Le test qui compte : une sentinelle non substituée partirait chez un adhérent."""
    texte, html = welcome_email.render(prenom)
    for sentinelle in SENTINELLES:
        assert sentinelle not in texte
        assert sentinelle not in html


@pytest.mark.parametrize("prenom", ["Camille", "", None])
def test_aucune_sentinelle_ne_survit_meme_sans_configuration(signature_absente, prenom):
    texte, html = welcome_email.render(prenom)
    for sentinelle in SENTINELLES:
        assert sentinelle not in texte
        assert sentinelle not in html


def test_la_signature_est_bien_presente_dans_les_deux_corps(signature_configuree):
    texte, html = welcome_email.render("Camille")
    for valeur in FICTIF.values():
        assert valeur in texte
        assert valeur in html


def test_le_prenom_est_substitue(signature_configuree):
    texte, html = welcome_email.render("Camille")
    assert "Camille" in texte
    assert "Camille" in html
    assert "{first_name}" not in texte
    assert "{first_name}" not in html


@pytest.mark.parametrize("prenom", ["", "   ", None])
def test_prenom_vide_repli_sur_a_toi(signature_configuree, prenom):
    texte, _ = welcome_email.render(prenom)
    assert "à toi" in texte


def test_une_signature_avec_accolades_ne_casse_pas_le_rendu(monkeypatch):
    """La substitution doit précéder le `.format()`.

    Dans l'ordre inverse, une accolade dans une valeur de signature ferait lever
    `KeyError` au `.format()` et l'adhésion échouerait au moment de l'envoi.
    """
    monkeypatch.setenv("SIGNATURE_NAME", "Prénom {NOM}")
    monkeypatch.setenv("SIGNATURE_ROLE", "Fonction")
    monkeypatch.setenv("SIGNATURE_PHONE", "+33 (0)6 00 00 00 00")
    monkeypatch.setenv("SIGNATURE_EMAIL", "prenom.nom@example.org")

    texte, html = welcome_email.render("Camille")
    assert "Prénom {NOM}" in texte
    assert "Prénom {NOM}" in html


def test_un_prenom_avec_accolades_ne_casse_pas_le_rendu(signature_configuree):
    texte, _ = welcome_email.render("Zoé {Martin}")
    assert "Zoé {Martin}" in texte


def test_l_objet_ne_depend_pas_de_la_signature(signature_absente):
    assert welcome_email.SUBJECT == "Bienvenue à La Coop des Communs !"
