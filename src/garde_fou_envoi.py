"""Ceinture d'envoi : hors production, refuser d'écrire à qui n'est pas sur la liste.

Le raisonnement tient en une phrase : **une consigne ne tient pas quatre mois, une
ceinture si.** Ce n'est pas une opinion, c'est mesuré sur ce projet. La consigne
« mettre le curseur à la bonne date avant le déploiement », écrite en avril dans
`vars.yml`, aurait renvoyé un mail de bienvenue à tous les adhérents depuis avril
si le playbook n'avait pas été corrigé le 26/08/2026. Personne ne l'avait relue.

Ici l'enjeu est le même en plus gros : l'annuaire porte 1061 fiches. Un script de
relance lancé une fois de trop, un `inventory/dev` qui pointe encore sur les
données de production, et l'erreur n'est pas rattrapable — un mail parti est
parti.

Le mécanisme, donc :

- Deux variables d'environnement. `ENVIRONNEMENT` vaut `production` ou autre
  chose ; `DESTINATAIRES_AUTORISES` porte la liste blanche du bac à sable.
- **Le défaut est le refus.** Variable absente = hors production = liste blanche
  vide = aucun envoi. C'est le sens de la sécurité qui compte : l'oubli doit
  bloquer, jamais laisser passer. Un poste de développement, une machine
  fraîche, un conteneur de CI n'ont rien à poser pour être sûrs ; c'est la
  production qui doit se déclarer, et elle le fait par le playbook, une fois.
- **Le garde-fou passe avant le `dry_run`**, exprès. Une ceinture qui se relâche
  en simulation apprend au développeur que « ça marche », et l'envoi réel part
  ensuite dans le mur. Un parcours de test doit buter sur le refus tout de suite.

Point d'application : `OVHEmailClient.send_email`, seul endroit du dépôt qui
ouvre une connexion SMTP. Le placer plus haut obligerait chaque nouveau script à
y penser, et c'est exactement ce qui ne tient pas.

La normalisation des adresses est volontairement recopiée ici plutôt qu'importée
de `mailinglist_extracter` : faire dépendre un client d'un script d'entrée pour
deux appels de méthode coûterait plus cher que la ligne dupliquée.
"""

import os
import syslog

VARIABLE_ENVIRONNEMENT = "ENVIRONNEMENT"
VARIABLE_LISTE_BLANCHE = "DESTINATAIRES_AUTORISES"
PRODUCTION = "production"

# Nombre d'adresses citées dans un message de refus. Un refus qui recracherait
# les 1061 destinataires rendrait le log illisible, donc non lu.
ADRESSES_CITEES = 3


def normaliser(adresse):
    """Forme canonique d'une adresse, pour comparaison uniquement."""
    return adresse.strip().lower() if isinstance(adresse, str) else ""


def en_production():
    """Vrai seulement si l'environnement s'est explicitement déclaré production."""
    return normaliser(os.getenv(VARIABLE_ENVIRONNEMENT)) == PRODUCTION


def _est_dangereux(motif):
    """Un motif qui rouvrirait la liste blanche à tout le monde.

    Sans ce filtre, désarmer la ceinture demanderait un seul caractère —
    `DESTINATAIRES_AUTORISES=*` — et quelqu'un finirait par l'écrire un soir
    pour débloquer un envoi. Le seul moyen de sortir du bac à sable doit rester
    de déclarer `ENVIRONNEMENT=production`, qui se voit dans un inventaire.
    """
    if motif in ("*", "*@*", "@*", "*@"):
        return True
    if motif.startswith("*@"):
        # « *@coopdescommuns.org » est un motif de domaine légitime,
        # « *@org » ou « *@fr » couvrirait la moitié d'internet.
        return "." not in motif[2:]
    # Un joker ailleurs qu'en tête de domaine n'est pas géré : le laisser
    # passer donnerait l'illusion qu'il filtre.
    return "*" in motif


def motifs_autorises():
    """Liste blanche lue dans l'environnement, motifs dangereux écartés."""
    brut = os.getenv(VARIABLE_LISTE_BLANCHE) or ""
    motifs = []
    for morceau in brut.replace(";", ",").split(","):
        motif = normaliser(morceau)
        if not motif:
            continue
        if _est_dangereux(motif):
            syslog.syslog(
                syslog.LOG_ERR,
                "garde-fou d'envoi : motif « {} » ignoré, il ouvrirait la liste "
                "blanche à tout le monde".format(motif),
            )
            continue
        motifs.append(motif)
    return motifs


def _est_autorisee(adresse, motifs):
    for motif in motifs:
        if motif.startswith("*@"):
            # On garde le « @ » dans la comparaison : sinon
            # « pirate@faux-coopdescommuns.org » passerait pour un motif
            # « *@coopdescommuns.org ».
            if adresse.endswith(motif[1:]):
                return True
        elif adresse == motif:
            return True
    return False


def verifier(destinataires):
    """Le destinataire de ce mail peut-il le recevoir depuis cet environnement ?

    Args:
        destinataires: toutes les adresses jointes par le message, `to`, `cc` et
            `bcc` confondus. Un `bcc` non contrôlé serait une porte ouverte.

    Returns:
        (autorisé, motif du refus). Le motif est vide quand c'est autorisé, et
        rédigé pour dire quoi faire quand ça ne l'est pas : un refus qu'on ne
        sait pas lever se contourne en désactivant le garde-fou.
    """
    if en_production():
        return True, ""

    motifs = motifs_autorises()
    if not motifs:
        return False, (
            "environnement « {} » (pas production) et {} est vide : aucun envoi "
            "n'est possible. Lister les adresses de test dans {}, ou déclarer "
            "{}=production si c'est bien la production.".format(
                os.getenv(VARIABLE_ENVIRONNEMENT) or "non déclaré",
                VARIABLE_LISTE_BLANCHE,
                VARIABLE_LISTE_BLANCHE,
                VARIABLE_ENVIRONNEMENT,
            )
        )

    refusees = [
        adresse
        for adresse in (normaliser(d) for d in destinataires or [])
        if adresse and not _est_autorisee(adresse, motifs)
    ]
    if not refusees:
        return True, ""

    citees = ", ".join(refusees[:ADRESSES_CITEES])
    if len(refusees) > ADRESSES_CITEES:
        citees += " (+{} autres)".format(len(refusees) - ADRESSES_CITEES)
    return False, (
        "{} destinataire(s) hors liste blanche : {}. Environnement « {} », "
        "{} = {}.".format(
            len(refusees),
            citees,
            os.getenv(VARIABLE_ENVIRONNEMENT) or "non déclaré",
            VARIABLE_LISTE_BLANCHE,
            ", ".join(motifs),
        )
    )
