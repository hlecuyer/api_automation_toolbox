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


def _valeur_utile(valeur):
    """Une réponse qui dit quelque chose. `False` en dit une, `''` non."""
    if valeur is None:
        return False
    if isinstance(valeur, (str, list, dict)):
        return len(valeur) > 0
    return True


def payload_depuis_reponse(champs):
    """Ce qu'une réponse a réellement à dire à la fiche.

    Le rapprochement est une **identité** : la table de réponses a été dérivée
    du schéma de l'Annuaire, colonne par colonne, options comprises. Il n'y a
    donc pas de table de correspondance à tenir, et donc pas de table de
    correspondance qui puisse diverger. C'est tout l'intérêt d'avoir généré la
    table plutôt que de l'avoir saisie.
    """
    return {
        nom: valeur
        for nom, valeur in champs.items()
        if nom not in CHAMPS_TECHNIQUES and _valeur_utile(valeur)
    }


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
