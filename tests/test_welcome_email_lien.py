"""Le lien de mise à jour dans le mail de bienvenue.

C'est la seule porte du parcours de mise à jour : l'adhérent ne le trouvera
nulle part ailleurs. Mais un lien manquant ne doit jamais faire échouer une
adhésion — le mail part sans le bloc, et le syslog le dit. Même règle que la
signature, pour la même raison : le mail de bienvenue est la dernière étape de
l'adhésion, tout ce qui plante là fait perdre l'adhésion entière.
"""

from unittest.mock import Mock, patch

from src.lien_formulaire import CHAMP_LIEN
from src.templates import welcome_email

LIEN = "https://airtable.com/appX/shrY?prefill_record_id=recZ&hide_record_id=true"


class TestRendu:
    def test_le_lien_est_dans_les_deux_versions(self):
        texte, html = welcome_email.render("Prosper", LIEN)
        assert LIEN in texte
        assert 'href="%s"' % LIEN in html

    def test_le_bouton_porte_un_intitule_lisible(self):
        _, html = welcome_email.render("Prosper", LIEN)
        assert "Vérifier mes informations" in html

    def test_sans_lien_le_bloc_disparait(self):
        """Pas de bouton mort, pas de phrase qui annonce un lien absent."""
        texte, html = welcome_email.render("Prosper")
        assert "VÉRIFIE TES INFORMATIONS" not in texte
        assert "Vérifier mes informations" not in html

    def test_sans_lien_le_reste_du_mail_est_intact(self):
        texte, html = welcome_email.render("Prosper")
        assert "Bonjour Prosper" in texte
        assert "Bienvenue, Prosper !" in html
        assert "{bloc_maj}" not in texte and "{bloc_maj}" not in html

    def test_la_signature_est_toujours_substituee(self):
        """Le bloc s'insère avant la substitution : une accolade dans le lien ne
        doit pas plus casser le rendu qu'une accolade dans la signature."""
        texte, html = welcome_email.render("Prosper", LIEN)
        assert "@@SIG_NAME@@" not in texte
        assert "@@SIG_NAME@@" not in html


class TestLecture:
    """Ce que `hello_asso_sync` lit dans la fiche qu'il vient d'écrire."""

    def sync(self):
        from src.hello_asso_sync import SyncHelloAsso
        return SyncHelloAsso.__new__(SyncHelloAsso)

    def test_le_lien_vient_du_champ_formule(self):
        assert self.sync()._lien_de_mise_a_jour(
            {"id": "recX", "fields": {CHAMP_LIEN: LIEN}}) == LIEN

    @patch("src.hello_asso_sync.syslog")
    def test_un_champ_vide_est_signale_sans_lever(self, syslog):
        """Un mail de bienvenue sans lien, c'est un adhérent qui ne mettra
        jamais sa fiche à jour : ça doit se voir dans la ligne de vie."""
        assert self.sync()._lien_de_mise_a_jour({"id": "recX", "fields": {}}) is None
        assert syslog.syslog.called

    @patch("src.hello_asso_sync.syslog")
    def test_un_resultat_de_dry_run_ne_leve_pas(self, _syslog):
        """En simulation, `upsert_record` n'est pas appelé et le résultat vaut
        `True`. Lire `.get` dessus ferait échouer la simulation, pas la
        production — donc silencieusement, jusqu'au jour du déploiement."""
        assert self.sync()._lien_de_mise_a_jour(True) is None
        assert self.sync()._lien_de_mise_a_jour(None) is None
