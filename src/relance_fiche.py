"""Relance les adhérents qui n'ont pas mis leur fiche à jour.

L'adhésion et la mise à jour de fiche sont séparées dans le temps : l'adhérent
paie, reçoit son mail de bienvenue avec un lien, et remplit le formulaire plus
tard — ou jamais. La table `Ajout à un groupe` de la base porte le même motif,
construit en 2022 sans relance : **8 lignes en trois ans**. La relance n'est pas
un confort, c'est la moitié manquante du dispositif.

Trois envois, à J+15, J+30 et J+60. Au-delà, plus rien : quelqu'un qui n'a pas
répondu trois fois a répondu.

**L'ancrage est `Lien envoyé le`, pas la date d'adhésion.** Ça mérite une
explication, parce que le champ `Date d'adhésion` de l'`Annuaire` existe et
semble fait pour ça : il est de type `lastModifiedTime`. Il ne dit pas quand
quelqu'un a adhéré, il dit quand sa fiche a bougé pour la dernière fois — la
réconciliation elle-même le remet à zéro. Compter les jours dessus aurait donné
des relances qui ne partent jamais, ou qui repartent indéfiniment.

`Lien envoyé le` dit exactement ce qu'on veut compter : le jour où l'adhérent a
reçu le lien. Pas de lien envoyé, pas de relance — ce qui est correct, on ne
relance pas quelqu'un sur un message qu'il n'a pas reçu.

**Le nombre de relances ne se compte pas, il se déduit.** Deux dates suffisent :
`Lien envoyé le` et `Dernière relance le`. Un compteur se désynchronise dès qu'un
passage échoue à mi-course ; deux dates, non. Et le palier dû étant le plus grand
palier atteint, un cron resté muet trois semaines rattrape au lieu de sauter.

Les garde-fous, parce que ce sont de vraies personnes :

- **simulation par défaut**, envoi réel seulement sur demande explicite ;
- **`désinscrit liste membres` exclut sans exception**, vérifié deux fois : dans
  la formule de sélection et à nouveau sur chaque fiche. Une ceinture vaut mieux
  qu'une clause de `WHERE` qu'un jour quelqu'un modifie ;
- **pas de lien, pas de relance** — un rappel qui ne mène nulle part est pire que
  pas de rappel ;
- **une limite d'envois** par passage, pour qu'une erreur de sélection ne se
  traduise pas en mille mails ;
- **le garde-fou d'envoi de `OVHEmailClient`** reste en travers du chemin : hors
  production, rien ne part.
"""

import syslog
from datetime import date, datetime, timedelta

from src.lien_formulaire import CHAMP_LIEN, CHAMP_LIEN_ENVOYE
from src.reconciliation import CHAMP_DATE_MAJ

PALIERS = (15, 30, 60)

CHAMP_DERNIERE_RELANCE = "Dernière relance le"
CHAMP_DESINSCRIT = "désinscrit liste membres"
CHAMP_ADRESSE = "E-mail"
CHAMP_PRENOM = "Prénom"

# Les fiches candidates : lien envoyé, fiche pas encore mise à jour, pas
# désinscrite. Le tri fin (palier dû, relance déjà partie) se fait ensuite en
# Python — une formule Airtable qui saurait tout ça serait illisible, donc
# fausse un jour sans que personne ne s'en aperçoive.
FORMULE_CANDIDATES = (
    "AND({%s}!='', {%s}='', NOT({%s}))"
    % (CHAMP_LIEN_ENVOYE, CHAMP_DATE_MAJ, CHAMP_DESINSCRIT)
)


