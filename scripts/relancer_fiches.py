#!/usr/bin/env python3
"""Relance les adhérents qui n'ont pas mis leur fiche à jour.

J+15, J+30, J+60 à compter du jour où l'adhérent a reçu son lien. Au-delà, plus
rien. La logique est dans `src/relance_fiche.py` ; ce script ne fait que la
brancher sur Airtable et sur le mail.

**Simulation par défaut.** Rien ne part sans `--envoyer`, et même alors le
garde-fou de `OVHEmailClient` reste en travers du chemin : hors production, il
refuse toute adresse qui n'est pas déclarée.

Usage :
    PYTHONPATH=. .venv/bin/python scripts/relancer_fiches.py               # simulation
    PYTHONPATH=. .venv/bin/python scripts/relancer_fiches.py --envoyer
    PYTHONPATH=. .venv/bin/python scripts/relancer_fiches.py --test moi@x.fr --envoyer
    PYTHONPATH=. .venv/bin/python scripts/relancer_fiches.py --base appXXXX

La cible par défaut est le bac à sable : on éprouve avant d'écrire à de vraies
personnes.
"""

import argparse
import json
import os
import sys
import syslog
import traceback
from datetime import date

from dotenv import load_dotenv

from src import heartbeat
from src.clients.airtable_client import AirtableClient
from src.clients.ovh_email_client import OVHEmailClient
from src.lien_formulaire import CHAMP_LIEN, CHAMP_LIEN_ENVOYE
from src.reconciliation import CHAMP_DATE_MAJ
from src.relance_fiche import (CHAMP_ADRESSE, CHAMP_DERNIERE_RELANCE, PALIERS,
                               Relance, a_relancer)
from src.templates import relance_email, welcome_email

CHEMIN_CONF = "config/hello-asso-automation-conf.json"

# Une erreur de sélection ne doit pas se traduire en mille mails. La limite est
# volontairement basse : le volume attendu est de quelques relances par jour sur
# une centaine d'adhésions par an, donc un passage qui la touche est un passage
# qui a un problème.
LIMITE_PAR_DEFAUT = 25

# La sentinelle du cron de relance. L'URL vit dans le `.env` de production,
# posée par Ansible depuis le vault ; sans elle, le ping est inerte.
HEARTBEAT_URL = "HEARTBEAT_URL_RELANCE"


