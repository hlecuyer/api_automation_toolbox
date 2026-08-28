#!/usr/bin/env python3
"""Le parcours d'adhésion, rejoué de bout en bout dans le bac à sable.

Une adhésion, rejouée à volonté, contrôlée **à chaque étape** plutôt qu'à la
fin : fiche créée dans l'Annuaire → rattachée au groupe → adresse abonnée à la
liste de diffusion → mail de bienvenue rendu. Un contrôle final unique dirait
« ça n'a pas marché » sans dire où, ce qui est à peu près la situation qu'on
essaie de quitter sur ce projet.

**Ce que ce script prouve, et ce qu'il ne prouve pas.** Il rejoue la chaîne à
partir d'un item HelloAsso, donc tout sauf l'appel à HelloAsso lui-même. C'est
délibéré : c'est ce qui le rend rejouable dix fois par jour, sans remplir un
formulaire dans un navigateur. La chaîne complète, soumission réelle comprise,
se vérifie en capturant un item du formulaire de test et en le rejouant ici
avec `--item`.

⚠️ **L'item synthétique est construit sur les libellés que le code attend** —
les clés de `CHAMPS_HELLOASSO_VERS_AIRTABLE`. Il ne peut donc pas, par
construction, détecter un libellé de formulaire qui ne rencontre pas le code :
c'est le défaut qui a fait perdre 84 consentements en 2026. Ce défaut-là se
détecte avec `bac_a_sable.py formulaire`, et se rejoue ici avec `--item`.

**Le mail : rendu, pas livraison.** Prouver qu'un mail *arrive* demanderait une
adresse capable de recevoir, donc une exception aux deux invariants du bac à
sable (toute adresse à un domaine réservé RFC 2606, et la liste blanche du
garde-fou). On s'en tient au rendu, et on prouve en plus que **le garde-fou
refuse réellement l'envoi** — ce qui est le critère de recette du bac à sable :
« aucune adresse d'adhérent réel ne peut être jointe », à démontrer par un refus
constaté, pas par une intention.

**Les opérations OVH sont asynchrones.** Un `POST` d'abonnement rend une tâche ;
l'abonné arrive une à deux minutes plus tard. L'acceptation prouve le droit
d'écrire, l'arrivée effective se constate à un passage ultérieur. Une
non-arrivée est donc dite, jamais comptée comme un écart — sinon le script
mentirait à chaque exécution rapide.

Usage :

    PYTHONPATH=. .venv/bin/python scripts/parcours_bac_a_sable.py
    PYTHONPATH=. .venv/bin/python scripts/parcours_bac_a_sable.py --appliquer
    PYTHONPATH=. .venv/bin/python scripts/parcours_bac_a_sable.py --appliquer --garder
    PYTHONPATH=. .venv/bin/python scripts/parcours_bac_a_sable.py --appliquer \\
        --item scripts/data/2026-08-28-item-formulaire-test.json

Par défaut rien n'est écrit : les étapes qui lisent tournent, les autres
annoncent ce qu'elles feraient. C'est le même défaut que `bac_a_sable.py`, et
pour la même raison — le geste qui écrit doit être demandé.

Les cibles viennent du `.env` : `AIRTABLE_BASE_ID_BAC_A_SABLE`,
`OVH_MAILING_LIST_BAC_A_SABLE` (sinon `bac-a-sable`), `OVH_*_BAC_A_SABLE`. Le
comportement (champs liés, champs calculés, référentiels) vient du fichier de
configuration passé à `--config`, pour que la répétition ait le même
comportement que la production et pas seulement les mêmes cibles.
"""

import argparse
import copy
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from src import garde_fou_envoi
from src.reconciliation import (CHAMP_DATE_MAJ, CHAMP_FICHE, CHAMP_SYNCHRONISE,
                                 CORRESPONDANCE, Reconciliation,
                                 payload_depuis_reponse)
from src.hello_asso_sync import SyncHelloAsso
from src.models.user_subscription import (CHAMPS_BOOLEENS_AIRTABLE,
                                          CHAMPS_HELLOASSO_VERS_AIRTABLE)
from src.templates import welcome_email, signature

# `scripts/` n'est pas un paquet : on charge le module voisin par son chemin,
# comme le font ses propres tests. Ce qu'on lui emprunte est ce qui ne doit
# surtout pas exister en deux exemplaires — la liste des domaines sans MX, la
# règle de confinement d'une clé OVH, l'attente d'une tâche asynchrone. Une
# ceinture recopiée est une ceinture qui diverge.
_CHEMIN_BAC = Path(__file__).resolve().parent / "bac_a_sable.py"
_spec = importlib.util.spec_from_file_location("bac_a_sable", _CHEMIN_BAC)
bac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bac)


# Adresse du parcours. Horodatée, donc une exécution ne marche jamais sur les
# traces de la précédente : deux parcours simultanés, ou un ménage qui a échoué,
# ne se confondent pas. Le domaine est réservé RFC 2606, sans MX.
MODELE_ADRESSE = "parcours-%s@example.org"

# Adresse servant à prouver que la ceinture tient encore. Elle a la forme d'une
# adresse d'adhérent, au domaine réel de l'association : c'est la seule question
# qui compte, « peut-on joindre un adhérent depuis ici ? », et la réponse doit
# être non même quand une adresse de contrôle est déclarée.
ADRESSE_TEMOIN_REFUS = "adherent-temoin@coopdescommuns.org"

# Expéditeur du bac à sable. Le même raisonnement que pour les destinataires :
# un domaine réservé RFC 2606 ne peut ni émettre ni recevoir.
EXPEDITEUR_BAC_A_SABLE = "bac-a-sable@example.org"

PRENOM = "Prosper"
NOM = "Répétition"

# Réponses de l'item synthétique, par libellé de question. Les libellés sont les
# clés du mapping : ce qui est rejoué ici, c'est le contrat que le code déclare
# lire, pas le formulaire réel (voir l'avertissement en tête de module).
REPONSES = {
    "Structure": bac.STRUCTURES[0],
    "Fonction au sein de votre structure": "Fonction de répétition",
    "Intérêts (mot-clés)": "communs, répétition, bac à sable",
    "Localisation (code postal)": "75000",
    "Je souhaite que mon Nom et Prénom soient partagés sur le site web de "
    "l'association dans la liste des adhérent·es": "Oui",
    "Souhaitez-vous partager les informations précédentes avec les autres "
    "adhérent·es de la Coop des Communs ? Pour information, les champs suivants "
    "seront uniquement accessibles par l'équipe de gestion de l'association et "
    "les prestataires missionnés.": "Oui",
    "Si oui, pouvez-vous nous indiquer deux personnes connues au sein de "
    "l'association ?": "Deux personnes du bac à sable",
    "Est-ce votre première adhésion à la coop des communs ?": "Oui",
}

# Réponse servie pour une question mappée dont on n'a pas de valeur écrite
# ci-dessus : mieux vaut une valeur quelconque qu'un trou, car une valeur vide
# est écartée par `to_airtable_payload` et la colonne ne serait jamais exercée.
REPONSE_PAR_DEFAUT = "Répétition"


# --------------------------------------------------------------------------
# L'adhésion rejouée
# --------------------------------------------------------------------------

