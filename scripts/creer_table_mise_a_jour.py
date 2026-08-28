#!/usr/bin/env python3
"""Pose la table de réponses du formulaire de mise à jour de fiche.

Le parcours cible : l'adhérent paie sur HelloAsso, reçoit le mail de bienvenue
avec un lien vers un formulaire Airtable **prérempli de ses données**, les
corrige, valide — et sa fiche de l'`Annuaire` est mise à jour.

Un formulaire Airtable natif ne sait que **créer** une ligne, jamais en modifier
une. Le formulaire écrit donc dans cette table-ci, et un passage de
réconciliation recopie la réponse dans la fiche désignée par `record_id`. Pour
l'adhérent la différence est invisible ; pour nous, elle laisse une trace de ce
qu'il a réellement répondu.

**Les champs sont dérivés du schéma de l'`Annuaire`, jamais réécrits ici.**
C'est le point qui compte. Le code n'utilise pas `typecast` : une valeur hors
options fait échouer l'écriture entière, et `hello_asso_sync` abandonne alors
l'adhésion complète. Une table de réponses dont les listes déroulantes auraient
divergé de l'`Annuaire` fabriquerait exactement ces valeurs-là. Recopier les
options à la main, c'est signer leur dérive.

Deux champs échappent au miroir, et c'est délibéré : `Visible sur le site` et
`Partage de donnée autorisé` sont des colonnes **texte** dans l'`Annuaire`
(elles y reçoivent la chaîne « Oui »). Un formulaire ne doit pas demander à un
adhérent de taper « Oui » à la main : ils deviennent ici des listes Oui/Non, et
c'est la réconciliation qui réécrit la chaîne attendue.

Il n'y a pas de champ « date de soumission » : l'API Airtable rend déjà
`createdTime` pour chaque enregistrement, sans qu'on ait à le stocker.

Le script est **idempotent** : il relit le schéma, crée la table si elle manque,
et n'ajoute que les champs absents. Il ne supprime ni ne modifie jamais un champ
existant, et ne touche à aucune autre table.

Usage :
    PYTHONPATH=. .venv/bin/python scripts/creer_table_mise_a_jour.py            # simulation
    PYTHONPATH=. .venv/bin/python scripts/creer_table_mise_a_jour.py --appliquer
    PYTHONPATH=. .venv/bin/python scripts/creer_table_mise_a_jour.py --spec
    PYTHONPATH=. .venv/bin/python scripts/creer_table_mise_a_jour.py --base appXXXX

La cible par défaut est le bac à sable (`AIRTABLE_BASE_ID_BAC_A_SABLE`) : on
éprouve avant de poser en production.
"""

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

from src.reconciliation import (CHAMP_FICHE, CHAMP_SYNCHRONISE, CHAMPS_FORMULAIRE,
                                COLONNES_OUI_NON)

TABLE_CIBLE = "Mise à jour fiche"
TABLE_SOURCE = "Annuaire"

# Les libellés du formulaire, les colonnes qu'ils visent et leurs explications
# sont déclarés dans `src/reconciliation.py` — le module qui les relit. Les poser
# ici aussi créerait deux listes à tenir, et donc deux listes qui divergent.

OPTIONS_OUI_NON = {"choices": [{"name": "Oui"}, {"name": "Non"}]}

# Les deux dates de suivi, posées dans l'`Annuaire` lui-même. Elles ne sont pas
# dans la table de réponses : elles décrivent l'adhérent, pas sa réponse.
#
# Il n'y a pas de compteur de relances : le nombre se déduit de l'écart entre
# `Date d'adhésion` et aujourd'hui. Un compteur est une donnée à tenir, qui se
# désynchronise dès qu'un passage échoue à mi-course ; une date, non.
CHAMPS_SUIVI_ANNUAIRE = [
    {"name": "Fiche mise à jour le", "type": "date",
     "options": {"dateFormat": {"name": "european"}},
     "description": "Renseigné par la réconciliation quand l'adhérent a validé "
                    "le formulaire de mise à jour. Vide = il ne l'a pas fait, "
                    "donc il est relançable."},
    {"name": "Dernière relance le", "type": "date",
     "options": {"dateFormat": {"name": "european"}},
     "description": "Renseigné par la relance. Empêche un second envoi le même "
                    "jour, quelle que soit la fréquence du cron."},
]


