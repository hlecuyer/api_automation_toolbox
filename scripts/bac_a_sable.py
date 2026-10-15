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

    comparer    dérive entre la base de référence (production) et le bac à sable
    verifier    aucune adresse du bac à sable ne peut atteindre une vraie personne
    peupler     génère des adhérents fictifs, des groupes et des structures
    formulaire  les questions d'un formulaire HelloAsso rencontrent-elles le code
    ovh         la liste de diffusion de test, et la clé qui la vise

Usage :
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py comparer --base appXXXX
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py verifier --base appXXXX
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py peupler  --base appXXXX --nombre 40
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py peupler  --base appXXXX --appliquer
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py formulaire --formulaire "Bac à sable — adhésion"
    PYTHONPATH=. .venv/bin/python scripts/bac_a_sable.py ovh --appliquer

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
    "Mise à jour fiche",
    "Centres d'intérêt",
]

# Écarts assumés entre la référence et le bac à sable, par (table, champ).
# Nommés à chaque passage, ils ne font plus sortir `comparer` en rouge :
# un écart tu n'est pas un écart connu, celui-ci l'est.
ECARTS_CONNUS = {
    ("Mise à jour fiche", "Avez-vous une autre adresse e-mail ?"):
        "question retirée du formulaire le 28/08, champ laissé dans le bac à sable (Hugo, 15/10)",
}

# Domaines réservés par l'IANA (RFC 2606) : ils n'ont pas d'enregistrement MX et
# ne peuvent structurellement pas recevoir de courrier. C'est ce qui fait de la
# vérification d'adresses un contrôle et non une convention.
DOMAINES_FICTIFS = ("example.org", "example.com", "example.net", "example.edu")

# L'exception déclarée, et c'est une brèche assumée dans l'invariant ci-dessus.
#
# Prouver qu'un mail de bienvenue **arrive** demande une adresse capable de
# recevoir, ce qu'aucun domaine réservé ne peut être. Une adresse de contrôle
# appartenant à l'équipe est donc admise — à trois conditions, et elles portent
# tout le raisonnement :
#
# 1. **Déclarée**, jamais devinée : par `ADRESSES_DE_CONTROLE` ou par
#    `--adresse-de-controle`. Rien d'implicite.
# 2. **Nominative**, jamais un motif. `*@dsi.coop` rouvrirait l'invariant à un
#    domaine entier, et la première adresse d'adhérent qui y atterrirait
#    passerait inaperçue. Un motif est refusé, bruyamment.
# 3. **Dite à chaque passage.** Le contrôle ne se tait pas parce qu'une
#    exception existe : il la compte et la nomme. Une brèche silencieuse cesse
#    d'être une brèche pour devenir un trou.
VARIABLE_ADRESSES_DE_CONTROLE = "ADRESSES_DE_CONTROLE"


def adresses_de_controle(declarees=None):
    """Les adresses de contrôle déclarées, motifs écartés."""
    brut = list(declarees or [])
    if not brut:
        brut = (os.getenv(VARIABLE_ADRESSES_DE_CONTROLE) or "").replace(";", ",").split(",")

    retenues = set()
    for morceau in brut:
        adresse = (morceau or "").strip().lower()
        if not adresse:
            continue
        if "*" in adresse or "@" not in adresse:
            print("⚠  adresse de contrôle « %s » ignorée : il faut une adresse nominative, "
                  "pas un motif." % adresse, file=sys.stderr)
            continue
        retenues.add(adresse)
    return retenues


def _hors_bac_a_sable(adresses, controle):
    """Les adresses qui peuvent atteindre quelqu'un et qui ne sont pas déclarées."""
    return [a for a in adresses
            if not a.strip().lower().endswith(DOMAINES_FICTIFS)
            and a.strip().lower() not in controle]


def _dire_les_exceptions(adresses, controle):
    """Nommer les adresses de contrôle rencontrées. Une brèche qui se voit."""
    vues = sorted({a.strip().lower() for a in adresses if a.strip().lower() in controle})
    if vues:
        print("   ⚠  %d adresse(s) de contrôle déclarée(s), qui peuvent recevoir : %s"
              % (len(vues), ", ".join(vues)))
        print("      L'invariant « aucune adresse réelle » est ouvert pour celles-là,")
        print("      et pour elles seules. À retirer quand la démonstration est faite.")
    return len(vues)


