"""Recopie les réponses du formulaire de mise à jour dans les fiches de l'Annuaire.

Un formulaire Airtable natif ne sait que **créer** une ligne, jamais en modifier
une. C'est la seule raison d'être de ce module : le formulaire écrit dans la
table « Mise à jour fiche », et ce passage recopie chaque réponse dans la fiche
que désigne son `record_id`. Pour l'adhérent, la différence est invisible — il
voit ses données, les corrige, valide. Pour nous, elle laisse une trace de ce
qu'il a réellement répondu, ce qu'une écriture directe n'aurait pas donné.

Quatre règles, et chacune vient d'un défaut déjà rencontré sur ce projet.

**Ne jamais écraser par du vide.** Une réponse laissée blanche ne veut pas dire
« efface ce que tu sais de moi ». Un champ absent de la réponse est un champ
qu'on ne touche pas.

**Valider les valeurs à choix fermé avant d'écrire.** Le code n'utilise pas
`typecast` : une seule valeur hors options fait échouer l'écriture **entière**.
Le 28/08/2026, c'est comme ça qu'une chaîne « Oui » dans une case à cocher
faisait perdre l'adhésion complète, mail de bienvenue compris. Le référentiel de
`AirtableClient` est donc appliqué ici aussi.

**Une ligne fautive n'arrête pas les autres.** Le même matin, `mailinglist_extracter`
abandonnait ses 24 listes dès qu'une adresse était refusée par OVH : la donnée
d'une personne privait toutes les autres de synchronisation. Chaque réponse est
donc traitée dans son propre `try`.

**Une réponse non recopiée reste non synchronisée.** Elle sera retentée au
passage suivant. Une erreur permanente — un `record_id` qui ne désigne plus
rien — se signalera donc à chaque passage, et c'est voulu : elle est visible
dans la ligne de vie au lieu d'être enterrée par un abandon silencieux.
"""

import syslog
from datetime import datetime

# Les deux colonnes techniques de la table de réponses. Elles ne décrivent pas
# l'adhérent et ne doivent jamais partir vers l'Annuaire.
CHAMP_FICHE = "record_id"
CHAMP_SYNCHRONISE = "Synchronisé"

# La date de suivi, dans l'Annuaire. Vide = l'adhérent n'a pas rempli son
# formulaire, donc il est relançable. C'est le seul lien entre ce module et la
# relance.
CHAMP_DATE_MAJ = "Fiche mise à jour le"

CHAMPS_TECHNIQUES = (CHAMP_FICHE, CHAMP_SYNCHRONISE)

# Le formulaire, dans l'ordre où il pose ses questions.
#
# `(libellé, colonne de l'Annuaire, explication)`.
#
# **Le libellé est une phrase, pas un nom de colonne, et c'est délibéré.** Un
# formulaire Airtable affiche le nom du champ comme intitulé de question : « 2
# personnes connues », « code postal », « Partage de donnée autorisé » sont des
# noms tenus par une gestionnaire, pas des questions posées à un adhérent. On
# écrit donc la question en toutes lettres, et l'explication vient sous elle.
#
# Le prix de cette lisibilité est une correspondance à tenir, là où des noms
# identiques n'en demandaient aucune. Elle est donc déclarée **ici et nulle part
# ailleurs** : `scripts/creer_table_mise_a_jour.py` s'en sert pour poser les
# champs, ce module pour les relire. Les deux ne peuvent pas diverger puisqu'ils
# lisent la même liste, et le script vérifie à chaque passage que chaque colonne
# visée existe bien dans l'Annuaire.
# `Mail optionnel` n'y est pas : question retirée du formulaire par Hugo le
# 28/08 — une seconde adresse n'a pas de sens à demander à l'adhérent. La colonne
# reste dans l'Annuaire (elle sert au rapprochement, sept fiches en portent
# plusieurs), elle ne sera simplement plus mise à jour par ce parcours.
CHAMPS_FORMULAIRE = [
    ("Quel est votre nom ?", "Nom", ""),
    ("Quel est votre prénom ?", "Prénom", ""),
    ("À quelle adresse e-mail la Coop peut-elle vous écrire ?", "E-mail",
     "C'est à cette adresse que partiront les messages de la Coop."),
    ("À quel numéro peut-on vous joindre ?", "Téléphone", "Facultatif."),
    ("Quel est votre genre ?", "Genre", ""),
    ("Quelle est votre date de naissance ?", "date de naissance", "Facultatif."),
    ("Quel est votre code postal ?", "code postal",
     "Nous sert à savoir où se trouvent les adhérent·es, rien de plus."),
    ("Dans quelle structure travaillez-vous ?", "Structure(s)",
     "Choisissez-la dans la liste. Si elle n'y figure pas, laissez vide et "
     "dites-le nous."),
    ("Quelle est votre fonction dans cette structure ?", "Fonction (structure)", ""),
    ("Quels sont vos centres d'intérêt ?", "Intérêts",
     "Quelques mots-clés suffisent."),
    ("Quelles sont les deux personnes que vous connaissez le mieux à la Coop ?",
     "2 personnes connues",
     "Surtout utile s'il s'agit de votre première adhésion."),
    ("Vous êtes plutôt…", "Type", ""),
    ("En quelle année avez-vous adhéré à la Coop pour la première fois ?",
     "Année de première adhésion",
     "Si vous ne vous en souvenez pas, laissez vide."),
    ("Souhaitez-vous que votre nom et votre prénom apparaissent sur le site de "
     "la Coop ?", "Visible sur le site",
     "Ils figureraient dans la liste des adhérent·es publiée sur le site de "
     "l'association."),
    ("Souhaitez-vous partager ces informations avec les autres adhérent·es ?",
     "Partage de donnée autorisé",
     "Sinon, les champs ci-dessus restent accessibles uniquement à l'équipe de "
     "gestion de l'association et aux prestataires missionnés."),
]