class PermissionRefusee(Exception):
    """Le jeton lit le schéma mais ne peut pas l'écrire.

    Ce n'est pas une panne, c'est le repli prévu : le script bascule sur
    l'impression de la spec exacte, à appliquer dans l'interface.
    """


# --------------------------------------------------------------------------

def _options_reprises(champ, tables_par_nom):
    """Les options d'un champ, ramenées à ce que l'API accepte en création.

    Airtable rend au schéma bien plus que ce qu'il accepte en entrée (couleurs,
    identifiants d'options, table liée sous plusieurs formes). On ne reprend que
    ce qui définit le champ, sinon la création est refusée pour des raisons qui
    n'ont rien à voir avec le champ lui-même.
    """
    type_ = champ["type"]
    options = champ.get("options") or {}

    if type_ in ("singleSelect", "multipleSelects"):
        return {"choices": [{"name": c["name"]} for c in options.get("choices", [])]}
    if type_ == "date":
        return {"dateFormat": options.get("dateFormat", {"name": "european"})}
    if type_ == "multipleRecordLinks":
        # L'`Annuaire` lu est celui de la **base cible** : l'identifiant de table
        # liée qu'il porte est donc déjà le bon. On le vérifie quand même —
        # pointer une table absente ferait échouer la création entière, et le
        # message d'Airtable ne dirait pas quel champ est en cause.
        identifiant = options.get("linkedTableId")
        connus = {t["id"] for t in tables_par_nom.values()}
        return {"linkedTableId": identifiant} if identifiant in connus else None
    if type_ == "checkbox":
        return {"icon": "check", "color": "greenBright"}
    return None


def champs_voulus(source, tables_par_nom):
    """La liste des champs à poser : libellés lisibles, types dérivés de l'Annuaire.

    Le nom du champ est le **libellé de la question**, parce qu'un formulaire
    Airtable l'affiche tel quel. Le type et les options, eux, viennent de la
    colonne de l'Annuaire qu'il vise : c'est ce qui garantit qu'une valeur saisie
    ici sera acceptée là-bas, sans `typecast`.
    """
    par_nom = {c["name"]: c for c in source["fields"]}
    voulus = [{"name": CHAMP_FICHE, "type": "singleLineText",
               "description": "Rempli automatiquement, ne pas modifier. Identifie "
                              "la fiche à mettre à jour."}]
    manquants = []

    for libelle, colonne, explication in CHAMPS_FORMULAIRE:
        origine = par_nom.get(colonne)
        if not origine:
            manquants.append("%s → colonne « %s »" % (libelle, colonne))
            continue

        if colonne in COLONNES_OUI_NON:
            # Texte dans l'Annuaire, liste ici : on ne demande pas à un adhérent
            # de taper « Oui » à la main. C'est la réconciliation qui réécrit la
            # chaîne attendue.
            champ = {"name": libelle, "type": "singleSelect",
                     "options": OPTIONS_OUI_NON}
        else:
            champ = {"name": libelle, "type": origine["type"]}
            options = _options_reprises(origine, tables_par_nom)
            if options is not None:
                champ["options"] = options
            elif origine["type"] == "multipleRecordLinks":
                manquants.append("%s (table liée introuvable)" % libelle)
                continue

        if explication:
            champ["description"] = explication
        voulus.append(champ)

    voulus.append({"name": CHAMP_SYNCHRONISE, "type": "checkbox",
                   "options": {"icon": "check", "color": "greenBright"},
                   "description": "Coché par la réconciliation. Ne pas mettre dans "
                                  "le formulaire."})
    return voulus, manquants