def _conf(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def _logo_inline():
    """Le logo embarqué du bloc signature, même mécanisme que le mail de bienvenue.

    Sans lui, le `cid:logo` du gabarit montre une image cassée. Logo manquant :
    le mail part quand même, le syslog porte l'avertissement — même règle que
    `hello_asso_sync`, la signature ne doit pas faire échouer la relance.
    """
    try:
        with open(welcome_email.LOGO_PATH, "rb") as f:
            return [("logo", f.read(), "png")]
    except OSError as e:
        syslog.syslog(
            syslog.LOG_WARNING,
            "relance_fiche: logo absent ({}) — mails sans logo embarqué".format(e),
        )
        return None


def _envoyeur(client, expediteur, dry_run_envoi):
    logo_inline = _logo_inline()

    def envoyer(destinataire, prenom, lien, palier):
        texte, html = relance_email.render(lien, prenom)
        return client.send_email(
            sender=expediteur,
            to=[destinataire],
            subject=relance_email.SUBJECT,
            body_html=html,
            body_text=texte,
            inline_images=logo_inline,
            dry_run=dry_run_envoi,
        )
    return envoyer


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--envoyer", action="store_true",
                   help="envoyer réellement (défaut : simulation, rien n'est écrit)")
    p.add_argument("--limite", type=int, default=LIMITE_PAR_DEFAUT,
                   help="nombre maximum d'envois pour ce passage (défaut : %d)"
                        % LIMITE_PAR_DEFAUT)
    p.add_argument("--test", metavar="ADRESSE",
                   help="envoyer à cette adresse au lieu des adhérents. Les fiches ne "
                        "sont alors pas marquées relancées.")
    p.add_argument("--base", help="base cible (défaut : AIRTABLE_BASE_ID_BAC_A_SABLE)")
    p.add_argument("--expediteur", help="adresse d'expédition (défaut : celle de la conf)")
    p.add_argument("--config", default=CHEMIN_CONF, help="chemin de la configuration")
    args = p.parse_args()

    try:
        code = passage(args)
    except Exception as e:
        # stderr reste non redirigé : le MAILTO du cron attrape l'échec et la
        # sentinelle part sur /fail. Un crash ne doit pas ressembler à un
        # passage sain.
        syslog.syslog(syslog.LOG_ERR,
                      "relance_fiche: échec du passage ({})".format(e))
        print("ERROR: relance_fiche a échoué : {}".format(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        heartbeat.signaler(HEARTBEAT_URL, succes=False)
        return 1
    if args.envoyer and not args.test:
        # Le voyant dit « le passage a eu lieu », pas « tout est parfait » :
        # les erreurs unitaires restent dans le compteur et le code de retour.
        # Simulation et --test ne pingent pas : un passage de diagnostic ne
        # doit pas rendre la sentinelle verte à la place du cron.
        heartbeat.signaler(HEARTBEAT_URL, succes=True)
    return code


def passage(args):
    base = args.base or os.getenv("AIRTABLE_BASE_ID_BAC_A_SABLE")
    jeton = (os.getenv("AIRTABLE_API_KEY_BAC_A_SABLE") or os.getenv("AIRTABLE_API_KEY")
             or os.getenv("AIRTABLE_API_KEY_PROD"))
    if not base or not jeton:
        sys.exit("Base ou jeton Airtable absent : --base appXXXX, et AIRTABLE_API_KEY "
                 "dans le .env.")

    conf_globale = _conf(args.config)
    conf = conf_globale["conf"]
    credentials = conf_globale.get("credentials", {})
    email = conf.get("ovh", {}).get("email", {})
    # La configuration locale ne porte pas de bloc `email` : il est posé par
    # Ansible en production. Hors production on retombe donc sur le compte SMTP
    # du `.env`, ce qui est aussi ce que fait le parcours du bac à sable.
    expediteur = args.expediteur or email.get("from") or os.getenv("SMTP_USER")
    if not expediteur:
        sys.exit("Aucun expéditeur : --expediteur, conf.ovh.email.from, ou SMTP_USER.")

    production = os.getenv("AIRTABLE_BASE_ID_PROD")
    print("base cible : %s%s" % (base, "  ⚠ PRODUCTION" if base == production else ""))
    print("mode       : %s%s" % ("ENVOI RÉEL" if args.envoyer else "simulation",
                                 "  (redirigé vers %s)" % args.test if args.test else ""))
    print("expéditeur : %s" % expediteur)
    print()

    annuaire = AirtableClient(api_key=jeton, base_id=base, table_name="Annuaire")
    client_mail = OVHEmailClient(
        smtp_host=credentials.get("smtp", {}).get("host") or os.getenv("SMTP_HOST"),
        smtp_port=credentials.get("smtp", {}).get("port") or os.getenv("SMTP_PORT"),
        smtp_user=credentials.get("smtp", {}).get("user") or os.getenv("SMTP_USER"),
        smtp_password=credentials.get("smtp", {}).get("password")
                      or os.getenv("SMTP_PASSWORD"),
    )

    relance = Relance(annuaire, _envoyeur(client_mail, expediteur, not args.envoyer))

    # Ce que le passage va faire, dit avant de le faire. Une relance part vers
    # une vraie personne : le passage doit être lisible avant d'être lancé.
    fiches = relance.candidates()
    dues = [(f, a_relancer(f.get("fields", {}), relance.aujourdhui)) for f in fiches]
    dues = [(f, p) for f, p in dues if p is not None]
    print("%d fiche(s) candidate(s), %d relance(s) due(s) :" % (len(fiches), len(dues)))
    for f, palier in dues[:args.limite]:
        champs = f["fields"]
        print("   J+%-3d %-38s envoyé le %s, %s"
              % (palier, champs.get(CHAMP_ADRESSE, "?"),
                 str(champs.get(CHAMP_LIEN_ENVOYE))[:10],
                 "jamais relancé" if not champs.get(CHAMP_DERNIERE_RELANCE)
                 else "dernière relance %s" % str(champs[CHAMP_DERNIERE_RELANCE])[:10]))
    if len(dues) > args.limite:
        print("   … et %d autre(s), au-delà de la limite de %d"
              % (len(dues) - args.limite, args.limite))
    print()

    compteurs = relance.passer(dry_run=not args.envoyer, limite=args.limite,
                               test=args.test)
    print("relances_dues=%(relances_dues)s relances_envoyées=%(relances_envoyées)s "
          "erreurs=%(erreurs)s" % compteurs)
    syslog.syslog(
        syslog.LOG_INFO,
        "relance_fiche: relances_dues=%(relances_dues)s "
        "relances_envoyées=%(relances_envoyées)s erreurs=%(erreurs)s" % compteurs)

    if not args.envoyer:
        print()
        print("Simulation. Aucun mail envoyé, aucune fiche marquée. --envoyer pour de vrai.")
    return 1 if compteurs["erreurs"] else 0


if __name__ == "__main__":
    sys.exit(main())
