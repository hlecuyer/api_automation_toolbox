#!/usr/bin/env python3
"""Outillage du bac à sable Airtable : dérive, données fictives, contrôle.

Un environnement de répétition ne vaut que par deux propriétés, et les deux se
perdent en silence :

1. **Il ressemble à la production.** Sinon une répétition qui passe ne garantit
   rien. Le schéma d'une base Airtable bouge par l'interface, sans commit et
   sans trace — la précédente base « dev » avait dérivé jusqu'à porter 47 champs
   là où la production en a 41, et ses quatre champs liés étaient devenus du
   texte simple.
2. **Il ne contient aucune donnée réelle.** Sinon ce n'est pas un bac à sable,
   c'est une seconde copie du fichier des adhérents — et c'est le cas par
   défaut, puisqu'un environnement de test se fabrique presque toujours en
   copiant la production. La sous-commande `verifier` existe pour que cette
   dérive-là ne puisse pas passer inaperçue.

Ce script rend ces deux propriétés vérifiables à la demande, donc falsifiables.

Trois sous-commandes :

    comparer   dérive entre la base de référence (production) et le bac à sable
    verifier   aucune adresse du bac à sable ne peut atteindre une vraie personne
    peupler    génère des adhérents fictifs, des groupes et des structures

Usage :
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py comparer --base appXXXX
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py verifier --base appXXXX
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py peupler  --base appXXXX --nombre 40
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py peupler  --base appXXXX --appliquer

Le bac à sable se désigne par `--base`, ou par `AIRTABLE_BASE_ID_BAC_A_SABLE`
dans le `.env`. La référence est `AIRTABLE_BASE_ID_PROD`.
"""

import argparse
import os
import random
import re
import sys
import unicodedata

import requests
from dotenv import load_dotenv

API = "https://api.airtable.com/v0"

# Le périmètre. Les quatre autres tables de la production sont des vestiges
# (« formulaire 2022 test », « Vote AG 2023 », « import GT 2023 », « comparatif
# listes membres ») : aucun code ne les touche. Elles restent hors périmètre, et
# `comparer` le dit à chaque passage — un écart tu n'est pas un écart connu.
TABLES_UTILES = [
    "Annuaire",
    "Liste des groupes",
    "Structures",
    "Liste Diffusion",
    "Ajout à un groupe",
    "Partenaires",
]

# Domaines réservés par l'IANA (RFC 2606) : ils n'ont pas d'enregistrement MX et
# ne peuvent structurellement pas recevoir de courrier. C'est ce qui fait de la
# vérification d'adresses un contrôle et non une convention.
DOMAINES_FICTIFS = ("example.org", "example.com", "example.net", "example.edu")

# Types de champs qu'Airtable refuse de créer par l'API. Le seul moyen de les
# obtenir sans les ressaisir un par un est la duplication de base dans
# l'interface, « sans les enregistrements ».
TYPES_NON_CREABLES = {
    "formula", "rollup", "count", "multipleLookupValues", "createdTime",
    "lastModifiedTime", "createdBy", "lastModifiedBy", "autoNumber", "button",
}


# --------------------------------------------------------------------------
# Accès Airtable
# --------------------------------------------------------------------------