def renommages(cible):
    """Les champs encore nommés comme la colonne qu'ils visent.

    La table a d'abord été posée le 28/08/2026 avec les noms de colonnes de
    l'Annuaire, avant qu'on s'avise qu'un formulaire affiche ces noms tels quels
    et qu'« Partage de donnée autorisé » n'est pas une question. Ce bloc fait la
    bascule, une fois, sans perdre les réponses déjà saisies.
    """
    par_nom = {c["name"]: c for c in cible["fields"]}
    a_renommer = []
    for libelle, colonne, _ in CHAMPS_FORMULAIRE:
        if libelle == colonne:
            continue
        ancien = par_nom.get(colonne)
        if ancien and libelle not in par_nom:
            a_renommer.append((ancien["id"], colonne, libelle))
    return a_renommer


def imprimer_spec(voulus):
    """La spec exacte, pour la poser à la main quand le jeton ne peut pas écrire."""
    print()
    print("SPEC À APPLIQUER À LA MAIN — table « %s »" % TABLE_CIBLE)
    print("=" * 64)
    print()
    print("Créer une table « %s », puis ces champs dans cet ordre :" % TABLE_CIBLE)
    print()
    vise = {libelle: colonne for libelle, colonne, _ in CHAMPS_FORMULAIRE}
    for i, champ in enumerate(voulus, 1):
        ligne = "%2d. %-52s %-20s" % (i, champ["name"], champ["type"])
        if champ["name"] in vise:
            ligne += " → %s" % vise[champ["name"]]
        options = champ.get("options") or {}
        if "choices" in options:
            ligne += " — " + ", ".join(c["name"] for c in options["choices"])
        if "linkedTableId" in options:
            ligne += " — vers la table liée"
        print(ligne)
    print()
    print("Puis, dans le formulaire construit sur cette table :")
    print("  · « %s » est prérempli et **masqué** (hide_%s=true dans l'URL) ;"
          % (CHAMP_FICHE, CHAMP_FICHE))
    print("  · « %s » n'apparaît pas dans le formulaire ;" % CHAMP_SYNCHRONISE)
    print("  · « Votre structure » est limité à une **vue filtrée** de Structures,")
    print("    sans autorisation d'en créer une nouvelle — c'est là que se gagne")
    print("    la qualité de la donnée, 577 structures pour 29 sites web.")


# --------------------------------------------------------------------------

