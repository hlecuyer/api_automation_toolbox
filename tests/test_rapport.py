"""Tests du rapport périodique.

Le rapport ne écrit à personne en simulation et ses comptes décident de ce
qu'un opérateur croira. Ce qui est vérifié ici : les comptes par fenêtre de
dates, les anomalies dites au lieu d'être cachées (adhésion sans mail de
bienvenue, réponses orphelines), et le rapport rendu lisible.
"""

from datetime import date

from scripts.rapport_hebdo import (_jour, compter_volumetries, rendre_rapport)

AUJOURDHUI = date(2026, 10, 13)
DEBUT = date(2026, 10, 7)
FIN = AUJOURDHUI


def fiche(ident, creation, **extra):
    champs = {CHAMP: valeur for CHAMP, valeur in {
        "Date de création": creation,
        "E-mail": "adherent@example.org",
    }.items()}
    champs.update(extra)
    return {"id": ident, "fields": champs}


class FauxTable:
    def __init__(self, lignes):
        self.lignes = lignes

    def list_records(self, **_):
        return self.lignes


def compter(annuaire, reponses=None, id_groupe=None):
    return compter_volumetries(
        FauxTable(annuaire), FauxTable(reponses or []), id_groupe, DEBUT, FIN, AUJOURDHUI)


def test_la_fenetre_compte_par_date():
    comptes = compter([
        fiche("rec1", "2026-10-08", **{"Lien envoyé le": "2026-10-08"}),
        fiche("rec2", "2026-10-01"),  # avant la fenêtre
        fiche("rec3", "2026-10-13", **{"Fiche mise à jour le": "2026-10-13",
                                       "Dernière relance le": "2026-10-12"}),
    ])
    assert comptes["adhesions"] == 2
    assert comptes["liens_envoyes"] == 1
    assert comptes["fiches_maj"] == 1
    assert comptes["relances"] == 1
    assert comptes["total_fiches"] == 3


def test_les_dates_iso_completes_sont_comprises():
    comptes = compter([
        fiche("rec1", "2026-10-08T14:30:00.000Z"),
    ])
    assert comptes["adhesions"] == 1


def test_une_adhesion_sans_lien_est_dite_anomalie():
    comptes = compter([fiche("rec1", "2026-10-08")])
    rapport = rendre_rapport(comptes, {}, False, DEBUT, FIN, AUJOURDHUI)
    assert "un mail de bienvenue n'est pas parti" in rapport


def test_une_reponse_orpheline_est_dite_anomalie():
    annuaire = [fiche("rec1", "2026-10-08")]
    orpheline = {"id": "recR1", "fields": {"record_id": "recSUPPRIMEE",
                                           "Synchronisé": True}}
    comptes = compter(annuaire, reponses=[orpheline])
    assert comptes["orphelines"] == 1
    rapport = rendre_rapport(comptes, {}, False, DEBUT, FIN, AUJOURDHUI)
    assert "sans fiche derrière" in rapport


def test_la_reponse_non_synchronisee_est_comptee_en_attente():
    annuaire = [fiche("rec1", "2026-10-08")]
    reponse = {"id": "recR1", "fields": {"record_id": "rec1", "Synchronisé": False}}
    comptes = compter(annuaire, reponses=[reponse])
    assert comptes["reponses_en_attente"] == 1
    rapport = rendre_rapport(comptes, {}, False, DEBUT, FIN, AUJOURDHUI)
    assert "pas encore recopiée" in rapport


def test_fiche_a_relancer_compte_en_attente():
    comptes = compter([
        fiche("rec1", "2026-09-01", **{"Lien envoyé le": "2026-09-01"}),  # J+42
        fiche("rec2", "2026-10-08", **{"Lien envoyé le": "2026-10-08"}),  # trop tôt
        fiche("rec3", "2026-09-01", **{"Lien envoyé le": "2026-09-01",
                                       "Fiche mise à jour le": "2026-10-01"}),  # à jour
        fiche("rec4", "2026-09-01", **{"Lien envoyé le": "2026-09-01",
                                       "désinscrit liste membres": True}),  # désinscrite
    ])
    assert comptes["a_relancer"] == 1


def test_la_repartition_distingue_nouveau_et_readhesion():
    comptes = compter([
        fiche("rec1", "2026-10-08", **{"Nouvel adhérent": "Oui"}),
        fiche("rec2", "2026-10-09", **{"Nouvel adhérent": "Non"}),
    ])
    assert comptes["repartition_adhesions"] == {"Oui": 1, "Non": 1}


def test_le_groupe_ne_compte_que_ses_membres():
    annuaire = [
        fiche("rec1", "2026-10-08", **{"Groupe(s)": ["recG"]}),
        fiche("rec2", "2026-10-08"),
    ]
    comptes = compter_volumetries(
        FauxTable(annuaire), FauxTable([]), "recG", DEBUT, FIN, AUJOURDHUI)
    assert comptes["dans_groupe"] == 1


def test_syslog_absent_est_dit_et_pas_caché():
    comptes = compter([])
    rapport = rendre_rapport(comptes, {}, False, DEBUT, FIN, AUJOURDHUI)
    assert "syslog non lisible" in rapport
    assert "AUCUN passage" not in rapport


def test_un_composant_muet_est_flagge_quand_le_syslog_est_lu():
    comptes = compter([])
    passages = {
        "hello_asso_sync": {"derniere": "Oct 13 20:58:01", "erreurs": 0,
                            "derniere_ligne": "hello_asso_sync: passage terminé"},
        "relance_fiche": {"derniere": None, "erreurs": 0, "derniere_ligne": None},
        "mailinglist": {"derniere": None, "erreurs": 0, "derniere_ligne": None},
    }
    rapport = rendre_rapport(comptes, passages, True, DEBUT, FIN, AUJOURDHUI)
    assert "relance_fiche : AUCUN passage" in rapport
    assert "hello_asso_sync : dernier passage le Oct 13 20:58:01" in rapport


def test_les_dates_dehors_ne_comptent_pas():
    assert _jour("2026-10-13") == AUJOURDHUI
    assert _jour("2026-10-13T10:00:00.000Z") == AUJOURDHUI
    assert _jour("") is None
    assert _jour(None) is None
    assert _jour("pas une date") is None
