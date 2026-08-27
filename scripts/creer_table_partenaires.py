#!/usr/bin/env python3
"""Pose la structure de la table Partenaires dans Airtable.

Traduit la proposition de Gaëlle F. du 26/08/2026 (neuf colonnes) en champs
Airtable. Trois écarts assumés par rapport à la lettre de la spec, expliqués
dans `planification/2026-08-27-table-partenaires-pour-vera.md` :

- colonne 6 : un champ lié n'a pas de limite de contacts, la question « trois
  maximum puis débordement dans les commentaires » ne se pose pas ;
- colonne 7 : portée par deux lookups qui traversent le lien Contacts, donc
  sans rien ressaisir ni modifier l'Annuaire. L'appartenance au CA y est déjà,
  `CA` étant un groupe de `Liste des groupes` ;
- colonne 3 bis : Airtable colore des options, pas des cellules. L'état de la
  relation est donc un champ à part, pas une couleur posée sur la colonne 3.

Le script est **idempotent** : il relit le schéma et n'ajoute que ce qui manque.
Il ne supprime ni ne modifie jamais un champ existant, et ne touche à aucune
autre table.

Usage :
    PYTHONPATH=. .venv/bin/python scripts/creer_table_partenaires.py            # dry-run
    PYTHONPATH=. .venv/bin/python scripts/creer_table_partenaires.py --appliquer
"""

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

TABLE_CIBLE = "Partenaires"
TABLE_AMORCE = "Partenaire (WIP)"  # coquille vide à recycler plutôt qu'à doubler

# --- Colonne 1 : secteur d'intervention -----------------------------------
#
# Airtable ne sait pas grouper des options. Le préfixe de famille rend la
# famille filtrable (« commence par Public · ») et lève au passage la collision
# entre « Association de Chercheurs » (Université) et « association de
# Chercheurs » (International), qui ne diffèrent que par la casse.
#
# Deux coquilles de la source sont corrigées ici : « Têetes » et « syructure ».
# Un select se renomme mal une fois des valeurs saisies, donc c'est maintenant
# ou jamais.

SECTEURS = {
    "Privé": [
        "Acteurs de la transition",
        "APD / Accueil aux migrants / Solidarité internationale",
        "Consultants / indépendants",
        "Éducation populaire",
        "Expertise comptable",
        "Expertise juridique",
        "Finance / banque",
        "Fondations / fonds de dotation",
        "Médias",
        "Monde associatif et associations",
        "Monde coopératif et coopératives",
        "Mutuelles",
        "Organisme de formation",
        "Porteurs de projets",
        "Soutien / défense de l'ESS",
        "Tiers-lieux",
        "Têtes de réseau des communs",
        "Têtes de réseau des tiers-lieux",
        "Think-tanks",
        "Tiers secteur de la recherche",
    ],
    "Public": [
        "Agences et instituts",
        "Associations d'élus",
        "Collectivités",
        "Députés français",
        "Formation secteur public",
        "Ministères",
        "Musées",
        "Services déconcentrés de l'État (DRAC, DREAL, DREETS…)",
    ],
    "Université": [
        "Boutique des sciences",
        "Chaires",
        "Association de chercheurs",
        "Organisateur de conférences",
        "Laboratoires",
        "Maison des sciences de l'homme",
        "Réseaux de chercheurs",
        "Revues",
        "Universités",
    ],
    "International": [
        "Association de chercheurs",
        "Députés ou membres du CESE Europe",
        "ESS au niveau UE",
        "Organisations internationales",
        "Structure de recherche-action sur les communs",
    ],
}

OPTIONS_SECTEUR = [
    "%s · %s" % (famille, libelle)
    for famille, libelles in SECTEURS.items()
    for libelle in libelles
]

# --- Colonne 2 : spécialités ---------------------------------------------
# La source s'arrête sur « …. » : la liste est ouverte, Véra la complète.
SPECIALITES = [
    "Communs",
    "Eau",
    "Économie sociale et solidaire",
    "Énergie",
    "Forêt",
    "Numérique",
    "Porteur de communs",
    "Territoire",
]

# --- Colonnes 3 et 4 ------------------------------------------------------
# La relation souhaitée reprend la relation actuelle, moins les deux étapes qui
# ne se souhaitent pas : on ne vise pas « Contact » ni « Prospection ».
RELATIONS = [
    "Contact",
    "Prospection",
    "Montage de projet",
    "Partenaire scientifique",
    "Partenaire opérationnel",
    "Terrain d'étude",
    "Commanditaire",
    "Financeur",
    "Diffusion / Valorisation",
    "Réseau / Interconnaissance",
    "Gouvernance",
    "Prestataire",
]
RELATIONS_SOUHAITEES = [r for r in RELATIONS if r not in ("Contact", "Prospection")]