def _jour(valeur):
    """Une date Airtable ramenée à un `date`, ou `None`."""
    if not valeur:
        return None
    try:
        return datetime.strptime(str(valeur)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def palier_du(envoye_le, aujourdhui):
    """Le plus grand palier atteint, ou `None` avant le premier.

    Le plus grand et non le plus proche : un cron resté muet trois semaines doit
    rattraper la relance qu'il a manquée, pas la sauter.
    """
    if not envoye_le:
        return None
    jours = (aujourdhui - envoye_le).days
    atteints = [p for p in PALIERS if jours >= p]
    return max(atteints) if atteints else None


def a_relancer(champs, aujourdhui):
    """Le palier à envoyer pour cette fiche, ou `None`.

    Rend `None` dès qu'une raison de ne pas écrire existe. Les raisons sont
    volontairement redondantes avec la formule de sélection : c'est la même
    règle, écrite deux fois, parce qu'une seule des deux peut être modifiée par
    erreur.
    """
    if champs.get(CHAMP_DESINSCRIT):
        return None
    if champs.get(CHAMP_DATE_MAJ):
        return None
    if not champs.get(CHAMP_ADRESSE) or not champs.get(CHAMP_LIEN):
        return None

    envoye_le = _jour(champs.get(CHAMP_LIEN_ENVOYE))
    palier = palier_du(envoye_le, aujourdhui)
    if palier is None:
        return None

    # Déjà relancé pour ce palier ? La question se pose en dates, jamais en
    # nombre d'envois.
    derniere = _jour(champs.get(CHAMP_DERNIERE_RELANCE))
    if derniere and derniere >= envoye_le + timedelta(days=palier):
        return None
    return palier


class Relance:
    """Un passage de relance sur l'`Annuaire`."""

    def __init__(self, annuaire, envoyer, aujourdhui=None):
        """
        Args:
            annuaire: AirtableClient branché sur la table Annuaire.
            envoyer: `(destinataire, prénom, lien, palier) -> bool`. Injectée
                plutôt qu'appelée en direct : ce module ne construit pas de
                client mail, donc un test n'a aucun moyen d'en envoyer un par
                mégarde.
            aujourdhui: le jour de référence, pour les tests.
        """
        self.annuaire = annuaire
        self.envoyer = envoyer
        self.aujourdhui = aujourdhui or date.today()

    def candidates(self):
        return self.annuaire.list_records(filter_by_formula=FORMULE_CANDIDATES)

    def passer(self, dry_run=True, limite=None, test=None):
        """Relance ce qui est dû. Rend les compteurs de la ligne de vie.

        Args:
            dry_run: par défaut, rien n'est envoyé ni écrit.
            limite: nombre maximum d'envois pour ce passage.
            test: adresse qui reçoit à la place des adhérents. Dans ce mode la
                fiche n'est **pas** marquée relancée : l'adhérent n'a rien reçu,
                le dire serait un mensonge que personne ne viendrait corriger.
        """
        compteurs = {"relances_dues": 0, "relances_envoyées": 0, "erreurs": 0}
        try:
            fiches = self.candidates()
        except Exception as e:
            syslog.syslog(syslog.LOG_ERR,
                          "relance: lecture de l'Annuaire impossible (%s)" % e)
            compteurs["erreurs"] += 1
            return compteurs

        for fiche in fiches:
            champs = fiche.get("fields", {})
            palier = a_relancer(champs, self.aujourdhui)
            if palier is None:
                continue
            compteurs["relances_dues"] += 1
            if limite is not None and compteurs["relances_envoyées"] >= limite:
                continue
            try:
                if self._relancer(fiche, champs, palier, dry_run, test):
                    compteurs["relances_envoyées"] += 1
                else:
                    compteurs["erreurs"] += 1
            except Exception as e:
                compteurs["erreurs"] += 1
                syslog.syslog(
                    syslog.LOG_ERR,
                    "relance: fiche %s non relancée (%s) — les suivantes le sont "
                    "quand même" % (fiche.get("id"), e),
                )
        return compteurs

    def _relancer(self, fiche, champs, palier, dry_run, test):
        destinataire = test or champs[CHAMP_ADRESSE]
        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                "[DRY RUN] relance: J+%d à %s (fiche %s)"
                % (palier, destinataire, fiche["id"]),
            )
            return True

        if not self.envoyer(destinataire, champs.get(CHAMP_PRENOM),
                            champs[CHAMP_LIEN], palier):
            syslog.syslog(
                syslog.LOG_ERR,
                "relance: envoi J+%d refusé pour la fiche %s — elle reste à "
                "relancer" % (palier, fiche["id"]),
            )
            return False

        if test:
            # Rien n'est écrit : la fiche doit rester exactement où elle en
            # était, sinon un essai consomme une relance de quelqu'un d'autre.
            syslog.syslog(syslog.LOG_INFO,
                          "relance: essai J+%d vers %s, fiche %s non marquée"
                          % (palier, destinataire, fiche["id"]))
            return True

        if not self.annuaire.update_record(
                fiche["id"], {CHAMP_DERNIERE_RELANCE: self.aujourdhui.isoformat()}):
            # Le mail est parti mais la date n'est pas posée : le passage suivant
            # renverra la même relance. Un doublon vaut mieux qu'un silence, mais
            # ça doit se voir tout de suite.
            syslog.syslog(
                syslog.LOG_ERR,
                "relance: J+%d envoyée à %s mais « %s » non écrite sur la fiche %s "
                "— elle sera renvoyée au prochain passage"
                % (palier, destinataire, CHAMP_DERNIERE_RELANCE, fiche["id"]),
            )
            return True

        syslog.syslog(
            syslog.LOG_INFO,
            "relance: J+%d envoyée à %s (fiche %s)" % (palier, destinataire, fiche["id"]),
        )
        return True