def _reponse(libelle, colonne, genres):
    if colonne in CHAMPS_BOOLEENS_AIRTABLE:
        # Une case à cocher se répète cochée : décochée, elle ne prouverait pas
        # que la conversion en booléen a lieu. C'est la colonne du consentement,
        # celle qui a fait échouer l'écriture entière avant le 28/08/2026.
        return "Oui"
    if libelle == "Genre":
        # Tirée des options de la base cible, jamais écrite en dur : le code
        # n'utilise pas `typecast`, donc une valeur hors options ferait échouer
        # l'écriture entière et l'adhésion serait perdue — mail de bienvenue
        # compris. Même règle que `bac_a_sable.py peupler`.
        return genres[0] if genres else "Non-précisé"
    return REPONSES.get(libelle, REPONSE_PAR_DEFAUT)


def item_synthetique(adresse, genres, quand=None):
    """Un item HelloAsso, dans la forme que `from_hello_asso_item` sait lire."""
    quand = quand or datetime.now()
    return {
        "payer": {"email": adresse},
        "user": {"firstName": PRENOM, "lastName": NOM},
        "order": {"date": quand.strftime("%Y-%m-%dT%H:%M:%S") + "+02:00"},
        "state": "Processed",
        "customFields": [
            {"name": libelle, "answer": _reponse(libelle, colonne, genres)}
            for libelle, colonne in CHAMPS_HELLOASSO_VERS_AIRTABLE.items()
        ],
    }


def item_depuis_fichier(chemin, adresse):
    """Un item réel capturé sur le formulaire de test, réadressé au parcours.

    L'adresse est **remplacée**, jamais conservée : un item capturé sur un vrai
    formulaire porte l'adresse de qui l'a rempli, et le bac à sable n'accepte
    aucune adresse capable de recevoir.
    """
    with open(chemin, encoding="utf-8") as f:
        item = json.load(f)
    item = copy.deepcopy(item)
    item.setdefault("payer", {})["email"] = adresse
    return item