class Airtable:
    def __init__(self, base, token):
        self.base = base
        self.h = {"Authorization": "Bearer " + token,
                  "Content-Type": "application/json"}

    def schema(self):
        r = requests.get(
            "https://api.airtable.com/v0/meta/bases/%s/tables" % self.base,
            headers=self.h, timeout=30)
        r.raise_for_status()
        return r.json()["tables"]

    def creer_table(self, nom, champs):
        r = requests.post(
            "https://api.airtable.com/v0/meta/bases/%s/tables" % self.base,
            headers=self.h, json={"name": nom, "fields": champs}, timeout=30)
        self._verifier(r)
        return r.json()

    def modifier_champ(self, table_id, champ_id, **attributs):
        r = requests.patch(
            "https://api.airtable.com/v0/meta/bases/%s/tables/%s/fields/%s"
            % (self.base, table_id, champ_id),
            headers=self.h, json=attributs, timeout=30)
        self._verifier(r)

    def creer_champ(self, table_id, champ):
        r = requests.post(
            "https://api.airtable.com/v0/meta/bases/%s/tables/%s/fields"
            % (self.base, table_id),
            headers=self.h, json=champ, timeout=30)
        self._verifier(r)

    @staticmethod
    def _verifier(r):
        if r.status_code == 403:
            raise PermissionRefusee(
                "le jeton n'a pas le droit d'écrire le schéma (scope "
                "schema.bases:write, et droit créateur sur la base)")
        if r.status_code >= 400:
            raise RuntimeError("HTTP %s — %s" % (r.status_code, r.text[:300]))


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--appliquer", action="store_true",
                   help="écrit réellement dans Airtable (sinon : simulation)")
    p.add_argument("--spec", action="store_true",
                   help="imprime la spec exacte à appliquer à la main")
    p.add_argument("--base", help="base cible (défaut : AIRTABLE_BASE_ID_BAC_A_SABLE)")
    args = p.parse_args()

    base = args.base or os.getenv("AIRTABLE_BASE_ID_BAC_A_SABLE")
    token = os.getenv("AIRTABLE_TOKEN_SCHEMA") or os.getenv("AIRTABLE_API_KEY_PROD")
    if not base:
        sys.exit("Base cible inconnue : --base appXXXX, ou AIRTABLE_BASE_ID_BAC_A_SABLE "
                 "dans le .env.")
    if not token:
        sys.exit("Aucun jeton Airtable dans le .env (AIRTABLE_TOKEN_SCHEMA / "
                 "AIRTABLE_API_KEY_PROD).")

    at = Airtable(base, token)
    tables = at.schema()
    par_nom = {t["name"]: t for t in tables}

    production = os.getenv("AIRTABLE_BASE_ID_PROD")
    print("base cible : %s%s" % (base, "  ⚠ PRODUCTION" if base == production else ""))
    if base == production:
        print("   Le bac à sable est là pour éprouver ça d'abord :")
        print("   --base %s" % (os.getenv("AIRTABLE_BASE_ID_BAC_A_SABLE") or "appXXXX"))
    print()

    if TABLE_SOURCE not in par_nom:
        sys.exit("La base %s n'a pas de table « %s » : les champs se dérivent d'elle."
                 % (base, TABLE_SOURCE))

    voulus, manquants = champs_voulus(par_nom[TABLE_SOURCE], par_nom)
    if manquants:
        print("⚠ %d champ(s) de la liste absent(s) de l'%s, donc non posé(s) :"
              % (len(manquants), TABLE_SOURCE))
        for nom in manquants:
            print("   %s" % nom)
        print()

    if args.spec:
        imprimer_spec(voulus)
        return 0

    _poser_suivi(at, par_nom[TABLE_SOURCE], args.appliquer)

    cible = par_nom.get(TABLE_CIBLE)
    if not cible:
        print("→ créer la table « %s » avec ses %d champs" % (TABLE_CIBLE, len(voulus)))
        for champ in voulus:
            print("     + %-28s %s" % (champ["name"], champ["type"]))
        if not args.appliquer:
            print()
            print("Simulation. Rien n'est écrit. Relancer avec --appliquer.")
            return 0
        try:
            creee = at.creer_table(TABLE_CIBLE, voulus)
        except PermissionRefusee as e:
            print("❌ %s" % e)
            imprimer_spec(voulus)
            return 1
        print()
        print("✅ table « %s » créée — %s" % (TABLE_CIBLE, creee["id"]))
        _rappel_formulaire()
        return 0

    a_renommer = renommages(cible)
    if a_renommer:
        print("→ renommer %d champ(s) en libellé de question" % len(a_renommer))
        for _, ancien, nouveau in a_renommer:
            print("     %-28s → %s" % (ancien, nouveau))
        if args.appliquer:
            for champ_id, _, nouveau in a_renommer:
                at.modifier_champ(cible["id"], champ_id, name=nouveau)
            print("   ✅ renommés")
            cible = {t["name"]: t for t in at.schema()}[TABLE_CIBLE]
        print()

    # En simulation, les renommages n'ont pas eu lieu : on raisonne quand même
    # sur leur résultat, sinon la simulation annoncerait de recréer les champs
    # qu'elle vient d'annoncer renommer.
    existants = {c["name"] for c in cible["fields"]}
    existants |= {nouveau for _, _, nouveau in a_renommer}
    a_poser = [c for c in voulus if c["name"] not in existants]

    _poser_descriptions(at, cible, voulus, args.appliquer)
    print("table « %s » déjà présente (%s) — %d champ(s) sur %d"
          % (TABLE_CIBLE, cible["id"], len(existants), len(voulus)))
    if not a_poser:
        print("✅ tous les champs voulus sont là, rien à faire")
        _rappel_formulaire()
        return 0

    for champ in a_poser:
        print("   + %-28s %s" % (champ["name"], champ["type"]))
    if not args.appliquer:
        print()
        print("Simulation. Rien n'est écrit. Relancer avec --appliquer.")
        return 0

    for champ in a_poser:
        try:
            at.creer_champ(cible["id"], champ)
        except PermissionRefusee as e:
            print("❌ %s" % e)
            imprimer_spec(voulus)
            return 1
        print("   ✅ %s" % champ["name"])
    _rappel_formulaire()
    return 0