# --- Colonne 3 bis --------------------------------------------------------
ETATS = [("Lien fort", "greenBright"), ("Lien faible", "orangeBright"),
         ("Difficile", "redBright")]


def selects(noms):
    return {"choices": [{"name": n} for n in noms]}


def lien(table_id):
    return {"linkedTableId": table_id}


def champs_voulus(ids):
    """Description des champs à poser. `ids` mappe un nom de table vers son id."""
    return [
        {
            "name": "Secteur d'intervention",
            "type": "multipleSelects",
            "options": selects(OPTIONS_SECTEUR),
            "description": "Colonne 1. Préfixé par famille : Airtable ne groupe pas les options.",
        },
        {
            "name": "Spécialité(s)",
            "type": "multipleSelects",
            "options": selects(SPECIALITES),
            "description": "Colonne 2. Liste ouverte, à compléter.",
        },
        {
            "name": "Relation actuelle",
            "type": "multipleSelects",
            "options": selects(RELATIONS),
            "description": "Colonne 3. Quelle relation a-t-on eu avec cette organisation ?",
        },
        {
            "name": "État de la relation",
            "type": "singleSelect",
            "options": {"choices": [{"name": n, "color": c} for n, c in ETATS]},
            "description": (
                "Colonne 3 bis. Champ à part et non une couleur posée sur la colonne 3 : "
                "Airtable colore des options, pas des cellules."
            ),
        },
        {
            "name": "Relation souhaitée",
            "type": "multipleSelects",
            "options": selects(RELATIONS_SOUHAITEES),
            "description": "Colonne 4. Sans Contact ni Prospection, qui ne se souhaitent pas.",
        },
        {
            "name": "Groupes de travail",
            "type": "multipleRecordLinks",
            "options": lien(ids["Liste des groupes"]),
            "description": "Colonne 5.",
        },
        {
            "name": "Contacts",
            "type": "multipleRecordLinks",
            "options": lien(ids["Annuaire"]),
            "description": "Colonne 6. Sans limite de nombre, rien n'est ressaisi.",
        },
        {
            "name": "Référent LCDC",
            "type": "multipleRecordLinks",
            "options": lien(ids["Annuaire"]),
            "description": "Colonne 8. Qui, au sein de la Coop, a le contact.",
        },
        {
            "name": "Structure liée",
            "type": "multipleRecordLinks",
            "options": lien(ids["Structures"]),
            "description": (
                "Hors spec. Rapproche la fiche partenaire de la fiche Structures quand "
                "l'organisation est aussi l'employeur d'un adhérent, au lieu de les laisser "
                "diverger. Aucune donnée n'est recopiée."
            ),
        },
        {
            "name": "Commentaires",
            "type": "multilineText",
            "description": "Colonne 9.",
        },
    ]


# Les lookups de la colonne 7, à part : l'API de création de champs ne les
# accepte pas toujours. S'ils échouent, ils se font en trois clics et le script
# le dit, plutôt que de laisser croire que tout est posé.
LOOKUPS = [
    ("Statut d'adhésion des contacts", "Contacts", "Cotisation LCDC"),
    ("Groupes des contacts", "Contacts", "Groupe(s)"),
]