class Airtable:
    def __init__(self, jeton):
        self.h = {"Authorization": "Bearer " + jeton}

    def schema(self, base):
        r = requests.get("%s/meta/bases/%s/tables" % (API, base), headers=self.h, timeout=30)
        self._verifier(r)
        return r.json()["tables"]

    def enregistrements(self, base, table, champs=None):
        sortie, offset = [], None
        while True:
            p = {"pageSize": 100}
            if champs:
                p["fields[]"] = champs
            if offset:
                p["offset"] = offset
            r = requests.get("%s/%s/%s" % (API, base, table), headers=self.h, params=p, timeout=30)
            self._verifier(r)
            d = r.json()
            sortie += d["records"]
            offset = d.get("offset")
            if not offset:
                return sortie

    def creer(self, base, table, fiches):
        """Crée par paquets de 10, la limite de l'API.

        Sans `typecast`, exprès : c'est le réglage de la production, et une
        valeur hors options doit échouer ici plutôt que d'être silencieusement
        convertie. Un bac à sable plus permissif que la production laisserait
        passer la classe de bug qu'il est censé attraper.
        """
        crees = []
        for i in range(0, len(fiches), 10):
            paquet = [{"fields": f} for f in fiches[i:i + 10]]
            r = requests.post("%s/%s/%s" % (API, base, table), headers=self.h,
                              json={"records": paquet}, timeout=30)
            self._verifier(r)
            crees += r.json()["records"]
        return crees

    @staticmethod
    def _verifier(r):
        if not r.ok:
            sys.exit("Airtable %s : %s" % (r.status_code, r.text[:400]))


# --------------------------------------------------------------------------
# comparer — la dérive de schéma
# --------------------------------------------------------------------------

def _par_nom(table):
    """Regroupe les champs par nom.

    La production a deux champs nommés « Annuaire copy » dans la même table, de
    types différents. Un dictionnaire simple en perdrait un sans rien dire.
    """
    index = {}
    for champ in table["fields"]:
        index.setdefault(champ["name"], []).append(champ)
    return index


def _options(champ):
    """Noms des options d'un select, ou None si ce n'en est pas un.

    Comparées parce que le code n'utilise pas `typecast` : une option présente
    en production et absente du bac à sable ferait échouer l'écriture entière,
    et `hello_asso_sync` abandonne alors l'adhésion complète, mail de bienvenue
    compris. C'est le défaut du 26/08 sur le champ Genre.
    """
    if champ["type"] not in ("singleSelect", "multipleSelects"):
        return None
    return sorted(o["name"] for o in champ.get("options", {}).get("choices", []))


def comparer(at, reference, cible):
    ref = {t["name"]: t for t in at.schema(reference)}
    bac = {t["name"]: t for t in at.schema(cible)}
    ecarts = 0

    print("référence  %s  (%d tables)" % (reference, len(ref)))
    print("bac à sable %s  (%d tables)" % (cible, len(bac)))
    print()

    for nom in TABLES_UTILES:
        if nom not in ref:
            print("⚠  « %s » absente de la RÉFÉRENCE — le périmètre du script est à revoir" % nom)
            ecarts += 1
            continue
        if nom not in bac:
            print("❌ table « %s » absente du bac à sable" % nom)
            ecarts += 1
            continue

        cr, cb = _par_nom(ref[nom]), _par_nom(bac[nom])
        lignes = []

        for champ in sorted(set(cr) - set(cb)):
            types = ", ".join(c["type"] for c in cr[champ])
            main = "  ⚠ à poser à la main" if any(
                c["type"] in TYPES_NON_CREABLES for c in cr[champ]) else ""
            lignes.append("   manquant  %-42s %s%s" % (champ, types, main))

        for champ in sorted(set(cb) - set(cr)):
            lignes.append("   en trop   %-42s %s" % (
                champ, ", ".join(c["type"] for c in cb[champ])))

        for champ in sorted(set(cr) & set(cb)):
            tr = sorted(c["type"] for c in cr[champ])
            tb = sorted(c["type"] for c in cb[champ])
            if tr != tb:
                lignes.append("   type      %-42s référence=%s  bac=%s" % (
                    champ, "/".join(tr), "/".join(tb)))
                continue
            for a, b in zip(cr[champ], cb[champ]):
                oa, ob = _options(a), _options(b)
                if oa is None or oa == ob:
                    continue
                manquantes = sorted(set(oa) - set(ob))
                surnumeraires = sorted(set(ob) - set(oa))
                detail = []
                if manquantes:
                    detail.append("absentes du bac : " + ", ".join(manquantes))
                if surnumeraires:
                    detail.append("en trop : " + ", ".join(surnumeraires))
                lignes.append("   options   %-42s %s" % (champ, " | ".join(detail)))

        if lignes:
            print("❌ %s — %d écart(s)" % (nom, len(lignes)))
            for ligne in lignes:
                print(ligne)
            ecarts += len(lignes)
        else:
            print("✅ %s — %d champs, identiques" % (nom, len(ref[nom]["fields"])))

    hors = sorted(set(ref) - set(TABLES_UTILES))
    if hors:
        print()
        print("Hors périmètre, non comparées (%d) : %s" % (len(hors), ", ".join(hors)))
        print("Ce ne sont pas des tables oubliées, ce sont des vestiges qu'aucun code ne touche.")

    print()
    print("→ %d écart(s)" % ecarts if ecarts else "→ aucun écart sur le périmètre utile")
    return 1 if ecarts else 0