def _poser_descriptions(at, cible, voulus, appliquer):
    """Les explications affichées sous chaque question du formulaire.

    Elles ne se posent pas qu'à la création : un champ renommé, ou créé avant
    qu'on écrive son explication, n'en a pas. C'est le seul texte que l'adhérent
    lit pour comprendre ce qu'on lui demande — le laisser vide, c'est lui laisser
    deviner.
    """
    voulues = {c["name"]: c.get("description", "") for c in voulus}
    a_poser = [(c["id"], c["name"], voulues[c["name"]])
               for c in cible["fields"]
               if c["name"] in voulues and voulues[c["name"]]
               and (c.get("description") or "") != voulues[c["name"]]]
    if not a_poser:
        return
    print("→ poser %d explication(s) de champ" % len(a_poser))
    if not appliquer:
        for _, nom, _ in a_poser:
            print("     %s" % nom)
        return
    for champ_id, nom, description in a_poser:
        at.modifier_champ(cible["id"], champ_id, description=description)
    print("   ✅ posées")
    print()


def _poser_suivi(at, annuaire, appliquer):
    """Les deux dates de suivi, dans l'`Annuaire`.

    Elles vivent là et non dans la table de réponses parce qu'elles décrivent
    l'adhérent et non sa réponse : quelqu'un qui n'a jamais répondu doit être
    relançable, et il n'a aucune ligne dans la table de réponses.
    """
    existants = {c["name"] for c in annuaire["fields"]}
    a_poser = [c for c in CHAMPS_SUIVI_ANNUAIRE if c["name"] not in existants]
    if not a_poser:
        print("suivi : « %s » et « %s » déjà dans l'%s"
              % (CHAMPS_SUIVI_ANNUAIRE[0]["name"], CHAMPS_SUIVI_ANNUAIRE[1]["name"],
                 TABLE_SOURCE))
        return
    print("→ poser %d champ(s) de suivi dans l'%s" % (len(a_poser), TABLE_SOURCE))
    for champ in a_poser:
        print("     + %-24s %s" % (champ["name"], champ["type"]))
    if not appliquer:
        return
    for champ in a_poser:
        try:
            at.creer_champ(annuaire["id"], champ)
        except PermissionRefusee as e:
            print("   ❌ %s" % e)
            return
        print("   ✅ %s" % champ["name"])
    print()


def _rappel_formulaire():
    """Ce que l'API ne sait pas faire, et qui reste à faire à la main."""
    print()
    print("Reste à faire dans l'interface — l'API ne crée pas de formulaire :")
    print("  1. construire le formulaire sur cette table ;")
    print("  2. masquer « %s » et « %s » ;" % (CHAMP_FICHE, CHAMP_SYNCHRONISE))
    print("  3. limiter « Votre structure » à une vue filtrée de Structures, sans")
    print("     autorisation d'en créer une nouvelle ;")
    print("  4. reporter l'identifiant du formulaire (shrXXXX) dans la formule")
    print("     « lien personnalisé formulaire » de l'Annuaire.")


if __name__ == "__main__":
    sys.exit(main())
