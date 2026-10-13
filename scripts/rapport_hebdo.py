#!/usr/bin/env python3
"""Rapport périodique : ce que le système a fait, lu depuis les données.

Une seule visée : savoir, après déploiement, si tout fonctionne, sans ouvrir
ni Airtable ni les logs. Un mail court, une section par composant, deux
familles de faits :

- **les volumétries**, comptées dans la base (adhésions, liens envoyés, fiches
  mises à jour, relances) : tout champ daté existe déjà, rien n'est à inventer ;
- **la santé des passages**, lue dans le syslog quand il est lisible : un
  rapport qui dirait « 0 événement » trois semaines de suite parce que plus
  rien ne tourne serait le pire des rapports. Les dates des derniers passages
  distinguent « rien ne s'est passé » de « ça ne tourne plus ».

Les anomalies sont dites dans le corps du rapport, pas cachées dans un
compteur : adhésion sans mail de bienvenue (le mail perdu, forme exacte du
silence fondateur de ce projet), réponse au formulaire sans fiche derrière,
erreurs cumulées sur la fenêtre.

**Simulation par défaut.** Sans `--envoyer`, le rapport est rendu sur stdout
et rien ne part. La sentinelle n'est pingée que sur un envoi réel, comme la
relance : un passage de diagnostic ne doit pas rendre la sentinelle verte.

Usage :
    PYTHONPATH=. .venv/bin/python scripts/rapport_hebdo.py               # rendu seul
    PYTHONPATH=. .venv/bin/python scripts/rapport_hebdo.py --envoyer
    PYTHONPATH=. .venv/bin/python scripts/rapport_hebdo.py --jours 30
    PYTHONPATH=. .venv/bin/python scripts/rapport_hebdo.py --base appXXXX

La cible par défaut est le bac à sable, comme partout : on éprouve avant
d'écrire à de vraies personnes.
"""

import argparse
import gzip
import json
import os
import re
import sys
import syslog
from collections import Counter
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from src import heartbeat
from src.clients.airtable_client import AirtableClient
from src.clients.ovh_email_client import OVHEmailClient
from src.reconciliation import CHAMP_FICHE, CHAMP_SYNCHRONISE

CHEMIN_CONF = "config/hello-asso-automation-conf.json"

HEARTBEAT_URL = "HEARTBEAT_URL_RAPPORT"

TABLE_REPONSES = "Mise à jour fiche"
TABLE_GROUPES = "Liste des groupes"

CHAMP_DATE_CREATION = "Date de création"
CHAMP_NOUVEAU = "Nouvel adhérent"
CHAMP_LIEN_ENVOYE = "Lien envoyé le"
CHAMP_DATE_MAJ = "Fiche mise à jour le"
CHAMP_DERNIERE_RELANCE = "Dernière relance le"
CHAMP_DESINSCRIT = "désinscrit liste membres"
CHAMP_GROUPES = "Groupe(s)"

# Les passages qui se signalent en syslog. Le mailinglist n'y écrit que ses
# échecs : son absence de ligne signifie « aucune erreur », le dire tel quel.
LIGNES_DE_VIE = {
    "hello_asso_sync": ("hello_asso_sync: passage terminé", "erreurs=(\\d+)"),
    "relance_fiche": ("relance_fiche: relances_dues=", "erreurs=(\\d+)"),
    "mailinglist": ("mailinglist", None),
}

LIMITE_RELANCES = 25  # même limite que relancer_fiches : la toucher est un signal


