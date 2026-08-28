"""Le lien prérempli vers le formulaire de mise à jour de fiche.

C'est ce qui fait que l'adhérent *voit* ce qu'on sait de lui au lieu de tout
retaper. Un formulaire Airtable se préremplit par l'URL : `prefill_<question>`
pose une réponse, `hide_<question>` masque la ligne. Le `record_id` de la fiche
voyage ainsi, prérempli et masqué : c'est lui qui dit à la réconciliation quelle
fiche mettre à jour, sans rapprochement par adresse — sept fiches en portent
plusieurs dans « Mail optionnel ».

Deux façons de construire ce lien, et elles ne servent pas la même chose.

**`formule()` rend la formule Airtable**, à poser dans le champ
`lien personnalisé formulaire` de l'`Annuaire`. C'est celle qui compte : le lien
est alors calculé par Airtable, pour chaque fiche, en permanence. Le mail de
bienvenue n'a plus qu'à lire ce champ. Rien à redéployer quand le formulaire
change, et le lien est juste même pour une fiche modifiée à la main.

**`url()` rend le lien en Python**, pour éprouver le parcours sans dépendre de la
formule. Une réserve à connaître : dans l'`Annuaire`, les colonnes liées portent
des identifiants (`recXXX`), alors que le formulaire attend le **nom** de
l'enregistrement. `url()` les écarte donc, sauf si l'appelant fournit les noms.
La formule, elle, n'a pas ce problème : Airtable rend déjà les noms.

Les deux se dérivent de `CHAMPS_FORMULAIRE`, comme la table elle-même. Une
question renommée suit partout, ou nulle part.
"""

import urllib.parse

from src.reconciliation import CHAMP_FICHE, CHAMPS_FORMULAIRE

RACINE = "https://airtable.com"

# Les colonnes date : Airtable les rend en date-heure ISO dans une formule, et le
# formulaire n'en veut que le jour.
COLONNES_DATE = ("date de naissance",)

# Un identifiant d'enregistrement Airtable. Sert à reconnaître une colonne liée
# non résolue plutôt qu'à la préremplir avec un `rec…` que l'adhérent verrait.
PREFIXE_IDENTIFIANT = "rec"


def _identifiants(valeurs):
    return all(isinstance(v, str) and v.startswith(PREFIXE_IDENTIFIANT) for v in valeurs)


def racine(base, formulaire):
    """L'adresse du formulaire, avant les paramètres.

    Airtable a deux générations de formulaires : la vue formulaire classique,
    partagée en `airtable.com/appXXX/shrXXX`, et le constructeur récent, dont
    l'adresse porte un `pagXXX`. Plutôt que de deviner laquelle, on accepte
    aussi bien un identifiant qu'une adresse complète collée depuis le bouton
    « Partager » — c'est ce qu'on a sous la main quand on teste.
    """
    if formulaire.startswith("http"):
        return formulaire.split("?")[0].rstrip("/")
    return "%s/%s/%s" % (RACINE, base, formulaire)


def url(base, formulaire, fiche, liens=None):
    """Le lien prérempli pour une fiche.

    Args:
        base: identifiant de la base (`appXXX`).
        formulaire: identifiant du formulaire (`shrXXX`), ou son adresse
            complète.
        fiche: l'enregistrement de l'`Annuaire`, tel que l'API le rend.
        liens: noms lisibles des colonnes liées, `{colonne: [noms]}`. Sans eux,
            ces colonnes ne sont pas préremplies — un `recXXX` dans un champ de
            formulaire ne veut rien dire pour l'adhérent.
    """
    liens = liens or {}
    champs = fiche.get("fields", {})
    params = [("prefill_" + CHAMP_FICHE, fiche["id"]),
              ("hide_" + CHAMP_FICHE, "true")]

    for libelle, colonne, _ in CHAMPS_FORMULAIRE:
        valeur = liens.get(colonne, champs.get(colonne))
        if valeur is None or valeur == "" or valeur == []:
            continue
        if isinstance(valeur, list):
            if _identifiants(valeur):
                continue
            valeur = ",".join(str(v) for v in valeur)
        params.append(("prefill_" + libelle, str(valeur)))

    return "%s?%s" % (racine(base, formulaire), urllib.parse.urlencode(params))


def formule(base, formulaire):
    """La formule Airtable du champ `lien personnalisé formulaire`.

    Un champ vide n'ajoute pas son paramètre : le lien reste court, et le
    formulaire affiche une question vraiment vide plutôt qu'une réponse à blanc.
    """
    encode = urllib.parse.quote

    lignes = ['"%s?prefill_%s=" & RECORD_ID() & "&hide_%s=true"'
              % (racine(base, formulaire), CHAMP_FICHE, CHAMP_FICHE)]

    for libelle, colonne, _ in CHAMPS_FORMULAIRE:
        valeur = "{%s}" % colonne
        if colonne in COLONNES_DATE:
            valeur = "DATETIME_FORMAT(%s, 'YYYY-MM-DD')" % valeur
        else:
            # Concaténer une chaîne vide ramène nombres et listes liées à du
            # texte : `ENCODE_URL_COMPONENT` n'accepte que ça.
            valeur = "%s & \"\"" % valeur
        lignes.append('IF({%s}, "&prefill_%s=" & ENCODE_URL_COMPONENT(%s), "")'
                      % (colonne, encode(libelle), valeur))

    return "\n& ".join(lignes)
