#!/usr/bin/env python3
"""Pose la table des centres d'intérêt et branche les champs liés.

La liste vient de Benjamin (réponse du 13/10/2026, voir
`mails/2026-10-13-reponse-benjamin-liste-tags.md` dans le dépôt) : c'est la
liste déjà en usage côté site WordPress, le formulaire reprend la même.
64 tags, posés tels quels, apostrophes typographiques comprises.

Le champ libre « centres d'intérêt » devient une liste de tags dans une table
à part (annoncé à Benjamin et Véra le 05/10) : ajouter une valeur qui manque,
c'est ajouter une fiche dans la table, pas éditer le schéma d'un champ.

Trois gestes, tous rejouables :

- la table `Centres d'intérêt` (champ primaire `Nom`) et ses 64 fiches ;
- les deux champs qui la désignent : `Intérêts` dans l'`Annuaire` (cible de la
  synchronisation HelloAsso et de la réconciliation) et la question
  « Quels sont vos centres d'intérêt ? » de `Mise à jour fiche` (posée par le
  formulaire) ;
- le re-pointage de la formule `lien personnalisé formulaire`, qui référence
  les colonnes **par identifiant de champ** : l'ancienne colonne texte est
  renommée, la nouvelle prend son nom, la formule doit donc suivre.

**Pourquoi renommer plutôt que supprimer.** L'API ne sait pas convertir un
champ texte en champ lié. Supprimer recréerait le champ sous un autre
identifiant et briserait la formule (référence par identifiant) et les
réponses du formulaire (questions rattachées par identifiant aussi). Renommer
préserve l'identifiant : les données de test restent lisibles dans
« … (avant tags) », et la bascule en production (26/10) rejouera exactement le
même geste, données réelles comprises — à ne faire là-bas qu'**après** le
retrait des questions de profil HelloAsso, sans quoi la synchronisation
écrirait dans le champ lié avant que son rattachement n'existe.

Après `--appliquer`, le formulaire (constructeur récent, `pag…`) garde
l'ancienne question renommée : la nouvelle question se rattache à la main dans
le constructeur (glisser le champ `Quels sont vos centres d'intérêt ?` dans le
formulaire, retirer l'ancienne). L'API ne sait pas éditer une vue formulaire.

Le script est **idempotent** : il relit le schéma et ne pose que ce qui manque.
Il ne supprime jamais un champ et ne touche à aucune autre table.

Usage :
    PYTHONPATH=. .venv/bin/python scripts/creer_table_centres_interet.py            # simulation
    PYTHONPATH=. .venv/bin/python scripts/creer_table_centres_interet.py --appliquer
    PYTHONPATH=. .venv/bin/python scripts/creer_table_centres_interet.py --spec
    PYTHONPATH=. .venv/bin/python scripts/creer_table_centres_interet.py --base appXXXX

La cible par défaut est le bac à sable (`AIRTABLE_BASE_ID_BAC_A_SABLE`) : on
éprouve avant de poser en production.
"""

import argparse
import os
import re
import sys

import requests
from dotenv import load_dotenv

from src.reconciliation import CORRESPONDANCE

TABLE_CIBLE = "Centres d'intérêt"
CHAMP_PRIMAIRE = "Nom"

# La question du formulaire de mise à jour, lue là où elle est déclarée : le
# libellé vit dans `src/reconciliation.py`, partagé avec la réconciliation et
# `creer_table_mise_a_jour.py`. Le recopier ici créerait deux listes à tenir.
QUESTION_INTERETS = next(libelle for libelle, colonne in CORRESPONDANCE.items()
                         if colonne == "Intérêts")

# Les deux champs à brancher : `(table, champ)`. L'`Annuaire` d'abord (cible de
# la synchronisation), le formulaire ensuite (ce que l'adhérent remplit).
BRANCHEMENTS = [
    ("Annuaire", "Intérêts"),
    ("Mise à jour fiche", QUESTION_INTERETS),
]

# Suffixe de l'ancienne colonne texte. Elle reste : renommer préserve
# l'identifiant du champ, donc la formule de préremplissage et les réponses
# déjà déposées. À retirer à la main bien plus tard, quand plus rien ne la lit.
SUFFIXE_AVANT_TAGS = " (avant tags)"