# Nombre d'adresses citées dans un constat d'anomalie. En recracher 1400 rendrait
# le message illisible, donc non lu — et un contrôle qu'on ne lit pas ne contrôle
# rien.
ADRESSES_CITEES = 5

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
    declares = 0
    declares_vus = set()

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
        trouves = []  # (champ, ligne) : le champ décide du sort de la ligne

        for champ in sorted(set(cr) - set(cb)):
            types = ", ".join(c["type"] for c in cr[champ])
            main = "  ⚠ à poser à la main" if any(
                c["type"] in TYPES_NON_CREABLES for c in cr[champ]) else ""
            trouves.append((champ, "   manquant  %-42s %s%s" % (champ, types, main)))

        for champ in sorted(set(cb) - set(cr)):
            trouves.append((champ, "   en trop   %-42s %s" % (
                champ, ", ".join(c["type"] for c in cb[champ]))))

        for champ in sorted(set(cr) & set(cb)):
            tr = sorted(c["type"] for c in cr[champ])
            tb = sorted(c["type"] for c in cb[champ])
            if tr != tb:
                trouves.append((champ, "   type      %-42s référence=%s  bac=%s" % (
                    champ, "/".join(tr), "/".join(tb))))
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
                trouves.append((champ, "   options   %-42s %s" % (champ, " | ".join(detail))))

        nouveaux = [(c, l) for c, l in trouves if (nom, c) not in ECARTS_CONNUS]
        announces = [(c, l) for c, l in trouves if (nom, c) in ECARTS_CONNUS]

        if nouveaux:
            print("❌ %s — %d écart(s)" % (nom, len(nouveaux)))
            for _, ligne in nouveaux:
                print(ligne)
        elif announces:
            print("✅ %s — identique, hors écarts déclarés" % nom)
        else:
            print("✅ %s — %d champs, identiques" % (nom, len(ref[nom]["fields"])))
        for champ, _ in announces:
            print("   déclaré  %-42s %s" % (champ, ECARTS_CONNUS[(nom, champ)]))

        ecarts += len(nouveaux)
        declares += len(announces)
        declares_vus.update((nom, c) for c, _ in announces)

    for cle in sorted(set(ECARTS_CONNUS) - declares_vus):
        print("⚠  écart déclaré sans effet, à retirer de ECARTS_CONNUS : %s / %s" % cle)

    hors = sorted(set(ref) - set(TABLES_UTILES))
    if hors:
        print()
        print("Hors périmètre, non comparées (%d) : %s" % (len(hors), ", ".join(hors)))
        print("Ce ne sont pas des tables oubliées, ce sont des vestiges qu'aucun code ne touche.")

    print()
    if ecarts:
        suite = " (+ %d déclaré(s))" % declares if declares else ""
        print("→ %d nouvel(s) écart(s)%s" % (ecarts, suite))
        return 1
    if declares:
        print("→ aucun écart à signaler (%d déclaré(s))" % declares)
        return 0
    print("→ aucun écart sur le périmètre utile")
    return 0


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


def verifier(at, cible, reference=None, controle=()):
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
    toutes = []
    for fiche in fiches:
        toutes += _adresses(fiche["fields"])
    suspectes = _hors_bac_a_sable(toutes, controle)

    print("bac à sable %s — Annuaire : %d fiche(s), %d adresse(s)"
          % (cible, len(fiches), len(toutes)))
    _dire_les_exceptions(toutes, controle)
    if not suspectes:
        print("✅ toutes les adresses sont à un domaine réservé (%s)" % ", ".join(DOMAINES_FICTIFS))
        print("   Aucune ne peut être délivrée : ces domaines n'ont pas de MX.")
        return 0

    print("❌ %d adresse(s) à un domaine réel — ce ne sont pas des données fictives" % len(suspectes))
    for adresse in suspectes[:ADRESSES_CITEES]:
        prenom, _, domaine = adresse.partition("@")
        print("   %s…@%s" % (prenom[:2], domaine))
    if len(suspectes) > ADRESSES_CITEES:
        print("   (+%d autres)" % (len(suspectes) - ADRESSES_CITEES))

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

