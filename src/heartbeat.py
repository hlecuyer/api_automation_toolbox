"""Dead man's switch : signaler qu'un passage a bien eu lieu.

Une ligne de log « ça a tourné » ne détecte rien toute seule, personne ne va la
lire. Ce qui détecte, c'est un service externe qui s'alarme quand le ping de fin
de passage n'arrive pas dans la fenêtre attendue. C'est le seul mécanisme qui
voit aussi la machine éteinte, le cron supprimé et le réseau coupé, trois cas
qu'aucun contrôle tournant sur la même machine ne peut voir.

Deux règles, et elles priment sur la fonctionnalité :

- Sans URL configurée, la fonction est inerte et ne fait aucun appel réseau.
  Les tests et le poste de dev restent silencieux sans configuration spéciale.
- Un ping qui échoue ne fait jamais tomber le travail qu'il surveille. Le
  monitoring est subordonné à la synchro, jamais l'inverse.

L'URL porte un identifiant qui vaut jeton : elle vit dans le `.env`, pas dans
l'inventaire en clair.
"""

import os
import syslog

import requests

DELAI = 5


def signaler(cle_env: str, *, succes: bool = True) -> None:
    """Ping le service de supervision à la fin d'un passage.

    Args:
        cle_env: nom de la variable d'environnement portant l'URL de ping.
        succes: False si le passage n'est pas allé au bout. Le ping part alors
            sur `<url>/fail`, pour qu'un passage en échec ne ressemble pas à un
            passage sain.
    """
    url = os.getenv(cle_env)
    if not url:
        return

    if not succes:
        url = url + "/fail"

    try:
        reponse = requests.get(url, timeout=DELAI)
        reponse.raise_for_status()
    except Exception as e:
        # Le service de supervision peut être en panne. Ça ne regarde pas
        # l'automatisation qui vient de tourner.
        syslog.syslog(
            syslog.LOG_WARNING,
            "heartbeat: ping {} en échec ({})".format(cle_env, e),
        )