def imprimer_spec():
    """La spec exacte, à appliquer dans l'interface Airtable.

    Sert de repli quand le jeton ne peut pas écrire le schéma. Tout y est, y
    compris les listes d'options in extenso : une heure de clics, mais rien
    d'ambigu et rien à deviner.
    """
    print("=" * 78)
    print("SPEC À APPLIQUER À LA MAIN — table « %s »" % TABLE_CIBLE)
    print("=" * 78)
    print("\n0. Renommer la table « %s » en « %s »." % (TABLE_AMORCE, TABLE_CIBLE))
    print("   Ses 3 fiches sont vides et sans nom : rien à sauvegarder.\n")

    ids = {"Liste des groupes": "Liste des groupes", "Annuaire": "Annuaire",
           "Structures": "Structures"}
    for n, champ in enumerate(champs_voulus(ids), start=1):
        opts = champ.get("options") or {}
        print("%d. %s" % (n, champ["name"]))
        print("   type : %s" % champ["type"])
        if champ.get("description"):
            print("   note : %s" % champ["description"])
        if "linkedTableId" in opts:
            print("   lien vers : %s" % opts["linkedTableId"])
        if "choices" in opts:
            print("   %d options :" % len(opts["choices"]))
            for c in opts["choices"]:
                couleur = "  (%s)" % c["color"] if c.get("color") else ""
                print("     - %s%s" % (c["name"], couleur))
        print()

    for n, (nom, via, source) in enumerate(LOOKUPS, start=len(champs_voulus(ids)) + 1):
        print("%d. %s" % (n, nom))
        print("   type : Rechercher (lookup)")
        print("   via le champ lié : %s" % via)
        print("   champ source dans Annuaire : %s" % source)
        print()
    print("=" * 78)


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

    def renommer_table(self, table_id, nom):
        r = requests.patch(
            "https://api.airtable.com/v0/meta/bases/%s/tables/%s" % (self.base, table_id),
            headers=self.h, json={"name": nom}, timeout=30)
        self._verifier(r)

    def creer_champ(self, table_id, champ):
        r = requests.post(
            "https://api.airtable.com/v0/meta/bases/%s/tables/%s/fields" % (self.base, table_id),
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
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--appliquer", action="store_true",
                   help="écrit réellement dans Airtable (sinon : simulation)")
    p.add_argument("--spec", action="store_true",
                   help="imprime la spec exacte à appliquer à la main")
    args = p.parse_args()

    load_dotenv()
    base = os.getenv("AIRTABLE_BASE_ID_PROD")
    token = os.getenv("AIRTABLE_API_KEY_PROD")
    if not base or not token:
        # Le .env local expose deux bases et la clé sans suffixe pointe vers la
        # mauvaise. On exige donc explicitement les variables _PROD.
        sys.exit("AIRTABLE_BASE_ID_PROD / AIRTABLE_API_KEY_PROD absents du .env")

    if args.spec:
        imprimer_spec()
        return 0

    at = Airtable(base, token)
    tables = at.schema()
    par_nom = {t["name"]: t for t in tables}
    ids = {n: t["id"] for n, t in par_nom.items()}

    mode = "APPLIQUE" if args.appliquer else "SIMULATION (rien n'est écrit)"
    print("Base %s — %s\n" % (base, mode))

    for requis in ("Annuaire", "Liste des groupes", "Structures"):
        if requis not in ids:
            sys.exit("table « %s » introuvable : les liens ne peuvent pas être posés" % requis)

    # 1. la table cible
    cible = par_nom.get(TABLE_CIBLE) or par_nom.get(TABLE_AMORCE)
    if cible is None:
        sys.exit("ni « %s » ni « %s » n'existent : les créer d'abord dans l'interface"
                 % (TABLE_CIBLE, TABLE_AMORCE))

    if cible["name"] != TABLE_CIBLE:
        print("→ renommer « %s » en « %s »" % (cible["name"], TABLE_CIBLE))
        if args.appliquer:
            try:
                at.renommer_table(cible["id"], TABLE_CIBLE)
            except PermissionRefusee as e:
                print("\n⚠ %s\n" % e)
                imprimer_spec()
                return 2
    else:
        print("= table « %s » déjà nommée ainsi" % TABLE_CIBLE)

    existants = {f["name"] for f in cible["fields"]}

    # 2. les champs
    poses, echecs = 0, []
    for champ in champs_voulus(ids):
        if champ["name"] in existants:
            print("= %-34s déjà présent" % champ["name"])
            continue
        detail = champ["type"]
        opts = champ.get("options") or {}
        if "choices" in opts:
            detail += ", %d options" % len(opts["choices"])
        if "linkedTableId" in opts:
            cible_lien = next(n for n, i in ids.items() if i == opts["linkedTableId"])
            detail += " → %s" % cible_lien
        print("→ %-34s %s" % (champ["name"], detail))
        if args.appliquer:
            try:
                at.creer_champ(cible["id"], champ)
                poses += 1
            except PermissionRefusee as e:
                print("\n⚠ %s\n" % e)
                imprimer_spec()
                return 2
            except Exception as e:
                echecs.append((champ["name"], str(e)))
                print("  ⚠ échec : %s" % e)

    # 3. les lookups de la colonne 7
    print()
    for nom, via, source in LOOKUPS:
        if nom in existants:
            print("= %-34s déjà présent" % nom)
            continue
        print("→ %-34s lookup : %s → Annuaire.%s" % (nom, via, source))
        if args.appliquer:
            print("  ⚠ à créer à la main : « Rechercher » via le champ %s, "
                  "champ source « %s »" % (via, source))

    print("\n%d champ(s) créé(s)." % poses)
    if echecs:
        print("%d échec(s) — à créer dans l'interface :" % len(echecs))
        for nom, err in echecs:
            print("  - %s : %s" % (nom, err))
        return 1
    if not args.appliquer:
        print("Relancer avec --appliquer pour écrire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