# Les deux consentements. Texte dans l'Annuaire, liste Oui/Non dans le
# formulaire : on ne demande pas à un adhérent de taper « Oui » à la main.
COLONNES_OUI_NON = ("Visible sur le site", "Partage de donnée autorisé")

CORRESPONDANCE = {libelle: colonne for libelle, colonne, _ in CHAMPS_FORMULAIRE}


def _valeur_utile(valeur):
    """Une réponse qui dit quelque chose. `False` en dit une, `''` non."""
    if valeur is None:
        return False
    if isinstance(valeur, (str, list, dict)):
        return len(valeur) > 0
    return True


def payload_depuis_reponse(champs):
    """Ce qu'une réponse a réellement à dire à la fiche.

    Traduit les libellés du formulaire en noms de colonnes de l'Annuaire. Un
    libellé inconnu est **ignoré** plutôt que recopié tel quel : quelqu'un qui
    ajoute une question dans le formulaire sans la déclarer ici ne doit pas faire
    échouer l'écriture entière des autres réponses — le code n'utilise pas
    `typecast`, et une colonne inexistante suffirait.
    """
    payload = {}
    for libelle, valeur in champs.items():
        if libelle in CHAMPS_TECHNIQUES or not _valeur_utile(valeur):
            continue
        colonne = CORRESPONDANCE.get(libelle)
        if colonne:
            payload[colonne] = valeur
    return payload


def _date_de(reponse):
    """Le jour de la soumission, tel qu'Airtable le donne.

    Aucun champ ne le stocke : `createdTime` accompagne chaque enregistrement.
    Une donnée qu'on n'a pas à tenir est une donnée qui ne peut pas être fausse.
    """
    brut = reponse.get("createdTime")
    if not brut:
        return datetime.now().strftime("%Y-%m-%d")
    return brut[:10]


class Reconciliation:
    """Le passage de réconciliation, sur deux tables de la même base."""

    def __init__(self, annuaire, reponses):
        """
        Args:
            annuaire: AirtableClient branché sur la table Annuaire.
            reponses: AirtableClient branché sur la table « Mise à jour fiche ».
        """
        self.annuaire = annuaire
        self.reponses = reponses

    def a_traiter(self):
        """Les réponses pas encore recopiées."""
        return self.reponses.list_records(
            filter_by_formula="NOT({%s})" % CHAMP_SYNCHRONISE
        )

    def passer(self, dry_run=False):
        """Recopie ce qui attend. Rend les compteurs de la ligne de vie.

        Ne lève jamais : un passage qui plante à la première réponse fautive
        laisserait les suivantes en plan, ce qui est exactement le défaut qu'on
        vient de corriger ailleurs.
        """
        compteurs = {"màj_reçues": 0, "màj_appliquées": 0, "erreurs": 0}
        try:
            reponses = self.a_traiter()
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR,
                          "reconciliation: lecture des réponses impossible (%s)" % e)
            compteurs["erreurs"] += 1
            return compteurs

        compteurs["màj_reçues"] = len(reponses)
        for reponse in reponses:
            try:
                if self._appliquer(reponse, dry_run):
                    compteurs["màj_appliquées"] += 1
                else:
                    compteurs["erreurs"] += 1
            except Exception as e:
                compteurs["erreurs"] += 1
                syslog.syslog(
                    syslog.LOG_ERR,
                    "reconciliation: réponse %s non appliquée (%s) — les suivantes "
                    "sont traitées quand même" % (reponse.get("id"), e),
                )
        return compteurs

    def _appliquer(self, reponse, dry_run):
        champs = reponse.get("fields", {})
        fiche = champs.get(CHAMP_FICHE)
        if not fiche:
            syslog.syslog(
                syslog.LOG_ERR,
                "reconciliation: réponse %s sans %s — elle ne désigne aucune fiche. "
                "Le formulaire doit préremplir ce champ et le masquer."
                % (reponse.get("id"), CHAMP_FICHE),
            )
            return False

        payload = payload_depuis_reponse(champs)
        # Le suivi part avec le reste : une écriture, pas deux. Si elle échoue,
        # la fiche n'est pas marquée à jour et la réponse sera retentée.
        payload[CHAMP_DATE_MAJ] = _date_de(reponse)
        self.annuaire.normaliser_champs(payload)

        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                "[DRY RUN] reconciliation: %s → %s (%d champ(s))"
                % (reponse.get("id"), fiche, len(payload)),
            )
            return True

        if not self.annuaire.update_record(fiche, payload):
            syslog.syslog(
                syslog.LOG_ERR,
                "reconciliation: écriture refusée sur la fiche %s (réponse %s). "
                "La réponse reste non synchronisée et sera retentée."
                % (fiche, reponse.get("id")),
            )
            return False

        if not self.reponses.update_record(reponse["id"], {CHAMP_SYNCHRONISE: True}):
            # La fiche est à jour mais la réponse n'est pas marquée : le passage
            # suivant la rejouera. Réécrire les mêmes valeurs est sans effet,
            # donc ce n'est pas une perte — c'est le sens de l'idempotence ici.
            syslog.syslog(
                syslog.LOG_WARNING,
                "reconciliation: fiche %s mise à jour, mais la réponse %s n'a pas pu "
                "être marquée — elle sera rejouée, sans conséquence"
                % (fiche, reponse["id"]),
            )
        syslog.syslog(
            syslog.LOG_INFO,
            "reconciliation: fiche %s mise à jour depuis la réponse %s (%d champ(s))"
            % (fiche, reponse["id"], len(payload)),
        )
        return True