# --------------------------------------------------------------------------
# verifier — aucune adresse réelle
# --------------------------------------------------------------------------

def _adresses(fiche):
    """Toutes les adresses d'une fiche, « Mail optionnel » découpé.

    Ce champ peut contenir plusieurs adresses séparées par des virgules : 7
    fiches, 111 adresses secondaires en production. Un contrôle qui ne
    découperait pas raterait des cas en silence — c'est arrivé le 27/08 dans une
    qualification manuelle.
    """
    brut = []
    for champ in ("E-mail", "Mail optionnel", "Ancien courriel"):
        valeur = fiche.get(champ)
        if isinstance(valeur, str):
            brut += re.split(r"[,;]", valeur)
    return [a.strip().lower() for a in brut if a.strip()]


def verifier(at, cible, reference=None):
    """Le bac à sable ne peut-il atteindre personne ?

    Le contrôle porte sur le domaine, pas sur une liste de personnes connues :
    une adresse à un domaine réservé RFC 2606 n'a pas de MX et ne peut pas être
    délivrée, quelle que soit l'identité qu'elle porte. C'est une propriété du
    DNS, pas une convention d'équipe.
    """
    schema = {t["name"]: t for t in at.schema(cible)}
    if "Annuaire" not in schema:
        sys.exit("La base %s n'a pas de table « Annuaire »." % cible)

    fiches = at.enregistrements(cible, schema["Annuaire"]["id"])
    suspectes, total = [], 0
    for fiche in fiches:
        for adresse in _adresses(fiche["fields"]):
            total += 1
            if not adresse.endswith(DOMAINES_FICTIFS):
                suspectes.append(adresse)

    print("bac à sable %s — Annuaire : %d fiche(s), %d adresse(s)" % (cible, len(fiches), total))
    if not suspectes:
        print("✅ toutes les adresses sont à un domaine réservé (%s)" % ", ".join(DOMAINES_FICTIFS))
        print("   Aucune ne peut être délivrée : ces domaines n'ont pas de MX.")
        return 0

    print("❌ %d adresse(s) à un domaine réel — ce ne sont pas des données fictives" % len(suspectes))
    for adresse in suspectes[:5]:
        prenom, _, domaine = adresse.partition("@")
        print("   %s…@%s" % (prenom[:2], domaine))
    if len(suspectes) > 5:
        print("   (+%d autres)" % (len(suspectes) - 5))

    if reference:
        ref_schema = {t["name"]: t for t in at.schema(reference)}
        reelles = set()
        for fiche in at.enregistrements(reference, ref_schema["Annuaire"]["id"]):
            reelles.update(_adresses(fiche["fields"]))
        communes = {a for a in suspectes if a in reelles}
        print("   dont %d présente(s) à l'identique en production : ce sont les mêmes personnes."
              % len(communes))
    return 1


# --------------------------------------------------------------------------
# peupler — des adhérents fictifs
# --------------------------------------------------------------------------