# La liste de Benjamin, 13/10/2026. Libellés exacts du site WordPress : le
# formulaire reprend la même, ne rien reformuler.
TAGS = [
    "Agriculture",
    "Alimentation",
    "Approche par les communs",
    "Banque et finance",
    "Biodiversité",
    "Climat",
    "Collectivités et communs",
    "Communs de la connaissance",
    "Communs de proximité",
    "Communs de territoire",
    "Communs fonciers",
    "Communs numériques",
    "Communs pédagogiques",
    "Communs urbains",
    "Comptabilité écologique et sociale (CARE)",
    "Coopération internationale",
    "Coopératives",
    "Culture",
    "Démocratie dans l’entreprise",
    "Démocratie économique",
    "Démocratie participative",
    "Données ouvertes",
    "Droit et outils juridiques",
    "Eau",
    "Économie des communs",
    "Économie sociale et solidaire (ESS)",
    "Éducation populaire",
    "Énergie",
    "Évaluation et outils de gestion",
    "Financement des communs",
    "Forêts",
    "Formation et transmission",
    "Genre et féminismes",
    "Gouvernance des données",
    "Gouvernance partagée",
    "Habitat",
    "Histoire et théories des communs",
    "Intelligence artificielle",
    "Interopérabilité",
    "Justice sociale",
    "Licences et droits d’auteur",
    "Logiciels libres",
    "Logistique",
    "Migrations et accueil",
    "Mobilité",
    "Modèles économiques des communs",
    "Mutualisme",
    "Ouverture et accès aux communs",
    "Plaidoyer pour les communs",
    "Plateformes coopératives",
    "Politiques publiques",
    "Propriété et droits d’usage",
    "Protection sociale",
    "Recherche-action",
    "Ruralités",
    "Santé",
    "Science ouverte",
    "Sens du travail",
    "Services publics",
    "Sols",
    "Tiers-lieux",
    "Transition écologique",
    "Travail et emploi",
    "Union européenne et communs",
]

# La formule de préremplissage référence les colonnes par identifiant de champ
# (`{fldXXX}`), pas par nom. Le re-pointage est donc une substitution
# d'identifiant dans l'expression existante, pas une réécriture.
CHAMP_FORMULE = "lien personnalisé formulaire"


class PermissionRefusee(Exception):
    """Le jeton lit le schéma mais ne peut pas l'écrire.

    Ce n'est pas une panne : c'est le cas de repli prévu. Le script bascule
    alors sur l'impression de la spec exacte, à appliquer dans l'interface.
    """


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

    def creer_table(self, nom):
        r = requests.post(
            "https://api.airtable.com/v0/meta/bases/%s/tables" % self.base,
            headers=self.h,
            json={"name": nom,
                  "fields": [{"name": CHAMP_PRIMAIRE, "type": "singleLineText"}]},
            timeout=30)
        self._verifier(r)
        return r.json()["id"]

    def creer_champ(self, table_id, champ):
        r = requests.post(
            "https://api.airtable.com/v0/meta/bases/%s/tables/%s/fields"
            % (self.base, table_id),
            headers=self.h, json=champ, timeout=30)
        self._verifier(r)
        return r.json()["id"]

    def renommer_champ(self, table_id, field_id, nom):
        r = requests.patch(
            "https://api.airtable.com/v0/meta/bases/%s/tables/%s/fields/%s"
            % (self.base, table_id, field_id),
            headers=self.h, json={"name": nom}, timeout=30)
        self._verifier(r)

    def repointer_formule(self, table_id, field_id, expression):
        r = requests.patch(
            "https://api.airtable.com/v0/meta/bases/%s/tables/%s/fields/%s"
            % (self.base, table_id, field_id),
            headers=self.h, json={"options": {"formula": expression}}, timeout=30)
        self._verifier(r)

    def noms_existants(self, table_id):
        """Les valeurs du champ primaire, pour ne créer que ce qui manque."""
        noms = set()
        offset = None
        while True:
            params = {"fields[]": CHAMP_PRIMAIRE}
            if offset:
                params["offset"] = offset
            r = requests.get(
                "https://api.airtable.com/v0/%s/%s" % (self.base, table_id),
                headers=self.h, params=params, timeout=30)
            r.raise_for_status()
            corps = r.json()
            for fiche in corps.get("records", []):
                valeur = fiche.get("fields", {}).get(CHAMP_PRIMAIRE)
                if isinstance(valeur, str):
                    noms.add(valeur)
            offset = corps.get("offset")
            if not offset:
                return noms

    def creer_fiches(self, table_id, noms):
        """Création par lots de 10, limite de l'API Airtable."""
        for debut in range(0, len(noms), 10):
            lot = [{"fields": {CHAMP_PRIMAIRE: nom}} for nom in noms[debut:debut + 10]]
            r = requests.post(
                "https://api.airtable.com/v0/%s/%s" % (self.base, table_id),
                headers=self.h, json={"records": lot}, timeout=30)
            r.raise_for_status()

    @staticmethod
    def _verifier(r):
        if r.status_code == 403:
            raise PermissionRefusee(
                "le jeton n'a pas le droit d'écrire le schéma (scope "
                "schema.bases:write, et droit créateur sur la base)")
        if r.status_code >= 400:
            raise RuntimeError("HTTP %s — %s" % (r.status_code, r.text[:300]))


