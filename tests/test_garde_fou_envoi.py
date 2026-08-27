"""Tests du garde-fou d'envoi.

Ce qui est vérifié ici n'est pas « la fonction retourne le bon booléen », c'est
la propriété qui rend le bac à sable utilisable : **hors production, aucune
adresse non listée ne peut recevoir de mail, quel que soit le chemin pris.**
"""

import pytest

from src import garde_fou_envoi
from src.clients.ovh_email_client import OVHEmailClient


@pytest.fixture
def hors_production(monkeypatch):
    """Environnement de bac à sable, liste blanche vide au départ."""
    monkeypatch.setenv(garde_fou_envoi.VARIABLE_ENVIRONNEMENT, "bac-a-sable")
    monkeypatch.delenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, raising=False)
    return monkeypatch


class TestDefautDeRefus:
    """Le défaut est le refus : c'est le sens de sécurité qui compte."""

    def test_sans_aucune_variable_rien_ne_part(self, monkeypatch):
        monkeypatch.delenv(garde_fou_envoi.VARIABLE_ENVIRONNEMENT, raising=False)
        monkeypatch.delenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, raising=False)

        autorise, refus = garde_fou_envoi.verifier(["adherent@coopdescommuns.org"])

        assert autorise is False
        assert garde_fou_envoi.VARIABLE_LISTE_BLANCHE in refus

    def test_liste_blanche_vide_hors_production(self, hors_production):
        autorise, _ = garde_fou_envoi.verifier(["qui-que-ce-soit@x.fr"])
        assert autorise is False

    def test_un_environnement_qui_ressemble_a_la_production_ne_suffit_pas(
        self, hors_production
    ):
        """« prod », « production-bis » : seul le mot exact ouvre la vanne."""
        for valeur in ("prod", "production-bis", "PRODUCTIONS", "preproduction"):
            hors_production.setenv(garde_fou_envoi.VARIABLE_ENVIRONNEMENT, valeur)
            assert garde_fou_envoi.en_production() is False


class TestProduction:
    def test_production_laisse_tout_passer(self, monkeypatch):
        monkeypatch.setenv(garde_fou_envoi.VARIABLE_ENVIRONNEMENT, "production")
        monkeypatch.delenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, raising=False)

        autorise, refus = garde_fou_envoi.verifier(["adherent@coopdescommuns.org"])

        assert autorise is True
        assert refus == ""

    def test_la_casse_et_les_espaces_ne_bloquent_pas_la_production(self, monkeypatch):
        monkeypatch.setenv(garde_fou_envoi.VARIABLE_ENVIRONNEMENT, "  Production ")
        assert garde_fou_envoi.en_production() is True


class TestListeBlanche:
    def test_adresse_exacte(self, hors_production):
        hors_production.setenv(
            garde_fou_envoi.VARIABLE_LISTE_BLANCHE, "hugo@dsi.coop"
        )
        assert garde_fou_envoi.verifier(["Hugo@DSI.coop"])[0] is True
        assert garde_fou_envoi.verifier(["autre@dsi.coop"])[0] is False

    def test_motif_de_domaine(self, hors_production):
        hors_production.setenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, "*@dsi.coop")
        assert garde_fou_envoi.verifier(["n-importe-qui@dsi.coop"])[0] is True
        assert garde_fou_envoi.verifier(["adherent@coopdescommuns.org"])[0] is False

    def test_un_domaine_qui_se_termine_pareil_ne_passe_pas(self, hors_production):
        """« pirate@faux-dsi.coop » ne doit pas passer pour « *@dsi.coop »."""
        hors_production.setenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, "*@dsi.coop")
        assert garde_fou_envoi.verifier(["pirate@faux-dsi.coop"])[0] is False

    def test_plusieurs_motifs_et_separateurs_tolerants(self, hors_production):
        hors_production.setenv(
            garde_fou_envoi.VARIABLE_LISTE_BLANCHE,
            " *@dsi.coop ; hugo@example.org ,, ",
        )
        assert garde_fou_envoi.verifier(["x@dsi.coop", "hugo@example.org"])[0] is True

    def test_un_seul_destinataire_hors_liste_refuse_tout_le_message(
        self, hors_production
    ):
        hors_production.setenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, "*@dsi.coop")
        autorise, _ = garde_fou_envoi.verifier(
            ["ok@dsi.coop", "adherent@coopdescommuns.org"]
        )
        assert autorise is False


class TestMotifsDangereux:
    """On ne doit pas pouvoir désarmer la ceinture depuis la liste blanche."""

    @pytest.mark.parametrize("motif", ["*", "*@*", "@*", "*@", "*@org", "*@fr", "a*@x.fr"])
    def test_motif_ignore(self, hors_production, motif):
        hors_production.setenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, motif)
        assert garde_fou_envoi.motifs_autorises() == []
        assert garde_fou_envoi.verifier(["adherent@coopdescommuns.org"])[0] is False

    def test_un_motif_dangereux_ne_annule_pas_les_autres(self, hors_production):
        hors_production.setenv(
            garde_fou_envoi.VARIABLE_LISTE_BLANCHE, "*,hugo@dsi.coop"
        )
        assert garde_fou_envoi.motifs_autorises() == ["hugo@dsi.coop"]
        assert garde_fou_envoi.verifier(["hugo@dsi.coop"])[0] is True


class TestAuNiveauDuClientMail:
    """La propriété doit tenir au point d'envoi, pas seulement dans la fonction."""

    @pytest.fixture
    def client(self):
        return OVHEmailClient(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="password",
        )

    def test_envoi_refuse_sans_ouvrir_de_connexion_smtp(
        self, client, hors_production, monkeypatch
    ):
        appels = []
        monkeypatch.setattr(
            "src.clients.ovh_email_client.smtplib.SMTP",
            lambda *a, **k: appels.append(a) or (_ for _ in ()).throw(
                AssertionError("SMTP ne doit pas être ouvert")
            ),
        )
        hors_production.setenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, "*@dsi.coop")

        resultat = client.send_email(
            sender="contact@dsi.coop",
            to=["adherent@coopdescommuns.org"],
            subject="Relance",
            body_text="…",
        )

        assert resultat is False
        assert appels == []

    def test_le_dry_run_ne_relache_pas_le_garde_fou(self, client, hors_production):
        """Une ceinture qui se desserre en simulation apprend que « ça marche »."""
        hors_production.setenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, "*@dsi.coop")

        resultat = client.send_email(
            sender="contact@dsi.coop",
            to=["adherent@coopdescommuns.org"],
            subject="Relance",
            body_text="…",
            dry_run=True,
        )

        assert resultat is False

    def test_le_bcc_est_controle_aussi(self, client, hors_production):
        hors_production.setenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, "*@dsi.coop")

        resultat = client.send_email(
            sender="contact@dsi.coop",
            to=["hugo@dsi.coop"],
            subject="Relance",
            body_text="…",
            bcc=["adherent@coopdescommuns.org"],
            dry_run=True,
        )

        assert resultat is False

    def test_destinataire_autorise_passe(self, client, hors_production):
        hors_production.setenv(garde_fou_envoi.VARIABLE_LISTE_BLANCHE, "*@dsi.coop")

        resultat = client.send_email(
            sender="contact@dsi.coop",
            to=["hugo@dsi.coop"],
            subject="Parcours de test",
            body_text="…",
            dry_run=True,
        )

        assert resultat is True