# `Nom` et `Label` ne servent pas à la même chose, et c'est ce qui protège la
# production ici.
#
# `hello_asso_sync` rattache l'adhérent au groupe par son **nom** : le premier
# doit donc porter le nom réel, sinon le rattachement ne se rejoue pas.
# `mailinglist_extracter`, lui, prend le **label** comme nom de liste OVH et
# aligne cette liste sur Airtable — en supprimant tout abonné absent d'Airtable.
#
# Un label de bac à sable qui coïnciderait avec une vraie liste OVH ferait donc
# vider cette liste au profit d'adresses fictives. Le préfixe rend la collision
# impossible par construction, au lieu de la rendre improbable.
#
# Label vide = groupe ignoré par l'extracteur : les deux GT de décor n'ont pas
# de liste OVH et n'en réclameront pas.
GROUPES = [
    {"Nom": "Adhérent·es la Coop des Communs", "Label": "bac-a-sable"},
    {"Nom": "GT Bac à sable"},
    {"Nom": "GT Répétition"},
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
    print("liste OVH visée par l'extracteur : %s (label du premier groupe)"
          % GROUPES[0]["Label"])
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

    groupes = at.creer(cible, schema["Liste des groupes"]["id"], [dict(g) for g in GROUPES])
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
# ovh — la liste de test, et surtout la clé qui la vise
# --------------------------------------------------------------------------

# Une opération sur une mailing list OVH n'est pas appliquée par l'appel : elle
# est **mise en file comme une tâche**. Le POST rend un objet
# `{"action": "mailinglist/addSubscriber", "id": …}` et l'abonné apparaît plus
# tard, parfois bien plus tard.
#
# Ça se vérifie ici, et ça éclaire un défaut traîné depuis des mois : la
# suppression sur la liste de production « ne fonctionne pas ». Elle n'échoue
# pas — elle est acceptée puis mise en file, et c'est l'application qui manque.
# Un contrôle qui conclurait à l'échec après quelques secondes se tromperait de
# diagnostic et ferait chercher au mauvais endroit.
#
# D'où la règle retenue : **l'acceptation prouve le droit d'écrire, l'arrivée
# effective se constate à un passage ultérieur.** Une non-arrivée n'est pas
# comptée comme un écart, elle est dite.
RELECTURES = 5
ATTENTE = 3.0


def _confinee(chemin, domaine, liste):
    """La règle d'accès ne porte-t-elle que sur cette liste ?

    Comparaison sur le préfixe **suivi d'un slash**, sinon une règle visant
    « bac-a-sable-autre » passerait pour une règle visant « bac-a-sable ».
    """
    prefixe = "/email/domain/%s/mailingList/%s" % (domaine, liste)
    return chemin == prefixe or chemin.startswith(prefixe + "/")


def _abonnes(client, domaine, liste):
    return client.get("/email/domain/%s/mailingList/%s/subscriber" % (domaine, liste))


def _attendre(client, domaine, liste, adresse, presente):
    """Attend que l'adresse soit là — ou n'y soit plus. Rend l'état atteint."""
    import time
    for _ in range(RELECTURES):
        actuels = {a.lower() for a in _abonnes(client, domaine, liste)}
        if (adresse.lower() in actuels) == presente:
            return True
        time.sleep(ATTENTE)
    return False


def verifier_ovh(client, mailing_client, domaine, liste, liste_production, appliquer,
                 controle=()):
    """La liste de test est-elle utilisable, et la clé est-elle une ceinture ?

    L'ordre des contrôles n'est pas indifférent. Les **droits de la clé** passent
    en premier parce que c'est le seul contrôle qui porte sur une garantie et non
    sur un état : une liste peut être saine aujourd'hui et polluée demain, tandis
    qu'une clé confinée rend l'accident impossible tant qu'elle n'est pas
    remplacée. Le 27/08/2026, la clé du bac à sable était celle de la production,
    autorisée sur la seule liste des adhérents réels : rien dans la configuration
    ne le disait, et rien ne l'aurait dit.
    """
    ecarts = 0
    print("domaine    : %s" % domaine)
    print("liste visée: %s" % liste)
    print()

    # 1. Les droits de la clé.
    print("1. Droits de la clé")
    try:
        cred = client.get("/auth/currentCredential")
    except Exception as e:
        print("   ❌ impossible de lire les droits : %s" % str(e)[:120])
        return 1
    regles = cred.get("rules", [])
    if not regles:
        print("   ❌ aucune règle d'accès lisible")
        ecarts += 1
    for r in regles:
        if _confinee(r["path"], domaine, liste):
            print("   ✅ %-7s %s" % (r["method"], r["path"]))
        else:
            print("   ❌ %-7s %s" % (r["method"], r["path"]))
            print("      cette règle déborde de « %s » : la clé peut atteindre autre chose "
                  "que le bac à sable." % liste)
            ecarts += 1
    if liste_production and liste == liste_production:
        print("   ❌ la liste visée EST celle de production")
        ecarts += 1
    if ecarts:
        print()
        print("→ la ceinture n'en est pas une, on s'arrête là.")
        return 1

    # 2. La liste existe.
    print()
    print("2. La liste")
    try:
        abonnes = _abonnes(client, domaine, liste)
    except Exception as e:
        print("   ❌ %s : %s" % (type(e).__name__, str(e)[:120]))
        print("      (l'énumération /mailingList n'est jamais autorisée : on interroge")
        print("       toujours une liste par son nom)")
        return 1
    print("   ✅ existe — %d abonné(s)" % len(abonnes))

    # 3. Hygiène des adresses, même invariant que pour Airtable.
    print()
    print("3. Adresses")
    _dire_les_exceptions(abonnes, controle)
    reelles = _hors_bac_a_sable(abonnes, controle)
    if reelles:
        print("   ❌ %d adresse(s) à un domaine réel" % len(reelles))
        for a in reelles[:ADRESSES_CITEES]:
            debut, _, dom = a.partition("@")
            print("      %s…@%s" % (debut[:2], dom))
        ecarts += 1
    else:
        print("   ✅ aucune adresse à un domaine réel")

    # 4. L'écriture, qui est la seule preuve qui compte.
    print()
    print("4. Écriture")
    if not appliquer:
        print("   simulation — relancer avec --appliquer pour prouver l'aller-retour")
        print()
        print("→ %d écart(s)" % ecarts if ecarts else "→ lecture conforme, écriture non prouvée")
        return 1 if ecarts else 0

    temoin = "temoin-bac-a-sable@example.org"
    present = temoin.lower() in {a.lower() for a in abonnes}

    if present:
        print("   ·  le témoin d'un passage précédent est arrivé : l'ajout s'applique bien")
    else:
        # add_subscriber est exactement ce qu'appelle hello_asso_sync : la preuve
        # passe par le chemin de production, pas par un appel écrit pour l'occasion.
        if not mailing_client.add_subscriber(temoin):
            print("   ❌ abonnement refusé (détail en syslog)")
            print()
            print("→ %d écart(s)" % (ecarts + 1))
            return 1
        print("   ✅ abonnement accepté — le droit d'écrire est prouvé")
        present = _attendre(client, domaine, liste, temoin, presente=True)
        if not present:
            print("   ⏳ pas encore appliqué après %d s : OVH traite l'opération en tâche"
                  % int(RELECTURES * ATTENTE))
            print("      de fond. Ce n'est pas un échec. Relancer cette commande plus tard :")
            print("      le témoin doit y être, et il sera retiré à ce moment-là.")
            print()
            print("→ %d écart(s)" % ecarts if ecarts
                  else "→ droits et lecture conformes, application en attente")
            return 1 if ecarts else 0

    try:
        client.delete("/email/domain/%s/mailingList/%s/subscriber/%s" % (domaine, liste, temoin))
    except Exception as e:
        print("   ❌ suppression refusée : %s" % str(e)[:110])
        ecarts += 1
    else:
        print("   ✅ suppression acceptée")
        if _attendre(client, domaine, liste, temoin, presente=False):
            print("   ✅ appliquée : la liste est rendue dans l'état trouvé")
        else:
            print("   ⏳ acceptée, pas encore appliquée après %d s."
                  % int(RELECTURES * ATTENTE))
            print("      À surveiller : c'est la forme exacte du défaut de suppression")
            print("      constaté sur la liste de production. Il se diagnostique enfin ici,")
            print("      sans toucher à 144 personnes réelles.")

    print()
    print("→ %d écart(s)" % ecarts if ecarts else "→ la liste de test est utilisable")
    return 1 if ecarts else 0


# --------------------------------------------------------------------------
# formulaire — les questions rencontrent-elles le code
# --------------------------------------------------------------------------

def _questions(client, titre):
    """Libellés des questions d'un formulaire, dans l'ordre où il les pose."""
    details = client.get_form_details(titre)
    if not details:
        sys.exit("Formulaire « %s » introuvable dans l'organisation." % titre)
    public = client.get_public_form(details["formType"], details["formSlug"])
    labels, vus = [], set()
    for tarif in public.get("tiers", []):
        for champ in tarif.get("customFields", []):
            if champ["label"] not in vus:
                vus.add(champ["label"])
                labels.append((champ["label"], champ.get("type", "")))
    return details, labels


def formulaire(client, titre_reference, titre_test):
    """Vérifie qu'un formulaire pose les questions que le code sait lire.

    Un libellé qui diffère d'un caractère ne lève rien : la réponse est ignorée
    et la colonne Airtable reste vide pour toujours. C'est le mode de défaillance
    le plus coûteux de cette chaîne, parce qu'il est parfaitement silencieux —
    il a fait perdre le consentement de 84 adhérents pendant toute l'année 2026.
    """
    from src.models.user_subscription import CHAMPS_HELLOASSO_VERS_AIRTABLE as contrat
    from src.models.user_subscription import _cle

    ecarts = 0
    details_ref, ref = _questions(client, titre_reference)
    print("référence : « %s »  (%s/%s), %d question(s)"
          % (titre_reference, details_ref["formType"], details_ref["formSlug"], len(ref)))
    labels_ref = {l for l, _ in ref}
    # Le code rogne les libellés à l'entrée : une espace en trop ne change plus
    # rien. La comparaison doit donc l'ignorer aussi, sinon elle signalerait un
    # défaut là où le code n'en a plus.
    cles_ref = {_cle(l) for l in labels_ref}

    labels_test = None
    if titre_test:
        details_test, test = _questions(client, titre_test)
        print("test      : « %s »  (%s/%s), %d question(s)"
              % (titre_test, details_test["formType"], details_test["formSlug"], len(test)))
        labels_test = {l for l, _ in test}
        cles_test = {_cle(l) for l in labels_test}
    print()

    print("Contrat de mappage — les %d libellés que le code sait lire :" % len(contrat))
    for libelle, colonne in contrat.items():
        dans_ref = _cle(libelle) in cles_ref
        dans_test = labels_test is None or _cle(libelle) in cles_test
        if dans_ref and dans_test:
            print("   ✅ %-30s ← %r" % (colonne, libelle))
            continue
        ecarts += 1
        manque = []
        if not dans_ref:
            manque.append("de la RÉFÉRENCE")
        if not dans_test:
            manque.append("du formulaire de TEST")
        print("   ❌ %-30s ← %r" % (colonne, libelle))
        print("      absent %s" % " et ".join(manque))
        if not dans_ref:
            proches = [l for l in labels_ref
                       if l.strip().lower().startswith(_cle(libelle).lower()[:12])
                       or _cle(libelle).lower()[:12] in l.strip().lower()]
            for p in proches:
                print("      candidat publié : %r" % p)
            if not proches:
                print("      aucune question publiée n'y ressemble : la colonne « %s »"
                      " ne sera jamais remplie depuis HelloAsso." % colonne)

    if labels_test is not None:
        print()
        for cle in sorted(cles_ref - cles_test):
            print("   ⚠  posée en référence, absente du test : %r"
                  % next(l for l in labels_ref if _cle(l) == cle))
        for cle in sorted(cles_test - cles_ref):
            print("   ·  posée dans le test seulement : %r"
                  % next(l for l in labels_test if _cle(l) == cle))
        # Différences d'espaces seules : sans effet depuis que le code rogne, mais
        # dites quand même — c'est la trace d'une recopie, et la prochaine pourrait
        # porter sur autre chose qu'une espace.
        for libelle in sorted(labels_ref - labels_test):
            jumeau = next((l for l in labels_test if _cle(l) == _cle(libelle)), None)
            if jumeau is not None:
                print("   ·  même question, espaces différentes (sans effet) :")
                print("        référence %r" % libelle)
                print("        test      %r" % jumeau)

    print()
    print("→ %d écart(s) sur le contrat" % ecarts if ecarts
          else "→ le contrat de mappage est honoré de bout en bout")
    return 1 if ecarts else 0


# --------------------------------------------------------------------------

def _conf_locale(chemin):
    """Section `conf` du config JSON local, si présent. Jamais de valeur client en dur."""
    if not os.path.exists(chemin):
        return {}
    import json
    with open(chemin, encoding="utf-8") as f:
        return json.load(f).get("conf", {})


def _ovh_depuis_args(args):
    """Monte le client OVH du bac à sable.

    Les identifiants dédiés priment. À défaut, on retombe sur les identifiants
    généraux **en le disant** : le premier contrôle refusera, et son message
    expliquera pourquoi mieux qu'un refus ici. Une ceinture qu'on voit se
    déclencher enseigne davantage qu'une ceinture qui empêche de partir.
    """
    import ovh as ovh_api

    conf = _conf_locale(args.config)
    liste_prod = conf.get("ovh", {}).get("mailing_list", {}).get("name")
    domaine = (args.domaine or os.getenv("OVH_MAILING_LIST_DOMAIN")
               or conf.get("ovh", {}).get("mailing_list", {}).get("domain"))
    liste = args.liste or os.getenv("OVH_MAILING_LIST_BAC_A_SABLE") or "bac-a-sable"
    if not domaine:
        sys.exit("Domaine inconnu : --domaine, OVH_MAILING_LIST_DOMAIN, ou le config JSON.")

    dedies = {suffixe: os.getenv("OVH_%s_BAC_A_SABLE" % suffixe)
              for suffixe in ("APP_KEY", "APP_SECRET", "CONSUMER_KEY")}
    if all(dedies.values()):
        cles = dedies
    else:
        cles = {s: os.getenv("OVH_" + s) for s in ("APP_KEY", "APP_SECRET", "CONSUMER_KEY")}
        if not all(cles.values()):
            sys.exit("Aucun identifiant OVH dans le .env. Créer une clé restreinte à « %s » "
                     "sur https://eu.api.ovh.com/createToken/ et la poser dans "
                     "OVH_APP_KEY_BAC_A_SABLE / OVH_APP_SECRET_BAC_A_SABLE / "
                     "OVH_CONSUMER_KEY_BAC_A_SABLE." % liste)
        print("⚠  Pas d'identifiants dédiés au bac à sable (OVH_*_BAC_A_SABLE) :")
        print("   on essaie avec les identifiants généraux, qui sont ceux de la production.")
        print()

    point = os.getenv("OVH_ENDPOINT", "ovh-eu")
    client = ovh_api.Client(endpoint=point,
                            application_key=cles["APP_KEY"],
                            application_secret=cles["APP_SECRET"],
                            consumer_key=cles["CONSUMER_KEY"])

    from src.clients.ovh_client import OVHMailingClient
    mailing = OVHMailingClient(
        application_key=cles["APP_KEY"], application_secret=cles["APP_SECRET"],
        consumer_key=cles["CONSUMER_KEY"], domain=domaine,
        mailing_list_name=liste, endpoint=point)

    return verifier_ovh(client, mailing, domaine, liste, liste_prod, args.appliquer,
                        adresses_de_controle(args.adresse_de_controle))


def _formulaire_depuis_args(args):
    """Monte le client HelloAsso depuis la configuration locale.

    Ni l'organisation ni le titre du formulaire ne sont écrits en dur : ce dépôt
    est public, et ces valeurs désignent un client.
    """
    from src.clients.hello_asso_client import HelloAssoClient

    conf = {}
    if os.path.exists(args.config):
        import json
        with open(args.config, encoding="utf-8") as f:
            conf = json.load(f).get("conf", {}).get("helloAsso", {})

    organisation = os.getenv("HELLOASSO_ORGANIZATION") or conf.get("organization_name")
    reference = (args.formulaire_reference or os.getenv("HELLOASSO_FORM_REFERENCE")
                 or conf.get("form_name"))
    if not organisation or not reference:
        sys.exit("Organisation ou formulaire de référence inconnus : les poser dans %s, "
                 "ou via HELLOASSO_ORGANIZATION / HELLOASSO_FORM_REFERENCE." % args.config)
    if not (os.getenv("HELLOASSO_CLIENT_ID") and os.getenv("HELLOASSO_CLIENT_SECRET")):
        sys.exit("HELLOASSO_CLIENT_ID / HELLOASSO_CLIENT_SECRET absents du .env.")

    client = HelloAssoClient(
        api_url=os.getenv("HELLOASSO_API_URL") or conf.get("api_url", "https://api.helloasso.com"),
        organization_name=organisation,
        client_id=os.getenv("HELLOASSO_CLIENT_ID"),
        client_secret=os.getenv("HELLOASSO_CLIENT_SECRET"),
    )
    return formulaire(client, reference, args.formulaire)


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["comparer", "verifier", "peupler", "formulaire", "ovh"])
    p.add_argument("--base", help="identifiant du bac à sable (défaut : AIRTABLE_BASE_ID_BAC_A_SABLE)")
    p.add_argument("--reference", help="base de référence (défaut : AIRTABLE_BASE_ID_PROD)")
    p.add_argument("--nombre", type=int, default=40, help="adhérents fictifs à créer (défaut 40)")
    p.add_argument("--cotisation", default="Payé 2026", help="valeur de Cotisation LCDC")
    p.add_argument("--graine", type=int, default=27082026, help="graine du tirage, pour un jeu reproductible")
    p.add_argument("--appliquer", action="store_true", help="écrire vraiment (défaut : simulation)")
    p.add_argument("--formulaire", help="formulaire : titre du formulaire de test à vérifier")
    p.add_argument("--formulaire-reference",
                   help="formulaire : titre du formulaire de production (défaut : celui du "
                        "config JSON, ou HELLOASSO_FORM_REFERENCE)")
    p.add_argument("--config", default="config/hello-asso-automation-conf.json",
                   help="formulaire : config d'où lire organisation et formulaire de référence")
    p.add_argument("--liste", help="ovh : liste de diffusion de test (défaut : "
                                   "OVH_MAILING_LIST_BAC_A_SABLE, sinon bac-a-sable)")
    p.add_argument("--domaine", help="ovh : domaine de la liste (défaut : celui du config JSON)")
    p.add_argument("--adresse-de-controle", action="append", metavar="ADRESSE",
                   help="adresse nominative autorisée à recevoir dans le bac à sable "
                        "(défaut : ADRESSES_DE_CONTROLE). Répétable. Elle est nommée à "
                        "chaque passage : la brèche doit se voir.")
    p.add_argument("--croiser-prod", action="store_true",
                   help="verifier : dire aussi combien d'adresses suspectes sont en production")
    args = p.parse_args()

    if args.action == "formulaire":
        return _formulaire_depuis_args(args)
    if args.action == "ovh":
        return _ovh_depuis_args(args)

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
        return verifier(at, cible, reference if args.croiser_prod else None,
                        adresses_de_controle(args.adresse_de_controle))
    return peupler(at, cible, args.nombre, args.cotisation, args.appliquer, args.graine)


if __name__ == "__main__":
    sys.exit(main())