def _conf(chemin):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def _jour(valeur):
    """Une date Airtable (`2026-10-13` ou ISO complet) ramenée à `date`."""
    if not valeur:
        return None
    try:
        return datetime.strptime(str(valeur)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _dans_fenetre(valeur, debut, fin):
    jour = _jour(valeur)
    return jour is not None and debut <= jour <= fin


def _id_groupe(groups_client, nom):
    """L'identifiant du groupe par son nom, ou None."""
    fiches = groups_client.list_records(
        filter_by_formula="{Nom} = '%s'" % nom.replace("'", "\\'"))
    return fiches[0]["id"] if fiches else None


def compter_volumetries(annuaire, reponses, id_groupe, debut, fin, aujourdhui):
    """Les comptes de la fenêtre, depuis un seul passage dans chaque table.

    Tout est compté en Python après un fetch unique : les formules Airtable qui
    sauraient le faire seraient illisibles, donc fausses un jour sans que
    personne ne s'en aperçoive (même parti pris que la sélection des relances).
    """
    fiches = annuaire.list_records()
    ids_annuaire = {f["id"] for f in fiches}

    creation = [f for f in fiches
                if _dans_fenetre(f["fields"].get(CHAMP_DATE_CREATION), debut, fin)]
    liens = [f for f in fiches
             if _dans_fenetre(f["fields"].get(CHAMP_LIEN_ENVOYE), debut, fin)]
    maj = [f for f in fiches
           if _dans_fenetre(f["fields"].get(CHAMP_DATE_MAJ), debut, fin)]
    relances = [f for f in fiches
                if _dans_fenetre(f["fields"].get(CHAMP_DERNIERE_RELANCE), debut, fin)]
    desinscrites = [f for f in fiches if f["fields"].get(CHAMP_DESINSCRIT)]
    dans_groupe = [f for f in fiches
                   if id_groupe and id_groupe in (f["fields"].get(CHAMP_GROUPES) or [])]
    a_relancer = [f for f in fiches if a_relancer_fiche(f["fields"], aujourdhui)]

    # La répartition nouveaux/réadhésions suit le champ calculé par la synchro
    # (« Oui » à la création d'un nouveau, « Non » sur une réadhésion).
    repartition = Counter(f["fields"].get(CHAMP_NOUVEAU) or "non renseigné"
                          for f in creation)

    toutes_reponses = reponses.list_records()
    orphelines = [r for r in toutes_reponses
                  if r["fields"].get(CHAMP_FICHE)
                  and r["fields"][CHAMP_FICHE] not in ids_annuaire]
    en_attente_synchro = [r for r in toutes_reponses
                          if not r["fields"].get(CHAMP_SYNCHRONISE)]

    return {
        "total_fiches": len(fiches),
        "dans_groupe": len(dans_groupe),
        "adhesions": len(creation),
        "repartition_adhesions": dict(repartition),
        "liens_envoyes": len(liens),
        "fiches_maj": len(maj),
        "relances": len(relances),
        "desinscrites": len(desinscrites),
        "orphelines": len(orphelines),
        "reponses_en_attente": len(en_attente_synchro),
        "a_relancer": len(a_relancer),
    }


def lire_passages_syslog(debut, fin, chemins=("/var/log/syslog", "/var/log/syslog.1")):
    """Les lignes de vie des composants dans la fenêtre, si le syslog est lisible.

    Le timestamp syslog ne porte pas l'année : l'année courante est supposée,
    ce qui se trompe une fois l'an, la première semaine de janvier sur les
    lignes de décembre. Volontairement accepté pour un rapport hebdo.
    """
    annee = date.today().year
    mois = {m: i for i, m in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}
    trouve = {nom: {"derniere": None, "erreurs": 0, "derniere_ligne": None}
              for nom in LIGNES_DE_VIE}
    lisible = False

    for chemin in chemins:
        try:
            ouvrir = gzip.open if chemin.endswith(".gz") else open
            with ouvrir(chemin, "rt", encoding="utf-8", errors="replace") as f:
                for ligne in f:
                    morceaux = ligne.split(None, 5)
                    if len(morceaux) < 6:
                        continue
                    try:
                        jour_lu = date(annee, mois[morceaux[0]], int(morceaux[1]))
                    except (KeyError, ValueError):
                        continue
                    if not (debut <= jour_lu <= fin):
                        continue
                    message = morceaux[5]
                    for nom, (prefixe, motif_erreurs) in LIGNES_DE_VIE.items():
                        if prefixe not in message:
                            continue
                        lisible = True
                        entree = trouve[nom]
                        entree["derniere"] = "%s %s %s" % (
                            morceaux[0], morceaux[1], morceaux[2])
                        entree["derniere_ligne"] = message.strip()
                        if motif_erreurs:
                            m = re.search(motif_erreurs, message)
                            if m:
                                entree["erreurs"] += int(m.group(1))
        except OSError:
            continue

    return lisible, trouve


def rendre_rapport(comptes, passages, syslog_lisible, debut, fin, aujourdhui):
    """Le texte du rapport, anomalies en tête de section."""
    anomalies = []
    if comptes["adhesions"] != comptes["liens_envoyes"]:
        anomalies.append(
            "⚠ %d adhésion(s) traitée(s) mais %d lien(s) de bienvenue envoyé(s) : "
            "un mail de bienvenue n'est pas parti."
            % (comptes["adhesions"], comptes["liens_envoyes"]))
    if comptes["orphelines"]:
        anomalies.append("⚠ %d réponse(s) au formulaire sans fiche derrière."
                         % comptes["orphelines"])
    if comptes["reponses_en_attente"]:
        anomalies.append("⚠ %d réponse(s) pas encore recopiée(s) dans les fiches."
                         % comptes["reponses_en_attente"])
    if comptes["a_relancer"] > LIMITE_RELANCES:
        anomalies.append("⚠ %d fiches à relancer : au-delà de la limite d'un passage "
                         "(%d), le cron laisse un reste chaque nuit."
                         % (comptes["a_relancer"], LIMITE_RELANCES))

    lignes = [
        "RAPPORT COOP DES COMMUNS",
        "fenêtre : du %s au %s (aujourd'hui : %s)"
        % (debut.strftime("%d/%m"), fin.strftime("%d/%m"),
           aujourdhui.strftime("%d/%m")),
        "",
    ]
    lignes += ["", *anomalies] if anomalies else []
    lignes += [
        "",
        "Adhésions traitées : %d" % comptes["adhesions"],
        "   répartition : %s" % (", ".join(
            "%s %d" % (k, v) for k, v in sorted(comptes["repartition_adhesions"].items()))
            or "aucune"),
        "Liens de bienvenue envoyés : %d" % comptes["liens_envoyes"],
        "Fiches mises à jour : %d" % comptes["fiches_maj"],
        "Relances envoyées : %d" % comptes["relances"],
        "",
        "En attente maintenant : %d fiche(s) à relancer, %d réponse(s) à recopier"
        % (comptes["a_relancer"], comptes["reponses_en_attente"]),
        "Totaux : %d fiches dans l'Annuaire, %d dans le groupe adhérents, "
        "%d désinscrite(s) de la liste membres (cumul, pas de date sur ce champ)"
        % (comptes["total_fiches"], comptes["dans_groupe"], comptes["desinscrites"]),
        "",
    ]

    lignes.append("Santé des passages :")
    if syslog_lisible:
        for nom, entree in passages.items():
            if nom == "mailinglist":
                lignes.append("  mailinglist : %s" % (
                    "échec le %s : %s" % (entree["derniere"], entree["derniere_ligne"])
                    if entree["derniere"] else
                    "aucune erreur journalisée sur la fenêtre "
                    "(ce composant ne journalise que ses échecs)"))
                continue
            if entree["derniere"]:
                lignes.append("  %s : dernier passage le %s, %d erreur(s) sur la fenêtre"
                              % (nom, entree["derniere"], entree["erreurs"]))
            else:
                lignes.append("  %s : AUCUN passage sur la fenêtre ⚠" % nom)
    else:
        lignes.append("  syslog non lisible depuis cet utilisateur : "
                      "la section santé est absente de ce rapport")
    return "\n".join(lignes) + "\n"


def a_relancer_fiche(champs, aujourdhui):
    """Le test de relance, réécrit en local pour ne pas dépendre du lien.

    Une fiche est à relancer si son lien est parti depuis au moins 15 jours,
    qu'elle n'est ni désinscrite ni mise à jour. Le palier exact (15, 30, 60)
    n'a pas d'importance pour un compte : seule l'existence en a.
    """
    if champs.get(CHAMP_DESINSCRIT) or champs.get(CHAMP_DATE_MAJ):
        return False
    envoye_le = _jour(champs.get(CHAMP_LIEN_ENVOYE))
    if not envoye_le:
        return False
    return (aujourdhui - envoye_le).days >= 15


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--envoyer", action="store_true",
                   help="envoyer réellement (défaut : rendu sur stdout)")
    p.add_argument("--jours", type=int, default=7,
                   help="fenêtre du rapport en jours (défaut : 7)")
    p.add_argument("--destinataire", help="destinataire du mail "
                                          "(défaut : RAPPORT_DESTINATAIRE, sinon SMTP_USER)")
    p.add_argument("--base", help="base cible (défaut : AIRTABLE_BASE_ID_BAC_A_SABLE)")
    p.add_argument("--expediteur", help="adresse d'expédition (défaut : celle de la conf)")
    p.add_argument("--config", default=CHEMIN_CONF, help="chemin de la configuration")
    args = p.parse_args()

    try:
        code = passage(args)
    except Exception as e:
        syslog.syslog(syslog.LOG_ERR,
                      "rapport: échec du passage ({})".format(e))
        print("ERROR: le rapport a échoué : {}".format(e), file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        heartbeat.signaler(HEARTBEAT_URL, succes=False)
        return 1
    if args.envoyer:
        heartbeat.signaler(HEARTBEAT_URL, succes=True)
    return code


def passage(args):
    aujourdhui = date.today()
    fin = aujourdhui
    debut = aujourdhui - timedelta(days=args.jours - 1)

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
    expediteur = (args.expediteur or email.get("from") or os.getenv("SMTP_USER"))
    if not expediteur:
        sys.exit("Aucun expéditeur : --expediteur, conf.ovh.email.from, ou SMTP_USER.")
    destinataire = (args.destinataire or os.getenv("RAPPORT_DESTINATAIRE")
                    or os.getenv("SMTP_USER"))
    if args.envoyer and not destinataire:
        sys.exit("Aucun destinataire : --destinataire ou RAPPORT_DESTINATAIRE.")

    production = os.getenv("AIRTABLE_BASE_ID_PROD")
    print("base cible : %s%s" % (base, "  ⚠ PRODUCTION" if base == production else ""))
    print("fenêtre    : %s → %s" % (debut, fin))
    print("destinataire : %s" % destinataire)
    print()

    annuaire = AirtableClient(api_key=jeton, base_id=base, table_name="Annuaire")
    reponses = AirtableClient(api_key=jeton, base_id=base, table_name=TABLE_REPONSES)

    nom_groupe = conf.get("groupe")
    id_groupe = _id_groupe(
        AirtableClient(api_key=jeton, base_id=base, table_name=TABLE_GROUPES),
        nom_groupe) if nom_groupe else None

    comptes = compter_volumetries(annuaire, reponses, id_groupe, debut, fin, aujourdhui)
    syslog_lisible, passages = lire_passages_syslog(debut, fin)
    rapport = rendre_rapport(comptes, passages, syslog_lisible, debut, fin, aujourdhui)

    print(rapport)
    if not args.envoyer:
        print("Simulation. Rien n'est envoyé. --envoyer pour de vrai.")
        return 0

    client_mail = OVHEmailClient(
        smtp_host=credentials.get("smtp", {}).get("host") or os.getenv("SMTP_HOST"),
        smtp_port=credentials.get("smtp", {}).get("port") or os.getenv("SMTP_PORT"),
        smtp_user=credentials.get("smtp", {}).get("user") or os.getenv("SMTP_USER"),
        smtp_password=credentials.get("smtp", {}).get("password")
                      or os.getenv("SMTP_PASSWORD"),
    )
    objet = "Rapport Coop des Communs — semaine du %s au %s" % (
        debut.strftime("%d/%m"), fin.strftime("%d/%m"))
    parti = client_mail.send_email(
        sender=expediteur,
        to=[destinataire],
        subject=objet,
        body_text=rapport,
        dry_run=False,
    )
    if not parti:
        syslog.syslog(syslog.LOG_ERR, "rapport: le mail de rapport n'est pas parti")
        print("ERROR: le mail n'est pas parti (voir syslog).", file=sys.stderr)
        return 1
    syslog.syslog(syslog.LOG_INFO,
                  "rapport: envoyé à %s (fenêtre %s → %s)"
                  % (destinataire, debut, fin))
    return 0


if __name__ == "__main__":
    sys.exit(main())