PRENOMS = [
    "Amandine", "Bastien", "Carine", "Damien", "Élodie", "Fabien", "Gaëlle",
    "Hakim", "Inès", "Jocelyn", "Katia", "Loïc", "Maëlle", "Nadir", "Ophélie",
    "Pascal", "Quentin", "Rachida", "Sylvain", "Tiphaine", "Ulysse", "Valérie",
    "Wassim", "Xavier", "Yasmine", "Zoé",
]

# Noms construits sur des toponymes et des mots communs, pour rester plausibles
# sans désigner personne.
NOMS = [
    "Bellecombe", "Chanteloup", "Duvivier", "Ferrandin", "Grandclos", "Hauterive",
    "Joncquière", "Lavaudieu", "Malbosc", "Noirefeuille", "Ourseval", "Peyrelade",
    "Quintenac", "Rochebrune", "Sauvestre", "Tourvieille", "Vaubourg", "Yvernaux",
]

STRUCTURES = [
    "Coopérative du Pont Vieux", "Tiers-lieu La Fabrique Ordinaire",
    "Association Terres Communes", "SCIC Rivages", "Fondation Sablières",
    "Collectif Aire Ouverte", "Institut des Usages", "Régie de Quartier Bellevue",
]

GROUPES = [
    "Adhérent·es la Coop des Communs",  # nom réel : le code le cherche par nom
    "GT Bac à sable",
    "GT Répétition",
]


def _sans_accent(texte):
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _options_du_champ(table, nom):
    for champ in table["fields"]:
        if champ["name"] == nom and champ["type"] in ("singleSelect", "multipleSelects"):
            return [o["name"] for o in champ.get("options", {}).get("choices", [])]
    return []


def _index_par_nom(champs_table):
    return {c["name"]: c for c in champs_table["fields"]}


def peupler(at, cible, nombre, cotisation, appliquer, graine):
    """Fabrique un annuaire fictif cohérent : groupes, structures, adhérents.

    Les valeurs de listes déroulantes sont tirées **des options de la base
    cible**, jamais écrites en dur : une valeur inventée ferait échouer
    l'écriture, et surtout le jeu de test cesserait d'être représentatif dès que
    la production renomme une option.
    """
    hasard = random.Random(graine)
    schema = {t["name"]: t for t in at.schema(cible)}
    for requise in ("Annuaire", "Liste des groupes", "Structures"):
        if requise not in schema:
            sys.exit("La base %s n'a pas de table « %s » : dupliquer d'abord la base de "
                     "production sans les enregistrements." % (cible, requise))

    annuaire = schema["Annuaire"]
    champs = _index_par_nom(annuaire)
    genres = _options_du_champ(annuaire, "Genre") or ["Non-précisé"]

    # Identités uniques : le couple prénom/nom sert à fabriquer l'adresse, donc
    # une collision produirait deux fiches à la même adresse et fausserait tout
    # test de rapprochement.
    couples = [(p, n) for p in PRENOMS for n in NOMS]
    hasard.shuffle(couples)
    if nombre > len(couples):
        sys.exit("Maximum %d identités distinctes." % len(couples))
    couples = couples[:nombre]

    adherents = []
    for prenom, nom in couples:
        adresse = "%s.%s@example.org" % (
            _sans_accent(prenom).lower(), _sans_accent(nom).lower())
        fiche = {"E-mail": adresse, "Prénom": prenom, "Nom": nom.upper()}
        if "Genre" in champs:
            fiche["Genre"] = hasard.choice(genres)
        if "code postal" in champs:
            fiche["code postal"] = "%05d" % hasard.randrange(1000, 96000)
        if "Cotisation LCDC" in champs:
            fiche["Cotisation LCDC"] = cotisation
        adherents.append(fiche)

    print("bac à sable : %s" % cible)
    print("à créer : %d groupe(s), %d structure(s), %d adhérent(s) « %s »"
          % (len(GROUPES), len(STRUCTURES), len(adherents), cotisation))
    print("adresses en @example.org — domaine réservé RFC 2606, sans MX")
    print()

    if not appliquer:
        for fiche in adherents[:5]:
            print("   %s %s  <%s>  %s" % (fiche["Prénom"], fiche["Nom"], fiche["E-mail"],
                                          fiche.get("Genre", "")))
        if len(adherents) > 5:
            print("   (+%d autres)" % (len(adherents) - 5))
        print()
        print("Simulation. Rien n'est écrit. Relancer avec --appliquer.")
        return 0

    groupes = at.creer(cible, schema["Liste des groupes"]["id"],
                       [{"Nom": g, "Label": g} for g in GROUPES])
    print("✅ %d groupe(s)" % len(groupes))

    structures = at.creer(cible, schema["Structures"]["id"],
                          [{"Name": s} for s in STRUCTURES])
    print("✅ %d structure(s)" % len(structures))

    groupe_adherents = groupes[0]["id"]
    for fiche in adherents:
        if "Groupe(s)" in champs and champs["Groupe(s)"]["type"] == "multipleRecordLinks":
            fiche["Groupe(s)"] = [groupe_adherents]
        if "Structure(s)" in champs and champs["Structure(s)"]["type"] == "multipleRecordLinks":
            if hasard.random() < 0.6:
                fiche["Structure(s)"] = [hasard.choice(structures)["id"]]

    crees = at.creer(cible, annuaire["id"], adherents)
    print("✅ %d adhérent(s)" % len(crees))
    print()
    print("Contrôle : bac_a_sable.py verifier --base %s" % cible)
    return 0