def item_depuis_helloasso(conf, cibles, depuis=None, capture=None):
    """Va chercher chez HelloAsso l'adhésion qui vient d'être saisie à la main.

    C'est la seule variante qui prouve la chaîne **entière**, appel à HelloAsso
    compris, et surtout la seule qui prouve que les **libellés du formulaire
    rencontrent le code** : l'item synthétique, lui, est construit sur les
    libellés que le code déclare lire, donc il ne peut pas voir le défaut qui a
    fait perdre 84 consentements.

    En échange elle demande un geste manuel, et elle n'est donc pas celle qu'on
    lance dix fois par jour.
    """
    from src.clients.hello_asso_client import HelloAssoClient

    hello_asso = conf.get("helloAsso", {})
    organisation = os.getenv("HELLOASSO_ORGANIZATION") or hello_asso.get("organization_name")
    if not (os.getenv("HELLOASSO_CLIENT_ID") and os.getenv("HELLOASSO_CLIENT_SECRET")):
        sys.exit("HELLOASSO_CLIENT_ID / HELLOASSO_CLIENT_SECRET absents du .env.")

    client = HelloAssoClient(
        api_url=hello_asso.get("api_url", "https://api.helloasso.com"),
        organization_name=organisation,
        client_id=os.getenv("HELLOASSO_CLIENT_ID"),
        client_secret=os.getenv("HELLOASSO_CLIENT_SECRET"),
    )

    details = client.get_form_details(cibles["formulaire"])
    if not details:
        sys.exit("Formulaire « %s » introuvable chez HelloAsso. Le titre doit être exact, et "
                 "la campagne publiée — une campagne non publiée ne rend pas sa définition."
                 % cibles["formulaire"])

    # La ceinture vaut ici aussi : aller lire le formulaire de production
    # rejouerait de vraies adhésions dans le bac à sable, adresses comprises.
    if cibles["formulaire_production"] and \
            cibles["formulaire"] == cibles["formulaire_production"]:
        sys.exit("REFUS : « %s » est le formulaire de PRODUCTION. Le parcours complet ne se "
                 "joue que sur le formulaire de test." % cibles["formulaire"])

    items = client.get_form_items(details["formType"], details["formSlug"])
    if not items:
        sys.exit("Aucune adhésion sur « %s ». Remplir le formulaire, puis relancer."
                 % cibles["formulaire"])

    if depuis:
        items = [i for i in items
                 if (i.get("payer", {}).get("email") or "").lower() == depuis.lower()]
        if not items:
            sys.exit("Aucune adhésion payée par %s sur ce formulaire." % depuis)

    items.sort(key=lambda i: i.get("order", {}).get("date", ""), reverse=True)
    item = copy.deepcopy(items[0])

    paye_par = item.get("payer", {}).get("email", "")
    debut, _, domaine = paye_par.partition("@")
    print("   ·  %d adhésion(s) sur « %s », la plus récente retenue"
          % (len(items), cibles["formulaire"]))
    print("   ·  %s, payée par %s…@%s"
          % (item.get("order", {}).get("date", "date inconnue"), debut[:2], domaine))

    if capture:
        # L'adresse est remplacée **avant** l'écriture : un item capturé ne doit
        # jamais porter sur disque l'adresse de qui a rempli le formulaire.
        garde = copy.deepcopy(item)
        garde.setdefault("payer", {})["email"] = MODELE_ADRESSE % "capture"
        Path(capture).write_text(json.dumps(garde, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print("   ·  item capturé dans %s (adresse remplacée) — rejouable avec --item"
              % capture)

    item.setdefault("payer", {})["email"] = cibles["adresse"]
    return item


# --------------------------------------------------------------------------
# La ceinture
# --------------------------------------------------------------------------

def controler_cibles(cibles, client_ovh):
    """Aucune étape n'a lieu tant que la cible n'est pas prouvée être le bac à sable.

    L'ordre suit celui de `bac_a_sable.py ovh` et pour la même raison : les
    garanties portées par un **credential** passent avant celles portées par une
    **configuration**, parce que les premières tiennent quand quelqu'un se
    trompe de fichier.
    """
    ecarts = 0
    print("1. Ceinture — la cible est-elle bien le bac à sable ?")

    if garde_fou_envoi.en_production():
        print("   ❌ ENVIRONNEMENT=production : ce parcours écrirait sur les données")
        print("      du client et enverrait de vrais mails. Refus.")
        return 1
    print("   ✅ environnement « %s » — hors production, le garde-fou d'envoi est armé"
          % (os.getenv(garde_fou_envoi.VARIABLE_ENVIRONNEMENT) or "non déclaré"))

    if cibles["base"] == cibles["base_production"]:
        print("   ❌ la base Airtable visée EST la base de production (%s)" % cibles["base"])
        return 1
    print("   ✅ base Airtable %s (production : %s)"
          % (cibles["base"], cibles["base_production"] or "inconnue"))

    if cibles["liste_production"] and cibles["liste"] == cibles["liste_production"]:
        print("   ❌ la liste de diffusion visée EST celle de production (%s)" % cibles["liste"])
        return 1
    print("   ✅ liste de diffusion %s (production : %s)"
          % (cibles["liste"], cibles["liste_production"] or "inconnue"))

    if cibles["adresse"].lower() in cibles["controle"]:
        # La brèche est ouverte, et elle se dit. Un parcours qui livrerait
        # vraiment sans l'annoncer serait le contraire d'un bac à sable.
        autorise, refus = garde_fou_envoi.verifier([cibles["adresse"]])
        if not autorise:
            print("   ❌ adresse de contrôle %s déclarée, mais refusée par le garde-fou :"
                  % cibles["adresse"])
            print("      %s" % refus)
            return 1
        print("   ⚠  adresse de contrôle %s — elle PEUT recevoir." % cibles["adresse"])
        print("      L'invariant « aucune adresse réelle dans le bac à sable » est ouvert")
        print("      pour elle seule, le temps de prouver la livraison. Le contrôle")
        print("      `bac_a_sable.py verifier` la nommera tant qu'elle sera en base :")
        print("      la déclarer aussi dans ADRESSES_DE_CONTROLE.")
    elif not cibles["adresse"].lower().endswith(bac.DOMAINES_FICTIFS):
        print("   ❌ l'adresse du parcours (%s) n'est pas à un domaine réservé RFC 2606,"
              % cibles["adresse"])
        print("      et n'est pas déclarée dans ADRESSES_DE_CONTROLE.")
        return 1
    else:
        print("   ✅ adresse %s — domaine réservé, sans MX" % cibles["adresse"])

    # Les droits réels de la clé OVH. `/auth/currentCredential` répond même
    # quand tout le reste est refusé : c'est ce qui dissout un NotGrantedCall au
    # lieu de le prendre pour une limite d'OVH.
    try:
        regles = client_ovh.get("/auth/currentCredential").get("rules", [])
    except Exception as e:
        print("   ❌ droits de la clé OVH illisibles : %s" % str(e)[:120])
        return 1
    debordantes = [r for r in regles
                   if not bac._confinee(r["path"], cibles["domaine"], cibles["liste"])]
    if not regles or debordantes:
        for r in debordantes:
            print("   ❌ %-7s %s — cette règle déborde de « %s »"
                  % (r["method"], r["path"], cibles["liste"]))
        if not regles:
            print("   ❌ aucune règle d'accès lisible sur la clé OVH")
        print("      la clé peut atteindre autre chose que le bac à sable. Refus.")
        return 1
    print("   ✅ clé OVH confinée à « %s » (%d règle(s))" % (cibles["liste"], len(regles)))

    if not cibles["jeton_airtable_dedie"]:
        # Dit, pas tu. Il n'existe pas encore de jeton Airtable restreint au bac
        # à sable : ce qui protège ici est la vérification de la base ci-dessus,
        # donc une configuration, pas un credential. C'est plus faible que du
        # côté OVH, et ça se voit à chaque passage tant que ce n'est pas réglé.
        print("   ⚠  clé Airtable non confinée : c'est le même jeton que la production,")
        print("      qui ouvre toutes les bases de l'espace de travail. La garantie ici")
        print("      est la vérification de base ci-dessus, pas le credential.")
        print("      À créer : un jeton restreint à %s, dans AIRTABLE_API_KEY_BAC_A_SABLE."
              % cibles["base"])

    return ecarts


def controler_configuration(conf):
    """Le bac à sable se comporte-t-il comme la production, ou seulement sur les mêmes rails ?

    Une configuration amputée de ses champs liés ou de ses référentiels produit
    une répétition qui passe sans rien garantir : le rattachement au groupe n'est
    plus testé, et une valeur hors options ne fait plus échouer l'écriture ici
    alors qu'elle la ferait échouer là-bas. Ce n'est pas un écart bloquant, mais
    ça se dit.
    """
    print()
    print("2. Configuration — le comportement, pas seulement les cibles")
    airtable = conf.get("airtable", {})
    for bloc, ce_que_ca_couvre in (
        ("linked_records", "rattachement au groupe et à la structure"),
        ("computed_fields", "nouvel adhérent, année de première adhésion"),
        ("normalized_fields", "référentiels de valeurs (Genre)"),
    ):
        if airtable.get(bloc):
            print("   ✅ %-18s %s" % (bloc, ce_que_ca_couvre))
        else:
            print("   ⚠  %-18s absent : %s n'est pas rejoué" % (bloc, ce_que_ca_couvre))
    print("   ·  cotisation « %s », groupe « %s »"
          % (conf.get("cotisation_label", "?"), conf.get("groupe", "?")))
    return 0


# --------------------------------------------------------------------------
# Les étapes du parcours
# --------------------------------------------------------------------------

def etape_adhesion(item, conf):
    """L'item devient une adhésion, l'adhésion devient un payload Airtable."""
    from src.models import UserSubscription

    hello_asso = conf.get("helloAsso", {})
    adhesion = UserSubscription.from_hello_asso_item(
        item,
        cotisation=conf.get("cotisation_label"),
        groupe=conf.get("groupe"),
        default_fields=hello_asso.get("default"),
        first_sub_field=hello_asso.get("first_sub_field"),
        name_field=hello_asso.get("name_field"),
    )
    payload = adhesion.to_airtable_payload()

    poses = [q["name"] for q in item.get("customFields", [])]
    ignorees = [q for q in poses
                if q.strip() not in CHAMPS_HELLOASSO_VERS_AIRTABLE
                and q.strip() not in (hello_asso.get("default") or {})]
    print("   ✅ %s %s <%s>" % (adhesion.first_name, adhesion.last_name, adhesion.email))
    print("   ·  %d question(s) posée(s), %d colonne(s) visée(s) dans l'Annuaire"
          % (len(poses), len(payload)))
    if ignorees:
        # Une question posée qui ne rencontre aucune clé du mapping est
        # exactement la forme du défaut de consentement : aucune erreur, aucune
        # trace, une colonne vide pour toujours.
        print("   ⚠  %d question(s) posée(s) que le code ne lit pas :" % len(ignorees))
        for q in ignorees[:bac.ADRESSES_CITEES]:
            print("      « %s… »" % q[:70])
    return adhesion, payload


def etape_airtable(sync, adhesion, payload, conf, appliquer):
    """`sync_subscriptions` écrit, puis on relit. Le contrôle est la relecture.

    C'est la méthode de production qui est appelée, pas une écriture écrite pour
    l'occasion : un parcours qui emprunte un autre chemin que le cron ne prouve
    rien sur le cron.
    """
    print()
    print("4. Airtable — la fiche")
    if not appliquer:
        print("   simulation — colonnes qui seraient écrites :")
        print("      %s" % ", ".join(sorted(payload)))
        return None, 0

    # Une date de filtre antérieure à l'adhésion, sinon `sync_subscriptions`
    # l'écarte en silence et l'étape passerait au vert sans avoir rien fait.
    sync.sync_subscriptions([adhesion], adhesion.subscription_date - timedelta(seconds=1))
    compteurs = sync._compteurs

    fiche = sync.airtable_client.find_record_by_email(adhesion.email)
    if not fiche:
        print("   ❌ aucune fiche à %s après la synchronisation (traitées=%s erreurs=%s)"
              % (adhesion.email, compteurs["traitées"], compteurs["erreurs"]))
        print("      Le code n'utilise pas `typecast` : une seule valeur incompatible")
        print("      fait échouer l'écriture ENTIÈRE, et hello_asso_sync abandonne")
        print("      l'adhésion complète, mail de bienvenue compris.")
        diagnostiquer_colonnes(sync, payload, conf)
        return None, 1
    print("   ✅ fiche créée — %s (traitées=%s erreurs=%s)"
          % (fiche["id"], compteurs["traitées"], compteurs["erreurs"]))
    if compteurs["erreurs"]:
        # Attendu, et il vaut mieux le dire que laisser lire un compteur rouge
        # au milieu d'un parcours vert : hors production, le garde-fou refuse le
        # mail de bienvenue, et `hello_asso_sync` compte ce refus comme une
        # erreur depuis le 28/08/2026. En production, ce compteur signalerait un
        # vrai mail non parti.
        print("      dont le mail de bienvenue, refusé par le garde-fou — attendu ici,")
        print("      et c'est précisément ce que ce refus doit produire dans la ligne de vie.")

    ecarts = 0
    champs = fiche.get("fields", {})
    for colonne, attendu in sorted(payload.items()):
        obtenu = champs.get(colonne)
        if obtenu is None:
            # Les champs liés partent en texte et reviennent en identifiants :
            # ils sont contrôlés à l'étape suivante, pas ici.
            print("   ❌ %-28s vide (attendu « %s »)" % (colonne, attendu))
            ecarts += 1
        elif isinstance(obtenu, list):
            print("   ·  %-28s %d lien(s)" % (colonne, len(obtenu)))
        elif str(obtenu).strip().lower() != str(attendu).strip().lower():
            # Pas un écart : les référentiels et les champs calculés ont le
            # droit de transformer la valeur. On la montre, on ne la juge pas.
            print("   ·  %-28s « %s » (envoyé « %s »)" % (colonne, obtenu, attendu))
        else:
            print("   ✅ %-28s « %s »" % (colonne, obtenu))
    return fiche, ecarts


def _a_diagnostiquer(payload, conf):
    """Les colonnes réellement écrites : celles du payload **et** les calculées.

    `upsert_record` ajoute les champs calculés après coup — « Nouvel adhérent »,
    « Année de première adhésion ». Ils ne sont pas dans le payload, et un
    diagnostic qui s'en tiendrait au payload dirait « toutes les colonnes
    passent » alors que l'écriture a échoué. C'est arrivé le 28/08/2026 : la
    configuration locale nommait la colonne « Nouvel Adherent », la base la
    nomme « Nouvel adhérent ».
    """
    colonnes = dict(payload)
    for regle in (conf.get("airtable", {}).get("computed_fields") or {}).values():
        nom = regle.get("field")
        if nom and nom not in colonnes:
            colonnes[nom] = regle.get("create_value", regle.get("fallback_value", ""))
    return colonnes


def diagnostiquer_colonnes(sync, payload, conf):
    """Quelle colonne refuse sa valeur ? — quand l'écriture entière a échoué.

    Le code n'utilise pas `typecast` : une seule valeur incompatible fait
    échouer l'écriture complète, et `hello_asso_sync` fait alors `continue`,
    donc l'adhésion est perdue en entier — fiche, liste de diffusion et mail de
    bienvenue compris — pour un champ secondaire. Le message d'Airtable ne
    nomme pas toujours le champ, et un payload en porte une quinzaine.

    On repart donc d'un payload minimal qui passe forcément, puis on ajoute les
    colonnes une par une. Ce qui échoue est nommé. Tout se passe dans le bac à
    sable, et la fiche d'essai est retirée derrière.

    Les colonnes liées sont écartées : elles attendent des identifiants
    d'enregistrement, pas le texte du payload, et leur résolution appartient à
    `upsert_record`. Les écarter ici évite de les accuser à tort.
    """
    print()
    print("   diagnostic — quelle colonne refuse sa valeur ?")
    minimal = {c: payload[c] for c in ("E-mail", "Prénom", "Nom") if c in payload}
    essai = sync.airtable_client.create_record(dict(minimal))
    if not essai:
        print("      ❌ même le payload minimal (%s) est refusé : le problème n'est pas"
              % ", ".join(minimal))
        print("         une valeur, c'est l'accès à la table ou son schéma.")
        return

    liees = set(conf.get("airtable", {}).get("linked_records") or {})
    fautives, ecartees = [], []
    for colonne, valeur in sorted(_a_diagnostiquer(payload, conf).items()):
        if colonne in minimal:
            continue
        if colonne in liees:
            ecartees.append(colonne)
            continue
        if sync.airtable_client.update_record(essai["id"], {colonne: valeur}):
            print("      ✅ %-28s « %s »" % (colonne, valeur))
        else:
            print("      ❌ %-28s « %s » — refusée" % (colonne, valeur))
            fautives.append(colonne)

    import requests
    requests.delete("%s/%s" % (sync.airtable_client.base_url, essai["id"]),
                    headers=sync.airtable_client.headers, timeout=30)

    if ecartees:
        print("      ·  colonnes liées non testées ici : %s" % ", ".join(ecartees))
    if fautives:
        print()
        print("      → %d colonne(s) à traiter avant que l'adhésion puisse aboutir : %s"
              % (len(fautives), ", ".join(fautives)))
        print("         Soit le type Airtable ne correspond pas à la valeur envoyée")
        print("         (une case à cocher qui reçoit la chaîne « Oui », par exemple),")
        print("         soit la valeur est hors des options d'une liste déroulante.")


def etape_groupe(at, fiche, conf, cibles):
    """La fiche est-elle rattachée au groupe, et ce groupe est-il bien celui du bac à sable ?

    Le second contrôle n'est pas du zèle. `mailinglist_extracter` prend le
    **Label** d'un groupe pour nom de liste OVH et aligne cette liste sur
    Airtable, en supprimant tout abonné absent. Un label de bac à sable qui
    coïnciderait avec une vraie liste la viderait au profit d'adresses fictives.
    """
    print()
    print("5. Le groupe")
    if not fiche:
        print("   – sans fiche, rien à contrôler")
        return 1

    attendu = conf.get("groupe")
    liens = fiche.get("fields", {}).get("Groupe(s)") or []
    if not liens:
        print("   ❌ la fiche n'est rattachée à aucun groupe (attendu « %s »)" % attendu)
        print("      `linked_records` absent de la configuration, ou groupe introuvable")
        print("      dans « Liste des groupes » : on_missing=warn laisse tomber le champ")
        print("      sans faire échouer l'écriture, donc sans bruit.")
        return 1

    groupes = {g["id"]: g.get("fields", {})
               for g in at.enregistrements(cibles["base"], "Liste des groupes")}
    noms = [groupes.get(i, {}).get("Nom", i) for i in liens]
    if attendu not in noms:
        print("   ❌ rattachée à %s, attendu « %s »" % (", ".join(noms), attendu))
        return 1
    print("   ✅ rattachée à « %s »" % attendu)

    ecarts = 0
    for identifiant in liens:
        label = groupes.get(identifiant, {}).get("Label")
        if label and not label.startswith(cibles["liste"]):
            print("   ❌ le groupe « %s » porte le label « %s » : l'extracteur alignerait"
                  % (groupes[identifiant].get("Nom"), label))
            print("      la liste OVH « %s » sur des données fictives." % label)
            ecarts += 1
    if not ecarts:
        print("   ✅ tous les labels de groupe restent dans « %s »" % cibles["liste"])
    return ecarts


def etape_liste(client_ovh, cibles, adresse, fiche):
    """L'adresse est-elle abonnée à la liste — en tenant compte du délai OVH."""
    print()
    print("6. La liste de diffusion")
    if not fiche:
        print("   – sans fiche, l'abonnement n'a pas été demandé")
        return 1

    if bac._attendre(client_ovh, cibles["domaine"], cibles["liste"], adresse, presente=True):
        print("   ✅ %s est abonnée à « %s »" % (adresse, cibles["liste"]))
        return 0
    # Pas un écart : l'abonnement est une tâche, pas une écriture. Compter
    # l'attente comme un échec ferait chercher un bug là où il n'y en a pas —
    # c'est précisément l'erreur de diagnostic faite pendant des mois sur la
    # liste de production.
    print("   ⏳ pas encore appliqué après %d s : OVH traite l'abonnement en tâche de fond."
          % int(bac.RELECTURES * bac.ATTENTE))
    print("      Ce n'est pas un échec. Relancer le parcours plus tard avec la même")
    print("      adresse (--adresse %s) pour constater l'arrivée." % adresse)
    return 0


def etape_mail(client_email, conf, prenom, adresse, compteurs=None, livraison=False,
               chemin_rendu=None):
    """Le mail de bienvenue est-il rendu, part-il vraiment, et la ceinture tient-elle ?

    La livraison n'est **pas** provoquée ici : elle a lieu à l'étape 4, dans
    `sync_subscriptions`, par le même chemin que le cron de production. Un envoi
    déclenché à part prouverait qu'on sait envoyer un mail, pas que la chaîne
    d'adhésion en envoie un.

    Le dernier contrôle est le critère de recette du bac à sable, et il reste
    vrai même quand une adresse de contrôle est déclarée : une adresse
    d'adhérent, au domaine réel de l'association, doit être refusée.
    """
    print()
    print("7. Le mail de bienvenue")
    ecarts = 0
    try:
        texte, html = welcome_email.render(prenom)
    except Exception as e:
        print("   ❌ le rendu lève %s : %s" % (type(e).__name__, str(e)[:120]))
        return 1

    if prenom not in texte or prenom not in html:
        print("   ❌ le prénom n'apparaît pas dans le rendu")
        ecarts += 1
    else:
        print("   ✅ rendu — %d caractères en texte, %d en HTML" % (len(texte), len(html)))

    restantes = [s for s in signature.CHAMPS if s in texte or s in html]
    if restantes:
        print("   ❌ sentinelle(s) de signature non substituée(s) : %s" % ", ".join(restantes))
        print("      les SIGNATURE_* manquent, ou la substitution a été court-circuitée")
        ecarts += 1
    else:
        print("   ✅ signature substituée (les 4 sentinelles ont disparu du rendu)")

    if chemin_rendu:
        Path(chemin_rendu).write_text(html, encoding="utf-8")
        print("   ·  rendu écrit dans %s" % chemin_rendu)
        print("      ⚠ ce fichier porte le bloc de signature, donc des données")
        print("        personnelles : il ne va pas dans un dépôt.")

    if livraison:
        if compteurs is None:
            print("   ⚠  livraison demandée mais l'étape Airtable n'a pas eu lieu :")
            print("      rien n'a été envoyé.")
        elif compteurs.get("erreurs"):
            print("   ❌ le mail n'est pas parti (erreurs=%s à l'étape 4). Détail en syslog :"
                  % compteurs["erreurs"])
            print("      journalctl -t hello_asso_sync, ou la sortie DEBUG ci-dessus.")
            ecarts += 1
        elif not compteurs.get("traitées"):
            print("   ⚠  aucune adhésion traitée : aucun mail n'avait à partir.")
        else:
            print("   ✅ mail réellement envoyé à %s par la chaîne d'adhésion elle-même," % adresse)
            print("      pas par un envoi écrit pour l'occasion. Expéditeur et signature")
            print("      sont ceux de la production : c'est le mail que reçoit un adhérent.")
            print("      → aller le lire. S'il n'arrive pas, regarder les indésirables avant")
            print("        de conclure : l'expéditeur et le destinataire ne sont pas du même")
            print("        domaine.")

    if not client_email:
        print("   ⚠  pas de client d'envoi configuré (conf.ovh.email absent) :")
        print("      le refus du garde-fou n'a pas pu être éprouvé.")
        return ecarts

    envoye = client_email.send_email(
        sender=conf.get("ovh", {}).get("email", {}).get("from", EXPEDITEUR_BAC_A_SABLE),
        to=[ADRESSE_TEMOIN_REFUS],
        subject=welcome_email.SUBJECT,
        body_text=texte,
        body_html=html,
        dry_run=True,
    )
    if envoye:
        print("   ❌ le garde-fou a laissé passer un envoi vers %s." % ADRESSE_TEMOIN_REFUS)
        print("      Une adresse d'adhérent est joignable depuis cet environnement :")
        print("      c'est la ceinture qui est en cause, et c'est le critère de recette")
        print("      du bac à sable qui tombe.")
        ecarts += 1
    else:
        print("   ✅ envoi vers une adresse d'adhérent (%s) refusé" % ADRESSE_TEMOIN_REFUS)
    return ecarts


TABLE_REPONSES = "Mise à jour fiche"

# Ce que la fausse réponse corrige : un texte libre et une valeur de liste
# fermée, les deux natures qui se comportent différemment à l'écriture.
#
# La valeur de liste est **une option valide**, et pas une variante comme « H ».
# Le bac à sable l'a montré le 28/08/2026 : la table de réponses refuse « H »,
# parce que ses listes déroulantes sont dérivées de celles de l'Annuaire. C'est
# une propriété gagnée en générant la table depuis le schéma plutôt qu'en la
# saisissant — **une valeur hors options ne peut pas naître de ce formulaire**,
# donc la classe de bug qui fait échouer l'écriture entière est fermée à la
# source. Le référentiel reste appliqué à la réconciliation par précaution, et
# c'est `tests/test_reconciliation.py` qui l'éprouve.
# Les clés sont les **libellés du formulaire**, pas les colonnes de l'Annuaire :
# c'est ce que dépose une vraie soumission. La colonne visée se lit dans
# CORRESPONDANCE, de sorte que renommer une question ne casse pas ce parcours en
# silence.
CORRECTIONS = {
    "Quelle est votre fonction dans cette structure ?": "Fonction corrigée par l'adhérent",
    "Quel est votre genre ?": "Féminin",
}


# Le parcours s'est arrêté sur le formulaire : il attend une validation humaine.
# Ce n'est ni une réussite ni un écart, et surtout ce n'est pas le moment de
# faire le ménage — la fiche doit rester pour être corrigée.
EN_ATTENTE = "en-attente-de-validation"


def _lecteur_de_liens(modele):
    """De quoi lire les noms d'une table liée, sur la même base que `modele`.

    Le client porte déjà la base et le jeton : on ne les repasse pas, ce serait
    une seconde occasion de viser la mauvaise base.
    """
    from src.clients.airtable_client import AirtableClient

    def lire(table, principal, identifiants):
        client = AirtableClient(api_key=modele.api_key, base_id=modele.base_id,
                                table_name=table)
        formule = "OR(%s)" % ",".join("RECORD_ID()='%s'" % i for i in identifiants)
        return [r["fields"].get(principal) for r in client.list_records(
            filter_by_formula=formule) if r["fields"].get(principal)]

    return lire


def _reponse_par_formulaire(reponses, cibles, fiche, formulaire):
    """Le vrai formulaire, rempli par Hugo, dans son navigateur.

    C'est la seule manière d'éprouver le **préremplissage** : l'API ne sait pas
    soumettre un formulaire Airtable, et une réponse déposée par l'API prouve
    tout ce qui vient après le formulaire, jamais le formulaire lui-même. Même
    rapport que `--complet` entretient avec l'adhésion HelloAsso.
    """
    from src.lien_formulaire import resoudre_liens, url

    lien = url(cibles["base"], formulaire, fiche,
               liens=resoudre_liens(fiche, _lecteur_de_liens(reponses)))
    print("   ·  ouvre ce lien, vérifie que tes données sont là, corrige, valide :")
    print()
    print("      %s" % lien)
    print()
    if not sys.stdin.isatty():
        # Sans terminal, personne ne peut valider le formulaire pendant que le
        # script attend. On rend la main en gardant tout en place plutôt que de
        # faire échouer l'étape : la fiche et l'abonnement restent, et le
        # parcours se termine par ce qu'il reste à faire.
        return EN_ATTENTE
    input("   Entrée quand le formulaire est validé — ")

    trouvees = reponses.list_records(
        filter_by_formula="{%s}='%s'" % (CHAMP_FICHE, fiche["id"]))
    if not trouvees:
        print("   ❌ aucune réponse ne désigne la fiche %s" % fiche["id"])
        print("      Le formulaire préremplit-il « %s », et le masque-t-il ?" % CHAMP_FICHE)
        return None
    return trouvees[-1]


def etape_mise_a_jour(sync, credentials, cibles, fiche, conf, formulaire=None):
    """L'adhérent corrige sa fiche, et la réconciliation la recopie.

    C'est la seconde moitié du parcours cible : le formulaire n'est pas rejoué
    ici — l'API ne sait pas soumettre un formulaire Airtable — mais **tout ce
    qui vient après lui** l'est, à partir d'une réponse déposée dans la table.
    Ce qui n'est donc pas prouvé ici, c'est le préremplissage ; c'est le
    parcours complet, avec une vraie soumission, qui s'en charge.
    """
    from src.clients.airtable_client import AirtableClient

    print()
    print("8. La mise à jour de fiche")
    if not fiche:
        print("   – sans fiche, rien à mettre à jour")
        return 1, None

    reponses = AirtableClient(
        api_key=credentials["airtable"]["api_key"],
        base_id=credentials["airtable"]["base_id"],
        table_name=TABLE_REPONSES,
    )

    if formulaire:
        depose = _reponse_par_formulaire(reponses, cibles, fiche, formulaire)
        if depose is EN_ATTENTE:
            return 0, EN_ATTENTE
        if not depose:
            return 1, None
        print("   ✅ réponse reçue du formulaire — %s, désignant la fiche %s"
              % (depose["id"], fiche["id"]))
    else:
        depose = reponses.create_record(dict(CORRECTIONS, **{CHAMP_FICHE: fiche["id"]}))
        if not depose:
            print("   ❌ impossible de déposer une réponse dans « %s »" % TABLE_REPONSES)
            print("      La table existe-t-elle ? scripts/creer_table_mise_a_jour.py")
            return 1, None
        print("   ✅ réponse déposée — %s, désignant la fiche %s"
              % (depose["id"], fiche["id"]))

    # Ce qu'on vérifiera dans la fiche : les réponses réellement saisies, pas une
    # liste écrite d'avance. Par le formulaire, on ne sait pas ce qu'Hugo a tapé
    # — et c'est justement ce qu'on veut retrouver de l'autre côté.
    attendus = payload_depuis_reponse(depose.get("fields", {}))
    sync.airtable_client.normaliser_champs(attendus)
    question = {colonne: libelle for libelle, colonne in CORRESPONDANCE.items()}

    compteurs = Reconciliation(sync.airtable_client, reponses).passer()
    print("   ·  passage : reçues=%(màj_reçues)s appliquées=%(màj_appliquées)s "
          "erreurs=%(erreurs)s" % compteurs)

    ecarts = 0
    relue = sync.airtable_client.find_record_by_email(fiche["fields"].get("E-mail", ""))
    champs = (relue or {}).get("fields", {})

    if not attendus:
        print("   ⚠  la réponse ne portait aucune valeur : rien à recopier")
    for colonne, attendu in sorted(attendus.items()):
        if champs.get(colonne) == attendu:
            print("   ✅ %-24s ← « %s »" % (colonne, question.get(colonne, colonne)))
        else:
            print("   ❌ %-24s « %s », attendu « %s » (question « %s »)"
                  % (colonne, champs.get(colonne), attendu,
                     question.get(colonne, colonne)))
            ecarts += 1

    if champs.get(CHAMP_DATE_MAJ):
        print("   ✅ %-28s %s — l'adhérent ne sera plus relancé"
              % (CHAMP_DATE_MAJ, champs[CHAMP_DATE_MAJ]))
    else:
        print("   ❌ %-28s vide : le suivi ne sait pas qu'il a répondu" % CHAMP_DATE_MAJ)
        ecarts += 1

    relue_reponse = reponses.list_records(
        filter_by_formula="RECORD_ID()='%s'" % depose["id"])
    if relue_reponse and relue_reponse[0]["fields"].get(CHAMP_SYNCHRONISE):
        print("   ✅ %-28s cochée — elle ne sera pas rejouée" % CHAMP_SYNCHRONISE)
    else:
        print("   ⚠  %-28s non cochée : la réponse sera rejouée au passage suivant,"
              % CHAMP_SYNCHRONISE)
        print("      sans conséquence puisque les valeurs sont les mêmes")

    return ecarts, (reponses, depose["id"])


def _attente(fiche, cibles):
    """Ce qu'il reste à faire quand le parcours s'arrête sur le formulaire."""
    print()
    print("→ le parcours attend ta validation. Rien n'a été nettoyé :")
    print("   ·  fiche      %s" % fiche["id"])
    print("   ·  adresse    %s" % cibles["adresse"])
    print("   Une fois le formulaire validé, la réconciliation reprend depuis là.")


def etape_menage(sync, client_ovh, cibles, fiche, adresse, garder, reponse=None):
    """Rendre le bac à sable dans l'état trouvé.

    Ce n'est pas de la coquetterie : l'espace de travail Airtable de la Coop a
    dépassé sa limite d'enregistrements (16 309 sur 31 bases, relevé le
    27/08/2026). Un parcours qui laisse une fiche derrière lui à chaque passage
    fait grossir le problème qu'on doit faire porter au client.
    """
    print()
    print("9. Ménage")
    if garder:
        print("   – conservé sur demande (--garder) : fiche %s, abonnement %s"
              % (fiche["id"] if fiche else "aucune", adresse))
        return 0

    if reponse:
        client, identifiant = reponse
        import requests as _r
        r = _r.delete("%s/%s" % (client.base_url, identifiant),
                      headers=client.headers, timeout=30)
        print("   %s réponse de mise à jour %s"
              % ("✅" if r.ok else "⚠ ", "supprimée" if r.ok else "à retirer à la main"))
    if not fiche:
        print("   – rien à retirer")
        return 0

    import requests
    r = requests.delete("%s/%s" % (sync.airtable_client.base_url, fiche["id"]),
                        headers=sync.airtable_client.headers, timeout=30)
    if r.ok:
        print("   ✅ fiche supprimée")
    else:
        print("   ⚠  fiche non supprimée (%s) : à retirer à la main" % r.status_code)

    try:
        client_ovh.delete("/email/domain/%s/mailingList/%s/subscriber/%s"
                          % (cibles["domaine"], cibles["liste"], adresse))
    except Exception as e:
        # L'abonné peut n'être pas encore arrivé : la tâche d'ajout est
        # asynchrone, donc la tâche de retrait peut la précéder.
        print("   ⚠  désabonnement refusé (%s) : l'abonnement n'est pas encore appliqué,"
              % type(e).__name__)
        print("      la tâche de retrait a devancé celle d'ajout. Relancer le parcours")
        print("      plus tard avec --adresse %s le retirera." % adresse)
    else:
        print("   ✅ désabonnement demandé")
    return 0


# --------------------------------------------------------------------------
# Montage
# --------------------------------------------------------------------------

class SyncBacASable(SyncHelloAsso):
    """`SyncHelloAsso` câblé sur le bac à sable, et sur rien d'autre.

    `load_config` prend les credentials dans l'environnement, où
    `AIRTABLE_BASE_ID` et `OVH_APP_KEY` désignent ce qu'ils désignent — sur ce
    poste, ils ont déjà désigné la mauvaise base pendant des semaines. On ne
    négocie donc pas avec l'environnement : les identifiants du bac à sable sont
    posés par-dessus, juste avant la construction des clients.
    """

    def __init__(self, chemin_conf, credentials, dry_run=None):
        self._credentials_bac_a_sable = credentials
        super().__init__(chemin_conf, dry_run=dry_run)

    def _init_clients(self):
        for service, valeurs in self._credentials_bac_a_sable.items():
            self.conf_global["credentials"].setdefault(service, {}).update(valeurs)
        super()._init_clients()


def _conf_bac_a_sable(chemin, cibles, expediteur=None):
    """La configuration de production, ses cibles remplacées par celles du bac à sable.

    Le comportement est recopié tel quel — champs liés, champs calculés,
    référentiels — parce que c'est lui qu'on répète. Seules les cibles bougent,
    et elles bougent ici, en un seul endroit, plutôt que d'être renseignées à la
    main dans un second fichier qui dériverait.
    """
    if not os.path.exists(chemin):
        sys.exit("Configuration introuvable : %s\nC'est d'elle que le parcours tire le "
                 "comportement à répéter (champs liés, champs calculés, référentiels). "
                 "La désigner avec --config." % chemin)
    with open(chemin, encoding="utf-8") as f:
        conf = copy.deepcopy(json.load(f).get("conf", {}))

    conf.setdefault("ovh", {}).setdefault("mailing_list", {})
    conf["ovh"]["mailing_list"]["name"] = cibles["liste"]
    conf["ovh"]["mailing_list"]["domain"] = cibles["domaine"]
    # L'expéditeur est **remplacé**, jamais conservé. Celui de la production est
    # la boîte nominative de la présidente : un envoi parti du bac à sable ne
    # doit pouvoir se réclamer ni de l'association, ni d'une personne. Domaine
    # réservé, donc sans MX, donc sans retour possible non plus.
    conf["ovh"].setdefault("email", {})
    # En mode livraison, l'expéditeur doit être la boîte authentifiée auprès du
    # relais SMTP : OVH refuse un `From` qui n'est pas la sienne. Prouver qu'un
    # mail arrive impose donc de l'émettre depuis l'adresse de production, avec
    # sa signature. C'est le prix de la démonstration, et il se dit.
    conf["ovh"]["email"]["from"] = expediteur or EXPEDITEUR_BAC_A_SABLE
    conf["ovh"]["email"].setdefault("subject", welcome_email.SUBJECT)
    conf["ovh"]["email"]["send_confirmation"] = True
    conf.setdefault("helloAsso", {})["form_name"] = cibles["formulaire"]
    return conf


def _cibles(args, conf_locale):
    liste = args.liste or os.getenv("OVH_MAILING_LIST_BAC_A_SABLE") or "bac-a-sable"
    domaine = (args.domaine or os.getenv("OVH_MAILING_LIST_DOMAIN")
               or conf_locale.get("ovh", {}).get("mailing_list", {}).get("domain"))
    base = args.base or os.getenv("AIRTABLE_BASE_ID_BAC_A_SABLE")
    if not base:
        sys.exit("Bac à sable non désigné : --base appXXXX, ou "
                 "AIRTABLE_BASE_ID_BAC_A_SABLE dans le .env.")
    if not domaine:
        sys.exit("Domaine de la liste inconnu : --domaine, OVH_MAILING_LIST_DOMAIN, "
                 "ou le config JSON.")
    # Une adresse de contrôle déclarée devient l'adresse de l'adhésion : le mail
    # de bienvenue part à l'adresse de l'adhérent, pas ailleurs. Prouver la
    # livraison suppose donc que l'adhérent, ce soit vous.
    controle = bac.adresses_de_controle(
        [args.adresse_de_controle] if args.adresse_de_controle else None)
    if args.adresse_de_controle and not controle:
        sys.exit("Adresse de contrôle invalide : il faut une adresse nominative, pas un motif.")
    adresse = (args.adresse
               or (args.adresse_de_controle.strip().lower() if args.adresse_de_controle else None)
               or MODELE_ADRESSE % datetime.now().strftime("%Y%m%d-%H%M%S"))

    return {
        "base": base,
        "base_production": os.getenv("AIRTABLE_BASE_ID_PROD"),
        "liste": liste,
        "liste_production": conf_locale.get("ovh", {}).get("mailing_list", {}).get("name"),
        "domaine": domaine,
        "adresse": adresse,
        "controle": controle,
        "formulaire": (args.formulaire or os.getenv("HELLOASSO_FORM_BAC_A_SABLE")
                       or "Bac à sable adhésion test"),
        "formulaire_production": conf_locale.get("helloAsso", {}).get("form_name"),
        "jeton_airtable_dedie": bool(os.getenv("AIRTABLE_API_KEY_BAC_A_SABLE")),
    }


def _credentials(cibles):
    """Identifiants du bac à sable, dédiés quand ils existent."""
    ovh = {suffixe: os.getenv("OVH_%s_BAC_A_SABLE" % suffixe)
           for suffixe in ("APP_KEY", "APP_SECRET", "CONSUMER_KEY")}
    if not all(ovh.values()):
        sys.exit("Identifiants OVH du bac à sable absents du .env. Créer une clé "
                 "restreinte à « %s » sur https://eu.api.ovh.com/createToken/ et la "
                 "poser dans OVH_APP_KEY_BAC_A_SABLE / OVH_APP_SECRET_BAC_A_SABLE / "
                 "OVH_CONSUMER_KEY_BAC_A_SABLE." % cibles["liste"])

    jeton = (os.getenv("AIRTABLE_API_KEY_BAC_A_SABLE") or os.getenv("AIRTABLE_API_KEY")
             or os.getenv("AIRTABLE_API_KEY_PROD"))
    if not jeton:
        sys.exit("Aucun jeton Airtable dans le .env.")

    return {
        "airtable": {"api_key": jeton, "base_id": cibles["base"]},
        "ovh": {"ak": ovh["APP_KEY"], "as": ovh["APP_SECRET"], "ck": ovh["CONSUMER_KEY"],
                "endpoint": os.getenv("OVH_ENDPOINT", "ovh-eu")},
    }


def _genres(jeton, base):
    """Options du champ Genre dans la base cible, si elles sont lisibles."""
    try:
        schema = {t["name"]: t for t in bac.Airtable(jeton).schema(base)}
    except (SystemExit, Exception):
        # Sans schéma lisible on retombe sur « Non-précisé », qui est une option
        # partout. Ne pas savoir lire le schéma n'est pas une raison de ne pas
        # rejouer le parcours.
        return []
    if "Annuaire" not in schema:
        return []
    return bac._options_du_champ(schema["Annuaire"], "Genre")


def parcours(args):
    conf_locale = bac._conf_locale(args.config)
    cibles = _cibles(args, conf_locale)
    credentials = _credentials(cibles)
    livraison = bool(args.adresse_de_controle)
    expediteur = args.expediteur or (os.getenv("SMTP_USER") if livraison else None)
    conf = _conf_bac_a_sable(args.config, cibles, expediteur)

    import ovh as ovh_api
    client_ovh = ovh_api.Client(endpoint=credentials["ovh"]["endpoint"],
                                application_key=credentials["ovh"]["ak"],
                                application_secret=credentials["ovh"]["as"],
                                consumer_key=credentials["ovh"]["ck"])

    print("parcours d'adhésion — bac à sable%s"
          % (" — COMPLET, avec livraison réelle" if livraison and args.complet
             else " — COMPLET" if args.complet
             else " — livraison réelle" if livraison else ""))
    print()
    if livraison and not args.appliquer:
        print("⚠  --adresse-de-controle sans --appliquer : rien n'est écrit, donc aucun")
        print("   mail n'est envoyé. Ajouter --appliquer pour la livraison.")
        print()
    ecarts = controler_cibles(cibles, client_ovh)
    if ecarts:
        print()
        print("→ la ceinture n'est pas bouclée, on ne va pas plus loin.")
        return 1
    ecarts += controler_configuration(conf)

    at = bac.Airtable(credentials["airtable"]["api_key"])

    print()
    print("3. L'adhésion")
    if args.item:
        item = item_depuis_fichier(args.item, cibles["adresse"])
        print("   ·  item rejoué depuis %s" % args.item)
    elif args.complet:
        item = item_depuis_helloasso(conf, cibles, args.depuis, args.capturer)
    else:
        item = item_synthetique(
            cibles["adresse"], _genres(credentials["airtable"]["api_key"], cibles["base"]))
        print("   ·  item synthétique, construit sur les libellés que le code déclare lire :")
        print("      il ne peut donc pas voir un libellé de formulaire qui ne rencontre")
        print("      rien. Pour ça, --complet ou bac_a_sable.py formulaire.")

    adhesion, payload = etape_adhesion(item, conf)

    # La configuration part dans un fichier temporaire : `SyncHelloAsso` prend un
    # chemin, et l'écrire à côté de la vraie configuration créerait un second
    # fichier de configuration qui dériverait.
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8",
                                     delete=False) as f:
        # Les identifiants HelloAsso sont posés en dur et sans valeur : ce
        # parcours n'appelle jamais HelloAsso, mais `load_config` refuse une
        # configuration qui n'en porte pas. Un vrai identifiant présent dans
        # l'environnement les écrasera, sans conséquence — le client est
        # construit et jamais utilisé.
        json.dump({"conf": conf,
                   "credentials": {"helloAsso": {"id": "non-utilisé",
                                                 "secret": "non-utilisé"}}},
                  f, ensure_ascii=False)
        chemin_temporaire = f.name
    try:
        sync = SyncBacASable(chemin_temporaire, credentials,
                             dry_run=None if args.appliquer else "full")
        fiche, e = etape_airtable(sync, adhesion, payload, conf, args.appliquer)
        ecarts += e
        if args.appliquer:
            ecarts += etape_groupe(at, fiche, conf, cibles)
            ecarts += etape_liste(client_ovh, cibles, cibles["adresse"], fiche)
        ecarts += etape_mail(sync.ovh_email_client, conf, adhesion.first_name,
                             cibles["adresse"],
                             compteurs=sync._compteurs if args.appliquer else None,
                             livraison=livraison and args.appliquer,
                             chemin_rendu=args.rendu)
        reponse = None
        if args.appliquer:
            e, reponse = etape_mise_a_jour(sync, credentials, cibles, fiche, conf,
                                           args.maj_formulaire)
            ecarts += e
            if reponse is EN_ATTENTE:
                _attente(fiche, cibles)
                return 0
            etape_menage(sync, client_ovh, cibles, fiche, cibles["adresse"], args.garder,
                         reponse)
    finally:
        os.unlink(chemin_temporaire)

    print()
    if ecarts:
        print("→ %d écart(s)" % ecarts)
        return 1
    if not args.appliquer:
        print("→ ceinture bouclée et adhésion lisible. Rien n'a été écrit :")
        print("  relancer avec --appliquer pour rejouer le parcours en entier.")
        return 0
    print("→ parcours complet, aucun écart")
    return 0


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--appliquer", action="store_true",
                   help="écrire vraiment dans le bac à sable (défaut : simulation)")
    p.add_argument("--garder", action="store_true",
                   help="ne pas retirer la fiche ni l'abonnement à la fin")
    p.add_argument("--adresse", help="adresse du parcours (défaut : horodatée, en @example.org)")
    p.add_argument("--item", help="item HelloAsso capturé (JSON) à rejouer, plutôt qu'un "
                                  "item synthétique construit sur le mapping")
    p.add_argument("--complet", action="store_true",
                   help="aller chercher chez HelloAsso l'adhésion que vous venez de saisir "
                        "sur le formulaire de test : la chaîne entière, appel à HelloAsso "
                        "et libellés réels compris")
    p.add_argument("--depuis", metavar="ADRESSE",
                   help="complet : choisir l'adhésion payée par cette adresse "
                        "(défaut : la plus récente)")
    p.add_argument("--capturer", metavar="FICHIER",
                   help="complet : enregistrer l'item récupéré (adresse remplacée) pour le "
                        "rejouer ensuite avec --item")
    p.add_argument("--adresse-de-controle", metavar="ADRESSE",
                   help="livrer vraiment le mail de bienvenue à cette adresse, qui devient "
                        "celle de l'adhésion. Ouvre une exception nominative aux deux "
                        "invariants du bac à sable, et la commande le dit à chaque passage.")
    p.add_argument("--expediteur",
                   help="expéditeur du mail (défaut : SMTP_USER en livraison, sinon une "
                        "adresse en @example.org)")
    p.add_argument("--rendu", help="écrire le mail de bienvenue rendu dans ce fichier HTML")
    p.add_argument("--base", help="base Airtable du bac à sable "
                                  "(défaut : AIRTABLE_BASE_ID_BAC_A_SABLE)")
    p.add_argument("--liste", help="liste de diffusion de test "
                                   "(défaut : OVH_MAILING_LIST_BAC_A_SABLE, sinon bac-a-sable)")
    p.add_argument("--domaine", help="domaine de la liste (défaut : celui du config JSON)")
    p.add_argument("--formulaire", help="titre du formulaire HelloAsso de test")
    p.add_argument("--maj-formulaire", metavar="shrXXXX",
                   help="étape 8 : ouvrir le vrai formulaire de mise à jour prérempli "
                        "et attendre sa validation, au lieu de déposer la réponse par "
                        "l'API. C'est ce qui éprouve le préremplissage.")
    p.add_argument("--config", default="config/hello-asso-automation-conf.json",
                   help="configuration dont le comportement est repris (champs liés, "
                        "champs calculés, référentiels)")
    return parcours(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())
