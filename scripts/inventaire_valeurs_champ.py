#!/usr/bin/env python3
"""Liste les valeurs distinctes d'un champ Airtable, avec leur nombre d'occurrences.

Sert à décider avant de normaliser : on ne peut pas choisir un référentiel sans
savoir ce que la base contient réellement. `extract_airtable_schema.py` montre les
champs et un enregistrement d'exemple ; celui-ci balaie toute la table.

Le regroupement par forme canonique (sans casse, sans accent, sans espaces) est
ce qui rend le résultat lisible : il montre d'un coup quelles écritures désignent
la même chose, et combien de fiches chacune représente.

Usage :
    .venv/bin/python scripts/inventaire_valeurs_champ.py Genre
    .venv/bin/python scripts/inventaire_valeurs_champ.py "Cotisation LCDC" --seuil 5

⚠️ La sortie contient les valeurs du champ. Sur un champ nominatif (E-mail,
Téléphone), elle contient donc des données personnelles : ne pas la coller
ailleurs sans y penser.
"""

import argparse
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.clients.airtable_client import AirtableClient, _cle_normalisee

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("champ", help="nom exact du champ Airtable")
    parser.add_argument(
        "--table", default=os.getenv("AIRTABLE_TABLE_NAME", "Annuaire"),
        help="table à balayer (défaut : Annuaire)",
    )
    parser.add_argument(
        "--seuil", type=int, default=0,
        help="ne montrer que les valeurs vues au moins N fois",
    )
    parser.add_argument(
        "--base",
        help="identifiant de base Airtable (défaut : AIRTABLE_BASE_ID du .env). "
             "Le .env porte plusieurs bases et le code n'en lit qu'une : passer "
             "l'identifiant explicitement évite d'inventorier la mauvaise.",
    )
    args = parser.parse_args()

    api_key = os.getenv("AIRTABLE_API_KEY")
    base_id = args.base or os.getenv("AIRTABLE_BASE_ID")
    if not api_key or not base_id:
        print(
            "AIRTABLE_API_KEY ou AIRTABLE_BASE_ID absent de l'environnement.\n"
            "Renseigner le .env (voir docs/CREDENTIALS_GUIDE.md).",
            file=sys.stderr,
        )
        return 1

    client = AirtableClient(api_key=api_key, base_id=base_id, table_name=args.table)

    print(f"Balayage de « {args.table} » dans la base {base_id}…")
    records = client.list_records()
    print(f"{len(records)} enregistrement(s).\n")

    occurrences = Counter()
    vides = 0
    for record in records:
        valeur = record.get("fields", {}).get(args.champ)
        if valeur is None or valeur == "":
            vides += 1
            continue
        if isinstance(valeur, list):
            for element in valeur:
                occurrences[str(element)] += 1
        else:
            occurrences[str(valeur)] += 1

    if not occurrences:
        print(f"Aucune valeur pour « {args.champ} ». Nom de champ exact ?")
        return 1

    # Regrouper les écritures qui désignent la même chose.
    familles = defaultdict(list)
    for valeur, nombre in occurrences.items():
        familles[_cle_normalisee(valeur)].append((valeur, nombre))

    renseignees = sum(occurrences.values())
    print(f"Champ « {args.champ} » — {renseignees} valeur(s) renseignée(s), {vides} vide(s)")
    print(f"{len(occurrences)} écriture(s) distincte(s), {len(familles)} forme(s) canonique(s)\n")

    for cle, variantes in sorted(
        familles.items(), key=lambda f: -sum(n for _, n in f[1])
    ):
        total = sum(n for _, n in variantes)
        if total < args.seuil:
            continue
        marque = "  ⚠️ " if len(variantes) > 1 else "     "
        print(f"{marque}{cle or '(vide)'} — {total} fiche(s)")
        for valeur, nombre in sorted(variantes, key=lambda v: -v[1]):
            print(f"        {valeur!r} : {nombre}")

    print()
    doublons = {c: v for c, v in familles.items() if len(v) > 1}
    if doublons:
        touchees = sum(n for v in doublons.values() for _, n in v)
        print(
            f"⚠️  {len(doublons)} forme(s) écrite(s) de plusieurs façons "
            f"(casse, accent ou espace), {touchees} fiche(s) concernée(s)."
        )

    espaces = [v for v in occurrences if v != v.strip()]
    if espaces:
        print(
            f"⚠️  {len(espaces)} valeur(s) avec un espace en trop : "
            + ", ".join(repr(v) for v in espaces)
        )
        print("   Un filtre Airtable en correspondance exacte les rate.")

    # Ce que ce script ne peut PAS trancher, et qu'il ne faut pas laisser croire
    # résolu : `H` et `Masculin` sont deux formes canoniques distinctes et
    # pourtant la même réponse. Aucun regroupement mécanique ne reconnaît des
    # synonymes. Annoncer « rien à normaliser » parce que chaque forme n'a qu'une
    # écriture serait un faux négatif sur exactement le bug qu'on traque.
    if len(familles) > 1:
        print(
            f"❓ {len(familles)} formes distinctes sur ce champ. Si certaines sont des "
            "synonymes\n"
            "   (`H` et `Masculin`, `Payé 2025` et `Payé 2026` non), c'est une décision "
            "humaine :\n"
            "   le script ne reconnaît que les variantes d'écriture, jamais le sens."
        )
    else:
        print("✅ Une seule forme sur ce champ.")

    total = len(records)
    if total and vides / total > 0.5:
        print(
            f"\n📉 {vides} fiche(s) sur {total} sans valeur ({vides * 100 // total} %). "
            "Un champ majoritairement vide\n"
            "   ne porte pas de statistique fiable : à verser au débat sur son usage."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
