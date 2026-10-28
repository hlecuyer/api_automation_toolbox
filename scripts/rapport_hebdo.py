#!/usr/bin/env python3
"""Rapport périodique : ce que le système a fait, lu depuis les données.

Une seule visée : savoir, après déploiement, si tout fonctionne, sans ouvrir
ni Airtable ni les logs. Un mail court, une section par composant, deux
familles de faits :

- **les volumétries**, comptées dans la base (adhésions, fiches créées hors
  flux, liens envoyés, fiches mises à jour, relances) : tout champ daté existe
  déjà, rien n'est à inventer ;
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
from src.templates import signature, welcome_email

CHEMIN_CONF = "config/hello-asso-automation-conf.json"

HEARTBEAT_URL = "HEARTBEAT_URL_RAPPORT"

TABLE_REPONSES = "Mise à jour fiche"
TABLE_GROUPES = "Liste des groupes"

CHAMP_DATE_CREATION = "Date de création"
CHAMP_NOUVEAU = "Nouvel adhérent"
CHAMP_ADRESSE = "E-mail"
CHAMP_LIEN_ENVOYE = "Lien envoyé le"
CHAMP_DATE_MAJ = "Fiche mise à jour le"
CHAMP_DERNIERE_RELANCE = "Dernière relance le"
CHAMP_DESINSCRIT = "désinscrit liste membres"
CHAMP_GROUPES = "Groupe(s)"

# Les passages qui se signalent en syslog. Le mailinglist écrit deux familles
# de lignes : sa ligne de vie (`statut=ok|échec`) et ses erreurs unitaires. La
# première version de ce rapport supposait qu'il n'écrivait que des erreurs et
# affichait donc « échec » sur un passage réussi : le statut se lit, il ne se
# suppose pas.
LIGNES_DE_VIE = {
    "hello_asso_sync": ("hello_asso_sync: passage terminé", "erreurs=(\\d+)"),
    "relance_fiche": ("relance_fiche: relances_dues=", "erreurs=(\\d+)"),
    "mailinglist": ("mailinglist", None),
}

# La ligne de vie du mailinglist : `passage terminé statut=ok listes=24
# ajouts=12 suppressions=3 erreurs=0`.
STATUT_MAILINGLIST = re.compile(r"passage terminé statut=(?P<statut>ok|échec)")

# Ses erreurs unitaires, qui précèdent la ligne de vie et ne doivent pas
# disparaître derrière elle : un abonné refusé par OVH journalise en LOG_ERR.
ERREUR_MAILINGLIST = re.compile(r"ERROR:|échec|refused by OVH|does not exists")


def etat_mailinglist(entree):
    """Ce que disent les passages des mailing lists, sans les supposer.

    Le rapport supposait que l'extracter n'écrivait que ses échecs : il
    affichait donc « échec » sur un passage réussi. L'extracter écrit en fait
    une ligne de vie par passage (`statut=ok|échec`), plus des erreurs unitaires
    quand un abonné se fait refuser.

    Deux faits à dire séparément quand ils coexistent : le dernier passage
    réussi **et** une erreur unitaire sur la fenêtre. La seconde ne doit pas
    disparaître sous le premier.
    """
    if not entree["derniere"]:
        if entree["erreurs"]:
            return "%d erreur(s) unitaire(s) sur la fenêtre, aucune ligne de vie" % (
                entree["erreurs"])
        return "aucune ligne sur la fenêtre"
    ligne = entree["derniere_ligne"] or ""
    m = STATUT_MAILINGLIST.search(ligne)
    if not m or m.group("statut") != "ok":
        return "échec le %s : %s" % (entree["derniere"], ligne)
    details = []
    for motif, mot in ((r"ajouts=(\d+)", "ajout"),
                       (r"suppressions=(\d+)", "suppression"),
                       (r"erreurs=(\d+)", "erreur")):
        trouve = re.search(motif, ligne)
        if not trouve:
            continue
        nombre = int(trouve.group(1))
        details.append("%d %s%s" % (nombre, mot, "s" if nombre > 1 else ""))
    resume = "dernier passage le %s, statut ok%s" % (
        entree["derniere"], " (%s)" % ", ".join(details) if details else "")
    if entree["erreurs"]:
        resume += " ; %d erreur(s) unitaire(s) sur la fenêtre, la dernière le %s : %s" % (
            entree["erreurs"], entree["derniere_erreur"], entree["ligne_erreur"])
    return resume

# L'horodatage RFC 3339 en tête de ligne (`2026-10-24T22:00:39.641851+00:00`)
# suivi de l'hôte. L'année, contrairement au format classique, est portée par
# la ligne. Mesuré sur la prod le 26/10/2026 : sans lui, aucune ligne ne se
# lit et le rapport annonce « syslog non lisible » depuis un utilisateur qui
# pourtant le lit (groupe adm, permissions 640 vérifiées).
LIGNE_SYSLOG_ISO = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\s+\S+\s+(.*)$"
)


def _decouper_ligne_syslog(ligne, annee, mois):
    """Rend (jour, horodatage lisible, message), ou None si ligne illisible.

    Deux formats cohabitent selon l'hôte : l'horodatage syslog classique
    (`Oct 24 22:00:39`, l'année absente et supposée courante, ce qui se trompe
    une fois l'an, la première semaine de janvier sur les lignes de décembre)
    et le RFC 3339. Rendre les deux, sinon le rapport se tait sur des hôtes
    pourtant lisibles.
    """
    m = LIGNE_SYSLOG_ISO.match(ligne)
    if m:
        try:
            jour = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
        return (jour,
                "%s-%s-%s %s" % (m.group(1), m.group(2), m.group(3), m.group(4)),
                m.group(5))

    morceaux = ligne.split(None, 5)
    if len(morceaux) < 6:
        return None
    try:
        jour = date(annee, mois[morceaux[0]], int(morceaux[1]))
    except (KeyError, ValueError):
        return None
    return jour, "%s %s %s" % (morceaux[0], morceaux[1], morceaux[2]), morceaux[5]


LIMITE_RELANCES = 25  # même limite que relancer_fiches : la toucher est un signal


def logo_inline():
    """Le logo embarqué de la signature, même mécanique que les autres mails."""
    try:
        with open(welcome_email.LOGO_PATH, "rb") as f:
            return [("logo", f.read(), "png")]
    except OSError as e:
        syslog.syslog(
            syslog.LOG_WARNING,
            "rapport: logo absent ({}) — mail sans logo embarqué".format(e),
        )
        return None


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

    # Une « adhésion traitée » est une fiche créée par le flux HelloAsso, et
    # il la reconnaît à son tampon : `Nouvel adhérent` est posé par
    # l'upsert à chaque passage (Oui à la création, Non sur une mise à jour).
    # Une saisie manuelle crée une fiche sans tampon ni lien envoyé : le
    # 26/10/2026, onze contacts Non Adhérent saisis d'un coup ont été comptés
    # « adhésions » avec zéro paiement HelloAsso dans la semaine, et l'alerte
    # « mail de bienvenue non parti » a hurlé pour rien. Elles se comptent à
    # part, visibles, sans être des adhésions.
    creation = [f for f in fiches
                if _dans_fenetre(f["fields"].get(CHAMP_DATE_CREATION), debut, fin)]
    creation_sync = [f for f in creation if f["fields"].get(CHAMP_NOUVEAU)]
    hors_flux = [f for f in creation if not f["fields"].get(CHAMP_NOUVEAU)]
    # L'anomalie fondatrice (le mail perdu) se dit par ses adresses : une
    # fiche créée par le flux sans lien posé dans la fenêtre. Comparer deux
    # totaux traitées/liens ne prouve rien dès qu'une réadhésion ou une
    # saisie manuelle s'y glisse — le 26/10 encore.
    sans_bienvenue = [f["fields"].get(CHAMP_ADRESSE, "?") for f in creation_sync
                      if not _dans_fenetre(f["fields"].get(CHAMP_LIEN_ENVOYE),
                                          debut, fin)]
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
    # (« Oui » à la création d'un nouveau, « Non » sur une réadhésion). Les
    # adresses sont listées dans le rapport : c'est un mail interne, et une
    # liste d'adresses se lit mieux qu'un compte quand il faut agir.
    repartition = Counter(f["fields"].get(CHAMP_NOUVEAU) or "non renseigné"
                          for f in creation_sync)
    adhesions_details = [
        {"email": f["fields"].get(CHAMP_ADRESSE, "?"),
         "nouveau": f["fields"].get(CHAMP_NOUVEAU) or "non renseigné"}
        for f in creation_sync
    ]
    hors_flux_adresses = [f["fields"].get(CHAMP_ADRESSE, "?") for f in hors_flux]

    toutes_reponses = reponses.list_records()
    orphelines = [r for r in toutes_reponses
                  if r["fields"].get(CHAMP_FICHE)
                  and r["fields"][CHAMP_FICHE] not in ids_annuaire]
    en_attente_synchro = [r for r in toutes_reponses
                          if not r["fields"].get(CHAMP_SYNCHRONISE)]

    return {
        "total_fiches": len(fiches),
        "dans_groupe": len(dans_groupe),
        "adhesions": len(creation_sync),
        "hors_flux": len(hors_flux),
        "hors_flux_adresses": hors_flux_adresses,
        "sans_bienvenue": sans_bienvenue,
        "repartition_adhesions": dict(repartition),
        "adhesions_details": adhesions_details,
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

    Deux formats d'horodatage cohabitent : voir `_decouper_ligne_syslog`.
    """
    annee = date.today().year
    mois = {m: i for i, m in enumerate(
        ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), start=1)}
    trouve = {nom: {"derniere": None, "erreurs": 0, "derniere_ligne": None,
                    "derniere_erreur": None, "ligne_erreur": None}
              for nom in LIGNES_DE_VIE}
    lisible = False

    for chemin in chemins:
        try:
            ouvrir = gzip.open if chemin.endswith(".gz") else open
            with ouvrir(chemin, "rt", encoding="utf-8", errors="replace") as f:
                for ligne in f:
                    decoupee = _decouper_ligne_syslog(ligne, annee, mois)
                    if not decoupee:
                        continue
                    jour_lu, horodatage, message = decoupee
                    if not (debut <= jour_lu <= fin):
                        continue
                    for nom, (prefixe, motif_erreurs) in LIGNES_DE_VIE.items():
                        if prefixe not in message:
                            continue
                        lisible = True
                        entree = trouve[nom]
                        if nom == "mailinglist":
                            # Deux familles de lignes pour ce composant : sa
                            # ligne de vie, qui date le passage, et ses erreurs
                            # unitaires, qui se comptent sans effacer la
                            # précédente. Prendre la dernière ligne venue
                            # ferait dire « échec » au rapport sur un abonné
                            # refusé alors que le passage s'est terminé ok.
                            if STATUT_MAILINGLIST.search(message):
                                entree["derniere"] = horodatage
                                entree["derniere_ligne"] = message.strip()
                            elif ERREUR_MAILINGLIST.search(message):
                                entree["erreurs"] += 1
                                entree["derniere_erreur"] = horodatage
                                entree["ligne_erreur"] = message.strip()
                            continue
                        entree["derniere"] = horodatage
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
    if comptes["sans_bienvenue"]:
        anomalies.append(
            "⚠ %d adhésion(s) sans mail de bienvenue : %s."
            % (len(comptes["sans_bienvenue"]),
               ", ".join(comptes["sans_bienvenue"])))
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
    ]
    for categorie in ("Oui", "Non"):
        adresses = [a["email"] for a in comptes["adhesions_details"]
                    if a["nouveau"] == categorie]
        if adresses:
            lignes.append("   %s : %s" % (
                "nouveaux adhérents" if categorie == "Oui" else "réadhésions",
                ", ".join(adresses)))
    lignes += [
        "Liens de bienvenue envoyés : %d" % comptes["liens_envoyes"],
        "Fiches créées hors flux : %d" % comptes["hors_flux"],
    ]
    if comptes["hors_flux_adresses"]:
        lignes.append("   %s" % ", ".join(comptes["hors_flux_adresses"]))
    lignes += [
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
                lignes.append("  mailinglist : %s" % etat_mailinglist(entree))
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


COULEUR = "#3CB1D4"      # le bleu des mails de la Coop
COULEUR_TEXTE = "#4B4B4D"
COULEUR_ANOMALIE = "#B45309"   # orange sobre : lu, sans crier
FOND_ANOMALIE = "#FEF3C7"
FOND_OK = "#ECFDF5"
VERT = "#047857"

BLOC_SIGNATURE = """                    <tr>
                        <td style="padding: 28px 32px 8px 32px;">
                            <p style="margin: 0;">Bien cordialement,</p>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 8px 32px 32px 32px;">
                            <table cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td valign="top" style="padding-right: 12px;">
                                        <img width="85" height="69" src="cid:logo" alt="La Coop des Communs" style="display:block;">
                                    </td>
                                    <td valign="top">
                                        <p style="margin:0;">
                                            <strong style="font-size:13px; color:#4B4B4D;">@@SIG_NAME@@</strong><br>
                                            <span style="color:#3CB1D4; font-size:12px;">@@SIG_ROLE@@</span>
                                        </p>
                                        <p style="margin: 4px 0 0 0; font-size:12px;">@@SIG_PHONE@@<br>
                                            <a href="mailto:@@SIG_EMAIL@@" style="color:#4B4B4D;">@@SIG_EMAIL@@</a><br>
                                            <a href="https://coopdescommuns.org/" style="color:#4B4B4D;">coopdescommuns.org</a>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>"""


def _ligne_metric(label, valeur, couleur=COULEUR_TEXTE):
    """Une ligne chiffre du rapport, en table HTML compatible clients mail."""
    return ('<tr>'
            '<td style="padding: 6px 0; color:#666; font-size:14px;">%s</td>'
            '<td align="right" style="padding: 6px 0; font-size:14px; '
            'font-weight:bold; color:%s;">%s</td>'
            '</tr>' % (label, couleur, valeur))


def _liste_adresses(adresses):
    if not adresses:
        return ""
    return ("<p style='margin:2px 0 8px 0; font-size:13px; color:#666;'>%s</p>"
            % ", ".join(adresses))


def rendre_rapport_html(comptes, passages, syslog_lisible, debut, fin, aujourdhui):
    """Le même rapport en HTML, aux couleurs des mails de la Coop.

    Même contenu que la version texte, même ordre : un seul fait, deux
    habillages. La signature est le bloc exact des autres mails.
    """
    anomalies_html = []
    if comptes["sans_bienvenue"]:
        anomalies_html.append(
            "%d adhésion(s) sans mail de bienvenue : %s."
            % (len(comptes["sans_bienvenue"]),
               ", ".join(comptes["sans_bienvenue"])))
    if comptes["orphelines"]:
        anomalies_html.append("%d réponse(s) au formulaire sans fiche derrière."
                              % comptes["orphelines"])
    if comptes["reponses_en_attente"]:
        anomalies_html.append("%d réponse(s) pas encore recopiée(s) dans les fiches."
                              % comptes["reponses_en_attente"])
    if comptes["a_relancer"] > LIMITE_RELANCES:
        anomalies_html.append(
            "%d fiches à relancer : au-delà de la limite d\'un passage (%d)."
            % (comptes["a_relancer"], LIMITE_RELANCES))

    if anomalies_html:
        fond, bord, titre = FOND_ANOMALIE, COULEUR_ANOMALIE, "À regarder"
        corps_anomalies = "".join(
            '<p style="margin:0 0 6px 0; color:%s; font-size:13px;">⚠ %s</p>'
            % (bord, texte) for texte in anomalies_html)
    else:
        fond, bord, titre = FOND_OK, VERT, "Aucune anomalie détectée"
        corps_anomalies = (
            '<p style="margin:0; color:' + VERT + '; font-size:13px;">'
            "Rien d\'anormal sur la fenêtre.</p>")

    bloc_anomalies = (
        '<tr><td style="padding: 20px 32px 0 32px;">'
        '<table width="100%%" cellspacing="0" cellpadding="0" border="0" '
        'style="background-color:' + fond + '; border-left:4px solid ' + bord
        + '; border-radius:4px;">'
        '<tr><td style="padding: 14px 18px;">'
        '<p style="margin:0 0 6px 0; font-size:12px; font-weight:bold; '
        'letter-spacing:1px; color:' + bord + '; text-transform:uppercase;">'
        + titre + "</p>" + corps_anomalies
        + "</td></tr></table></td></tr>")

    nouveaux = [a["email"] for a in comptes["adhesions_details"]
                if a["nouveau"] == "Oui"]
    readhesions = [a["email"] for a in comptes["adhesions_details"]
                   if a["nouveau"] == "Non"]
    detail_adhesions = ""
    if nouveaux:
        detail_adhesions += _ligne_detail("Nouveaux adhérents", nouveaux)
    if readhesions:
        detail_adhesions += _ligne_detail("Réadhésions", readhesions)
    if comptes["hors_flux_adresses"]:
        detail_adhesions += _ligne_detail("Fiches créées hors flux",
                                         comptes["hors_flux_adresses"])

    metriques = ""
    for label, valeur in (
            ("Adhésions traitées", str(comptes["adhesions"])),
            ("Liens de bienvenue envoyés", str(comptes["liens_envoyes"])),
            ("Fiches créées hors flux", str(comptes["hors_flux"])),
            ("Fiches mises à jour", str(comptes["fiches_maj"])),
            ("Relances envoyées", str(comptes["relances"])),
            ("En attente : fiches à relancer", str(comptes["a_relancer"])),
            ("En attente : réponses à recopier", str(comptes["reponses_en_attente"])),
            ("Désinscrites de la liste membres (cumul)", str(comptes["desinscrites"]))):
        metriques += _ligne_metric(label, valeur)
    detail_adhesions = detail_adhesions.replace("%%", "%")

    if syslog_lisible:
        lignes_sante = []
        for nom, entree in passages.items():
            if nom == "mailinglist":
                lignes_sante.append("mailinglist : " + etat_mailinglist(entree))
            elif entree["derniere"]:
                lignes_sante.append(
                    "%s : dernier passage le %s, %d erreur(s) sur la fenêtre"
                    % (nom, entree["derniere"], entree["erreurs"]))
            else:
                lignes_sante.append("%s : AUCUN passage sur la fenêtre ⚠" % nom)
        corps_sante = "".join(
            '<p style="margin:0 0 4px 0; font-size:13px; color:#666;">%s</p>' % l
            for l in lignes_sante)
    else:
        corps_sante = (
            '<p style="margin:0; font-size:13px; color:#666;">'
            "syslog non lisible depuis cet utilisateur : section santé absente "
            "de ce rapport.</p>")

    html = (
        '<html>\n<head><meta charset="UTF-8"></head>\n'
        '<body style="margin:0; padding:0; background-color:#f5f7f9; '
        'font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333;">\n'
        '<table width="100%%" cellspacing="0" cellpadding="0" border="0" '
        'style="background-color:#f5f7f9; padding: 24px 0;"><tr><td align="center">\n'
        '<table width="600" cellspacing="0" cellpadding="0" border="0" '
        'style="background-color:#ffffff; border-radius: 8px; max-width: 600px; '
        'width: 100%%;">\n'
        '<tr><td style="padding: 32px 32px 0 32px;">'
        '<h1 style="margin:0; font-size:20px; color:' + COULEUR + ';">'
        "Rapport Coop des Communs</h1>"
        '<p style="margin:4px 0 0 0; color:#666; font-size:13px;">semaine du '
        + debut.strftime("%d/%m") + " au " + fin.strftime("%d/%m") + "</p>"
        '</td></tr>\n'
        + bloc_anomalies + "\n"
        + '<tr><td style="padding: 20px 32px 0 32px;">'
        '<table width="100%%" cellspacing="0" cellpadding="0" border="0" '
        'style="border-top:2px solid #eef2f5;">'
        '<tr><td style="padding: 12px 0 2px 0;"></td></tr>'
        + metriques + "</table>"
        + detail_adhesions + "</td></tr>\n"
        + '<tr><td style="padding: 20px 32px 0 32px;">'
        '<p style="margin:0 0 8px 0; font-size:12px; font-weight:bold; '
        'letter-spacing:1px; color:#99A3AB; text-transform:uppercase;">'
        "Santé des passages</p>" + corps_sante + "</td></tr>\n"
        + BLOC_SIGNATURE + "\n"
        + "</table></td></tr></table>\n</body>\n</html>"
    )
    return signature.appliquer(html)


def _ligne_detail(titre, adresses):
    """La liste des adresses d\'une catégorie d\'adhésions, sous le tableau."""
    return (
        '<p style="margin:6px 0 2px 0; font-size:13px; color:' + COULEUR_TEXTE
        + '; font-weight:bold;">' + titre + " :</p>"
        + "<p style='margin:0 0 8px 0; font-size:13px; color:#666;'>"
        + ", ".join(adresses) + "</p>")
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
    # Le rapport est un mail interne : il part de l'identité du relais
    # (SMTP_USER, `support@dsi.coop` en production), pas de l'expéditeur
    # institutionnel des mails aux adhérents (conf.ovh.email.from, la boîte
    # de la présidente). Rien d'un rapport de supervision ne doit ressembler
    # à un courrier de la Coop.
    expediteur = args.expediteur or os.getenv("SMTP_USER")
    if not expediteur:
        sys.exit("Aucun expéditeur : --expediteur ou SMTP_USER.")
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
    rapport_html = rendre_rapport_html(comptes, passages, syslog_lisible,
                                       debut, fin, aujourdhui)

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
        body_html=rapport_html,
        inline_images=logo_inline(),
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
