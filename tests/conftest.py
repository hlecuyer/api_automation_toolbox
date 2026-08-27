"""Réglages communs à toute la suite de tests.

Un seul objet pour l'instant : **la suite de tests ne doit jamais pouvoir
envoyer un mail à une vraie personne.** Le garde-fou d'envoi
(`src/garde_fou_envoi.py`) le garantit déjà, mais `config_loader` appelle
`load_dotenv()` à l'import : sans ce fixture, un `.env` local portant
`ENVIRONNEMENT=production` ferait tourner toute la suite en production.

On force donc l'environnement à « tests » et on n'ouvre la liste blanche
qu'aux domaines de fiction utilisés par les tests, plus `dsi.coop` qui est la
boîte d'Hugo — seule destination des tests marqués `manual`, les seuls à
envoyer réellement.

Conséquence voulue : le garde-fou est *exercé* par toute la suite au lieu
d'être neutralisé. Un test qui écrirait à une adresse d'adhérent échouerait.
"""

import pytest

from src import garde_fou_envoi

DOMAINES_DE_TEST = [
    "*@example.com",
    "*@example.org",
    "*@test.com",
    "*@test.org",
    "*@x.fr",
    "*@y.fr",
    "*@dsi.coop",
]


@pytest.fixture(autouse=True)
def bac_a_sable(monkeypatch):
    monkeypatch.setenv(garde_fou_envoi.VARIABLE_ENVIRONNEMENT, "tests")
    monkeypatch.setenv(
        garde_fou_envoi.VARIABLE_LISTE_BLANCHE, ",".join(DOMAINES_DE_TEST)
    )
