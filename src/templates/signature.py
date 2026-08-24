"""Le bloc de signature des mails, tenu hors du code.

Une signature porte des données personnelles : nom, fonction, téléphone, adresse.
Les écrire en dur, c'est publier la vie privée d'un tiers dans un dépôt public, et
c'est irrattrapable une fois poussé. Les valeurs vivent donc dans l'environnement
(`.env`, gitignoré ; en production le `.env` généré par Ansible).

Les gabarits portent des sentinelles littérales, substituées au chargement du module,
avant tout `.format()`. Deux raisons de ne pas utiliser des placeholders `{sig_*}` :
`.format()` obligerait chaque appelant à fournir ces clés, et il trébucherait sur les
accolades d'un éventuel CSS. `str.replace` ne fait ni l'un ni l'autre.
"""

import os
import syslog
from pathlib import Path

from dotenv import load_dotenv

# Charger ici plutôt que de compter sur l'ordre des imports : un module qui importe
# `welcome_email` sans passer par `config_loader` enverrait sinon des mails signés
# « La Coop des Communs » sans que rien ne le signale à l'appelant.
#
# Le chemin est explicite, et non déduit par `find_dotenv()` : celui-ci remonte
# depuis le fichier appelant en inspectant la pile, ce qui échoue sous l'importeur
# de pytest. Même repère que LOGO_PATH dans `welcome_email`.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

CHAMPS = {
    "@@SIG_NAME@@": "SIGNATURE_NAME",
    "@@SIG_ROLE@@": "SIGNATURE_ROLE",
    "@@SIG_PHONE@@": "SIGNATURE_PHONE",
    "@@SIG_EMAIL@@": "SIGNATURE_EMAIL",
}

# Repli sans aucune donnée personnelle. Une adresse de contact d'association n'est
# pas la donnée d'une personne : elle peut rester ici.
REPLI = {
    "@@SIG_NAME@@": "La Coop des Communs",
    "@@SIG_ROLE@@": "",
    "@@SIG_PHONE@@": "",
    "@@SIG_EMAIL@@": "contact@coopdescommuns.org",
}

_avertissement_emis = False


def valeurs() -> dict:
    """Les valeurs de signature, ou le repli institutionnel si rien n'est configuré.

    Ne lève jamais : une synchronisation d'adhésion ne doit pas échouer parce qu'une
    signature manque. Un mail non signé se rattrape, une adhésion perdue non.
    """
    global _avertissement_emis
    if not os.getenv("SIGNATURE_NAME"):
        if not _avertissement_emis:
            syslog.syslog(
                syslog.LOG_WARNING,
                "SIGNATURE_NAME absent de l'environnement — les mails partiront avec la "
                "signature institutionnelle. Renseigner SIGNATURE_* dans .env "
                "(voir config/.env.example).",
            )
            _avertissement_emis = True
        return dict(REPLI)
    return {sentinelle: os.getenv(cle, "") for sentinelle, cle in CHAMPS.items()}


def appliquer(texte: str) -> str:
    """Substitue les sentinelles de signature dans une chaîne."""
    if not isinstance(texte, str):
        return texte
    for sentinelle, valeur in valeurs().items():
        texte = texte.replace(sentinelle, valeur)
    return texte


def appliquer_dict(obj):
    """Comme appliquer, en descendant dans les dicts et listes imbriqués.

    Permet de traiter un catalogue de gabarits d'un seul geste plutôt que de répéter
    l'appel sur chaque corps de mail — donc sans risque d'en oublier un.
    """
    if isinstance(obj, dict):
        return {cle: appliquer_dict(valeur) for cle, valeur in obj.items()}
    if isinstance(obj, list):
        return [appliquer_dict(element) for element in obj]
    return appliquer(obj)
