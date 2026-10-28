"""Tests du rapport périodique.

Le rapport ne écrit à personne en simulation et ses comptes décident de ce
qu'un opérateur croira. Ce qui est vérifié ici : les comptes par fenêtre de
dates, les anomalies dites au lieu d'être cachées (adhésion sans mail de
bienvenue, réponses orphelines), et le rapport rendu lisible.
"""

from datetime import date

from scripts.rapport_hebdo import (_jour, compter_volumetries, etat_mailinglist,
                                   lire_passages_syslog, rendre_rapport)

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
        fiche("rec1", "2026-10-08", **{"Nouvel adhérent": "Oui",
                                       "Lien envoyé le": "2026-10-08"}),
        fiche("rec2", "2026-10-01", **{"Nouvel adhérent": "Oui"}),  # avant la fenêtre
        fiche("rec3", "2026-10-13", **{"Nouvel adhérent": "Oui",
                                       "Fiche mise à jour le": "2026-10-13",
                                       "Dernière relance le": "2026-10-12"}),
        fiche("rec4", "2026-10-09"),  # saisie manuelle : hors flux, pas une adhésion
    ])
    assert comptes["adhesions"] == 2
    assert comptes["hors_flux"] == 1
    assert comptes["liens_envoyes"] == 1
    assert comptes["fiches_maj"] == 1
    assert comptes["relances"] == 1
    assert comptes["total_fiches"] == 4


def test_les_dates_iso_completes_sont_comprises():
    comptes = compter([
        fiche("rec1", "2026-10-08T14:30:00.000Z", **{"Nouvel adhérent": "Oui"}),
    ])
    assert comptes["adhesions"] == 1


def test_une_adhesion_sans_lien_est_dite_anomalie():
    comptes = compter([
        fiche("rec1", "2026-10-08"),  # saisie manuelle : pas une adhésion
        fiche("rec2", "2026-10-08", **{"Nouvel adhérent": "Oui"}),
    ])
    rapport = rendre_rapport(comptes, {}, False, DEBUT, FIN, AUJOURDHUI)
    assert "1 adhésion(s) sans mail de bienvenue : adherent@example.org" in rapport
    assert "n'est pas parti" not in rapport # l'ancienne comparaison de totaux


def test_une_saisie_manuelle_nest_pas_une_adhesion():
    comptes = compter([fiche("rec1", "2026-10-08")])  # pas de tampon du flux
    assert comptes["adhesions"] == 0
    assert comptes["hors_flux"] == 1
    assert comptes["hors_flux_adresses"] == ["adherent@example.org"]
    rapport = rendre_rapport(comptes, {}, False, DEBUT, FIN, AUJOURDHUI)
    assert "Fiches créées hors flux : 1" in rapport
    assert "sans mail de bienvenue" not in rapport


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


def test_les_adresses_sont_listees_par_categorie():
    annuaire = [
        fiche("rec1", "2026-10-08", **{"Nouvel adhérent": "Oui",
                                       "E-mail": "nouveau@example.org"}),
        fiche("rec2", "2026-10-09", **{"Nouvel adhérent": "Non",
                                       "E-mail": "retour@example.org"}),
    ]
    comptes = compter(annuaire)
    assert comptes["adhesions_details"] == [
        {"email": "nouveau@example.org", "nouveau": "Oui"},
        {"email": "retour@example.org", "nouveau": "Non"},
    ]
    rapport = rendre_rapport(comptes, {}, False, DEBUT, FIN, AUJOURDHUI)
    assert "nouveaux adhérents : nouveau@example.org" in rapport
    assert "réadhésions : retour@example.org" in rapport


def test_le_rendu_html_porte_les_listes_et_la_signature():
    from scripts.rapport_hebdo import rendre_rapport_html
    annuaire = [
        fiche("rec1", "2026-10-08", **{"Nouvel adhérent": "Oui",
                                       "E-mail": "nouveau@example.org"}),
    ]
    comptes = compter(annuaire)
    html = rendre_rapport_html(comptes, {}, False, DEBUT, FIN, AUJOURDHUI)
    assert "nouveau@example.org" in html
    assert "Nouveaux adhérents" in html
    assert '<img width="85" height="69" src="cid:logo"' in html
    assert "@@SIG_" not in html


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
        "mailinglist": {"derniere": None, "erreurs": 0, "derniere_ligne": None,
                        "derniere_erreur": None, "ligne_erreur": None},
    }
    rapport = rendre_rapport(comptes, passages, True, DEBUT, FIN, AUJOURDHUI)
    assert "relance_fiche : AUCUN passage" in rapport
    assert "hello_asso_sync : dernier passage le Oct 13 20:58:01" in rapport


def test_un_passage_mailinglist_reussi_n_est_pas_un_echec():
    # Le défaut signalé le 26/10/2026 : l'extracter journalise « passage
    # terminé statut=ok » et le rapport l'affichait « échec le … ».
    entree = {"derniere": "2026-10-28 12:37:04", "erreurs": 0,
              "derniere_ligne": "mailinglist_extracter: passage terminé "
                                "statut=ok listes=24 ajouts=12 suppressions=3 "
                                "erreurs=0",
              "derniere_erreur": None, "ligne_erreur": None}
    assert etat_mailinglist(entree) == (
        "dernier passage le 2026-10-28 12:37:04, statut ok "
        "(12 ajouts, 3 suppressions, 0 erreur)")
    assert "échec" not in etat_mailinglist(entree)