def imprimer_spec():
    """La spec exacte, à appliquer dans l'interface Airtable."""
    print("=" * 78)
    print("SPEC À APPLIQUER À LA MAIN — table « %s »" % TABLE_CIBLE)
    print("=" * 78)
    print("\n0. Créer la table « %s », champ primaire « %s » (texte)."
          % (TABLE_CIBLE, CHAMP_PRIMAIRE))
    print("   %d fiches à créer :" % len(TAGS))
    for tag in TAGS:
        print("     - %s" % tag)
    for table, champ in BRANCHEMENTS:
        print("\n1. Dans « %s » :" % table)
        print("   - renommer « %s » en « %s%s »" % (champ, champ, SUFFIXE_AVANT_TAGS))
        print("   - créer « %s » : champ lié vers « %s »" % (champ, TABLE_CIBLE))
    print("\n2. Dans l'`Annuaire`, la formule « %s » suit le renommage toute"
          % CHAMP_FORMULE)
    print("   seule (référence par identifiant) : vérifier qu'elle reste valide.")
    print("=" * 78)


def champ_lien(table_id):
    return {"name": None, "type": "multipleRecordLinks",
            "options": {"linkedTableId": table_id}}


def remplacer_identifiant(expression, ancien, nouveau):
    """Le re-pointage de la formule : `{fldAncien}` devient `{fldNouveau}`."""
    return re.sub(r"\{%s\}" % ancien, "{%s}" % nouveau, expression)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--appliquer", action="store_true",
                   help="écrit réellement dans Airtable (sinon : simulation)")
    p.add_argument("--spec", action="store_true",
                   help="imprime la spec exacte à appliquer à la main")
    p.add_argument("--base", help="base cible (défaut : AIRTABLE_BASE_ID_BAC_A_SABLE)")
    p.add_argument("--forcer", action="store_true",
                   help="autorise une base autre que le bac à sable (la bascule "
                        "prod ne se fait qu'après retrait des questions HelloAsso)")
    args = p.parse_args()

    load_dotenv()
    bac_a_sable = os.getenv("AIRTABLE_BASE_ID_BAC_A_SABLE")
    base = args.base or bac_a_sable
    token = os.getenv("AIRTABLE_TOKEN_SCHEMA") or os.getenv("AIRTABLE_API_KEY_PROD")
    if not base or not token:
        sys.exit("Base cible inconnue : --base appXXXX, ou AIRTABLE_BASE_ID_BAC_A_SABLE "
                 "dans le .env. Aucun jeton : AIRTABLE_TOKEN_SCHEMA ou AIRTABLE_API_KEY_PROD.")
    if base != bac_a_sable and not args.forcer:
        sys.exit("La cible n'est pas le bac à sable. Ce geste se rejoue en production\n"
                 "à la bascule, APRÈS le retrait des questions de profil HelloAsso\n"
                 "(sinon la synchronisation écrit dans le champ lié avant que son\n"
                 "rattachement n'existe). Passer --forcer pour le faire quand même.")

    mode = "APPLIQUE" if args.appliquer else "SIMULATION (rien n'est écrit)"
    print("Base %s — %s\n" % (base, mode))

    if args.spec:
        imprimer_spec()
        return 0

    at = Airtable(base, token)
    tables = at.schema()
    par_nom = {t["name"]: t for t in tables}
    mode_ok = True

    # 1. la table des tags ----------------------------------------------------
    cible = par_nom.get(TABLE_CIBLE)
    if cible is None:
        print("→ table « %s » (%d fiches)" % (TABLE_CIBLE, len(TAGS)))
        if args.appliquer:
            table_id = at.creer_table(TABLE_CIBLE)
            cible = {"id": table_id, "name": TABLE_CIBLE, "fields": []}
        else:
            table_id = "tblÀ_CRÉER"
            cible = {"id": table_id, "name": TABLE_CIBLE, "fields": []}
    else:
        table_id = cible["id"]
        print("= table « %s » déjà présente" % TABLE_CIBLE)

    existants = at.noms_existants(table_id) if args.appliquer or cible["id"] != "tblÀ_CRÉER" else set()
    manquants = [t for t in TAGS if t not in existants]
    if manquants:
        print("→ %d fiche(s) à créer (%d déjà présentes)"
              % (len(manquants), len(TAGS) - len(manquants)))
        if args.appliquer:
            at.creer_fiches(table_id, manquants)
    else:
        print("= %d fiches déjà présentes" % len(TAGS))

    # 2. les champs liés ------------------------------------------------------
    renommages = []  # (table, ancien field_id, nouveau field_id)
    for table_nom, champ_nom in BRANCHEMENTS:
        table = par_nom.get(table_nom)
        if table is None:
            print("⚠ table « %s » introuvable : branchement impossible" % table_nom)
            mode_ok = False
            continue

        def trouvé():
            return next((f for f in table["fields"] if f["name"] == champ_nom), None)

        champ = trouvé()
        if champ and champ["type"] == "multipleRecordLinks":
            pointe = champ.get("options", {}).get("linkedTableId")
            if pointe == table_id:
                print("= %-22s %-42s déjà lié" % (table_nom, champ_nom))
                continue
            print("⚠ %-22s %-42s lié ailleurs (%s) : à vérifier à la main"
                  % (table_nom, champ_nom, pointe))
            mode_ok = False
            continue

        action = "renommer en « %s%s » + créer le champ lié" % (champ_nom, SUFFIXE_AVANT_TAGS) \
            if champ else "créer le champ lié"
        print("→ %-22s %-42s %s" % (table_nom, champ_nom, action))
        if not args.appliquer:
            continue
        try:
            if champ:
                at.renommer_champ(table["id"], champ["id"], champ_nom + SUFFIXE_AVANT_TAGS)
                # relire le schéma : le renommage change la table qu'on parcourt
                table = next(t for t in at.schema() if t["id"] == table["id"])
                par_nom[table_nom] = table
            nouveau_id = at.creer_champ(
                table["id"], dict(champ_lien(table_id), name=champ_nom))
            if champ:
                renommages.append((table_nom, champ["id"], nouveau_id))
        except PermissionRefusee as e:
            print("\n⚠ %s\n" % e)
            imprimer_spec()
            return 2
        except Exception as e:
            print("  ⚠ échec : %s" % e)
            mode_ok = False

    # 3. la formule de préremplissage ----------------------------------------
    annuaire = par_nom.get("Annuaire")
    formule_field = next((f for f in (annuaire or {}).get("fields", [])
                          if f["name"] == CHAMP_FORMULE), None)
    if formule_field:
        expression = formule_field.get("options", {}).get("formula", "")
        nouvelle = expression
        for _, ancien_id, nouveau_id in renommages:
            nouvelle = remplacer_identifiant(nouvelle, ancien_id, nouveau_id)
        if nouvelle != expression:
            print("→ %s : re-pointage de %d référence(s)"
                  % (CHAMP_FORMULE, len(renommages)))
            if args.appliquer:
                try:
                    at.repointer_formule(annuaire["id"], formule_field["id"], nouvelle)
                except Exception as e:
                    print("  ⚠ échec : %s" % e)
                    print("     La formule affiche l'ancienne colonne renommée :")
                    print("     la re-pointer à la main sur « Intérêts » dans l'interface.")
                    mode_ok = False
        else:
            print("= %s déjà à jour" % CHAMP_FORMULE)

    # 4. ce qui reste à la main ----------------------------------------------
    if args.appliquer and renommages:
        print()
        print("Dans le constructeur du formulaire (vue « form » du pag…) :")
        print("  1. retirer la question « %s%s »" % (QUESTION_INTERETS, SUFFIXE_AVANT_TAGS))
        print("  2. y glisser le nouveau champ « %s »" % QUESTION_INTERETS)
        print("     (l'API ne sait pas éditer une vue formulaire)")

    print()
    if not mode_ok:
        print("Des écarts restent à traiter à la main (voir ⚠ ci-dessus).")
        return 1
    if not args.appliquer:
        print("Relancer avec --appliquer pour écrire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