# --------------------------------------------------------------------------

def main():
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["comparer", "verifier", "peupler"])
    p.add_argument("--base", help="identifiant du bac à sable (défaut : AIRTABLE_BASE_ID_BAC_A_SABLE)")
    p.add_argument("--reference", help="base de référence (défaut : AIRTABLE_BASE_ID_PROD)")
    p.add_argument("--nombre", type=int, default=40, help="adhérents fictifs à créer (défaut 40)")
    p.add_argument("--cotisation", default="Payé 2026", help="valeur de Cotisation LCDC")
    p.add_argument("--graine", type=int, default=27082026, help="graine du tirage, pour un jeu reproductible")
    p.add_argument("--appliquer", action="store_true", help="écrire vraiment (défaut : simulation)")
    p.add_argument("--croiser-prod", action="store_true",
                   help="verifier : dire aussi combien d'adresses suspectes sont en production")
    args = p.parse_args()

    cible = args.base or os.getenv("AIRTABLE_BASE_ID_BAC_A_SABLE")
    reference = args.reference or os.getenv("AIRTABLE_BASE_ID_PROD")
    jeton = os.getenv("AIRTABLE_TOKEN_SCHEMA") or os.getenv("AIRTABLE_API_KEY_PROD")

    if not cible:
        sys.exit("Bac à sable non désigné : --base appXXXX, ou AIRTABLE_BASE_ID_BAC_A_SABLE "
                 "dans le .env.")
    if not jeton:
        sys.exit("Aucun jeton Airtable dans le .env.")

    # La ceinture. Le même raisonnement que le garde-fou d'envoi : une consigne
    # « ne pas se tromper de base » ne tient pas, un refus si. Ce script écrit
    # des données fictives et ne doit jamais pouvoir les écrire en production.
    if reference and cible == reference:
        sys.exit("REFUS : la base désignée (%s) est la base de PRODUCTION.\n"
                 "Le bac à sable est forcément une autre base." % cible)

    at = Airtable(jeton)
    if args.action == "comparer":
        if not reference:
            sys.exit("Aucune référence : --reference appXXXX, ou AIRTABLE_BASE_ID_PROD.")
        return comparer(at, reference, cible)
    if args.action == "verifier":
        return verifier(at, cible, reference if args.croiser_prod else None)
    return peupler(at, cible, args.nombre, args.cotisation, args.appliquer, args.graine)


if __name__ == "__main__":
    sys.exit(main())