def test_un_passage_mailinglist_en_echec_reste_un_echec():
    entree = {"derniere": "2026-10-28 18:37:04", "erreurs": 0,
              "derniere_ligne": "mailinglist_extracter: passage terminé "
                                "statut=échec listes=0 ajouts=0 suppressions=0 "
                                "erreurs=0",
              "derniere_erreur": None, "ligne_erreur": None}
    assert etat_mailinglist(entree).startswith("échec le 2026-10-28 18:37:04")


def test_une_erreur_unitaire_ne_se_cache_pas_sous_un_passage_vert():
    entree = {"derniere": "2026-10-28 18:37:04", "erreurs": 1,
              "derniere_ligne": "mailinglist_extracter: passage terminé "
                                "statut=ok listes=24 ajouts=0 suppressions=0 "
                                "erreurs=1",
              "derniere_erreur": "2026-10-28 18:37:02",
              "ligne_erreur": "ERROR: add toto@example.org on listes refused "
                              "by OVH — other subscribers are still processed"}
    resume = etat_mailinglist(entree)
    assert "statut ok" in resume
    assert "1 erreur(s) unitaire(s)" in resume
    assert "toto@example.org" in resume


def test_les_dates_dehors_ne_comptent_pas():
    assert _jour("2026-10-13") == AUJOURDHUI
    assert _jour("2026-10-13T10:00:00.000Z") == AUJOURDHUI
    assert _jour("") is None
    assert _jour(None) is None
    assert _jour("pas une date") is None


def test_les_deux_formats_de_syslog_se_lisent(tmp_path):
    # Mesuré sur la prod le 26/10/2026 : rsyslog écrit en RFC 3339, le rapport
    # ne lisait que le format classique et disait « syslog non lisible ».
    chemin = tmp_path / "syslog"
    lignes = [
        # hors fenêtre : une erreur d'un mois passé ne doit pas être comptée
        "2026-09-30T18:58:06.000000+00:00 dsi hello_asso_sync.py: "
        "hello_asso_sync: passage terminé statut=ok vues=87 traitées=0 erreurs=9 "
        "non_rattachés=0 curseur=2026-09-30T20:58:02\n",
        "2026-10-12T18:58:06.641851+00:00 dsi hello_asso_sync.py: "
        "hello_asso_sync: passage terminé statut=ok vues=87 traitées=1 erreurs=0 "
        "non_rattachés=0 curseur=2026-10-12T20:58:02\n",
        "Oct 12 10:23:06 dsi relancer_fiches.py: relance_fiche: "
        "relances_dues=1 relances_envoyées=1 erreurs=2\n",
        "2026-10-13T09:37:01.000000+00:00 dsi mailinglist_extracter.py: "
        "mailinglist: échec de synchronisation d'une liste\n",
    ]
    chemin.write_text("".join(lignes), encoding="utf-8")
    lisible, passages = lire_passages_syslog(DEBUT, FIN, chemins=(str(chemin),))
    assert lisible
    assert passages["hello_asso_sync"]["derniere"] == "2026-10-12 18:58:06"
    assert passages["hello_asso_sync"]["erreurs"] == 0  # la ligne hors fenêtre ignorée
    assert passages["relance_fiche"]["derniere"] == "Oct 12 10:23:06"
    assert passages["relance_fiche"]["erreurs"] == 2
    assert "échec de synchronisation" in passages["mailinglist"]["ligne_erreur"]
    assert passages["mailinglist"]["derniere"] is None  # aucune ligne de vie dans le lot


def test_le_fichier_ancien_n_ecrase_pas_le_courant(tmp_path):
    # Le 28/10/2026, le rapport en simulation annonçait « dernier passage le
    # 24/10 » alors que le cron avait tourné à 12:37 le jour même : /var/log/syslog
    # puis /var/log/syslog.1 étaient lus dans cet ordre, et le fichier de la
    # rotation (le plus ancien) écrasait le courant.
    courant = tmp_path / "syslog"
    courant.write_text(
        "2026-10-13T18:37:28.000000+01:00 dsi mailinglist_extracter.py: "
        "mailinglist_extracter: passage terminé statut=ok listes=30 ajouts=0 "
        "suppressions=12 erreurs=0\n", encoding="utf-8")
    ancien = tmp_path / "syslog.1"
    ancien.write_text(
        "2026-10-09T18:37:28.000000+01:00 dsi mailinglist_extracter.py: "
        "mailinglist_extracter: passage terminé statut=ok listes=30 ajouts=0 "
        "suppressions=13 erreurs=0\n", encoding="utf-8")

    # Ordre de lecture du code : le courant d'abord, le reste ensuite.
    _, passages = lire_passages_syslog(
        DEBUT, FIN, chemins=(str(courant), str(ancien)))
    assert passages["mailinglist"]["derniere"] == "2026-10-13 18:37:28"
    assert "suppressions=12" in passages["mailinglist"]["derniere_ligne"]

    # Et l'ordre inverse ne change rien : la date la plus récente gagne.
    _, passages = lire_passages_syslog(
        DEBUT, FIN, chemins=(str(ancien), str(courant)))
    assert passages["mailinglist"]["derniere"] == "2026-10-13 18:37:28"


def test_un_syslog_introuvable_reste_silencieux(tmp_path):
    lisible, passages = lire_passages_syslog(
        DEBUT, FIN, chemins=(str(tmp_path / "absent"),))
    assert not lisible
    assert all(p["derniere"] is None for p in passages.values())
