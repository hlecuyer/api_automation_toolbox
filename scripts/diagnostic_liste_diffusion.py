#!/usr/bin/env python3
"""Compare une liste de diffusion OVH à sa source Airtable, sans rien modifier.

Écrit le 26/08/2026 après lecture de `mailinglist.log` : 1730 lignes `delete`
pour 30 `add`, et les mêmes seize adresses supprimées de la liste « membres » à
chaque passage du cron depuis des mois — sans jamais disparaître.

Deux questions que le log ne tranche pas, et que ce script tranche :

1. **La suppression prend-elle effet ?** Si les adresses sont encore abonnées
   après un passage, l'appel OVH ne fait rien et le script tourne à vide.
2. **Ces adresses devraient-elles être supprimées ?** Si ce sont des adhérents
   légitimes tombés hors du groupe Airtable, alors le jour où la suppression
   fonctionnera, seize personnes perdront la liste sans que personne ne le voie.

Strictement en lecture : aucun appel d'écriture, ni vers OVH ni vers Airtable.

Usage, sur le serveur, avec les credentials du cron :
    cd /opt/coopdescommuns/api_automation_toolbox
    set -a && . ./.env.mailinglist && set +a
    PYTHONPATH=. venv/bin/python scripts/diagnostic_liste_diffusion.py \
        -c mailinglist-extracter-autosync-conf.json --liste membres
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.mailinglist_extracter import CheckOvhMailinglist, normaliser_email


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--conf", required=True, help="fichier de configuration")
    parser.add_argument("--liste", required=True, help="nom de la liste OVH (ex. membres)")
    args = parser.parse_args()

    app = CheckOvhMailinglist(args.conf)
    conf = app.conf["auto_sync_mailing_list"]

    mailing_list = {"name": args.liste, "domain": conf["ovh_domain"]}
    abonnes_ovh = app.GetOvhMailingListSub(mailing_list)

    tmp = dict(conf)
    tmp["select_field"] = [{"name": conf["mail_field"]}]
    tmp["filter"] = {
        "field": conf["label_field"],
        "value": [args.liste],
        "operation": "=",
    }
    donnees = app.GetAirtableData(tmp)
    attendus = donnees[0] if donnees and donnees[0] else []

    index_ovh = {normaliser_email(e): e for e in abonnes_ovh}
    index_airtable = {normaliser_email(e): e for e in attendus}

    en_trop = sorted(set(index_ovh) - set(index_airtable))
    manquants = sorted(set(index_airtable) - set(index_ovh))

    print(f"\nListe OVH « {args.liste} » : {len(abonnes_ovh)} abonné(s)")
    print(f"Groupe Airtable « {args.liste} » : {len(attendus)} adresse(s)\n")

    if en_trop:
        print(f"⚠️  {len(en_trop)} abonné(s) OVH absent(s) d'Airtable — le script les supprime")
        print("   à chaque passage. S'ils sont encore listés ici après un passage du cron,")
        print("   c'est que l'appel de suppression ne prend pas effet.\n")
        for cle in en_trop:
            print(f"     {index_ovh[cle]}")
    else:
        print("✅ Aucun abonné OVH absent d'Airtable.")

    print()
    if manquants:
        print(f"⚠️  {len(manquants)} adresse(s) Airtable non abonnée(s) — à ajouter\n")
        for cle in manquants:
            print(f"     {index_airtable[cle]}")
    else:
        print("✅ Toutes les adresses Airtable sont abonnées.")

    doublons_casse = [
        cle for cle in index_ovh
        if sum(1 for e in abonnes_ovh if normaliser_email(e) == cle) > 1
    ]
    if doublons_casse:
        print(f"\n⚠️  {len(doublons_casse)} adresse(s) présente(s) plusieurs fois dans OVH "
              "à la casse près.")

    print(f"\nRésumé : {len(en_trop)} en trop, {len(manquants)} manquante(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
