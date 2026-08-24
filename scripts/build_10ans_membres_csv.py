#!/usr/bin/env python3
"""Construit le CSV des destinataires de la campagne "10 ans membres".

Fusionne 3 sources sans doublons (clé = email lower-case) :
1. scripts/data/Annuaire-Membres 10 ans.csv  (priorité 1, Genre fiable)
2. scripts/data/2025_0701 Rencontre Com Numerique-Inscrits.csv  (priorité 2)
3. scripts/data/partenaire_invit.md  (priorité 3, format texte libre)

Output: scripts/data/10ans_membres_perso.csv (cols: mail,prenom,cher_chere)
"""

import csv
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
ANNUAIRE = DATA_DIR / "Annuaire-Membres 10 ans.csv"
INSCRITS = DATA_DIR / "2025_0701 Rencontre Com Numerique-Inscrits.csv"
PARTENAIRES = DATA_DIR / "partenaire_invit.md"
# Liste des destinataires déjà invités (campagne intervenants) — exclus du
# nouveau CSV pour éviter les doubles invitations.
ALREADY_INVITED = DATA_DIR / "10ans_intervenants_perso-VV.csv"
OUTPUT = DATA_DIR / "10ans_membres_perso.csv"

# Validation: TLD ≥ 2 chars, partie locale + domaine non vides
EMAIL_RE = re.compile(r"[\w\.\+\-]+@[\w\.\-]+\.[A-Za-z]{2,}")
# Permet de détecter un email dans une ligne (tolère <>, ;, etc. autour)
EMAIL_FINDALL_RE = re.compile(r"[\w\.\+\-]+@[\w\.\-]+\.[A-Za-z]{2,}")
DEJA_INCLUS_RE = re.compile(r"\bd[ée]j[àa]\s+inclus(?:e|es)?\b", re.IGNORECASE)


def normalize_email(email: str) -> str:
    """Strip whitespace + brackets + trailing punctuation, fix Unicode hyphens."""
    email = email.strip().strip("<>").strip(";,. ")
    # Remplace les hyphens Unicode par des - ASCII (cas tiers‑lieux.fr)
    email = email.replace("‑", "-").replace("‐", "-")
    return email


def is_valid_email(email: str) -> bool:
    """Validation stricte : doit matcher EMAIL_RE en entier."""
    if not email:
        return False
    m = EMAIL_RE.fullmatch(email)
    return m is not None


def titlecase_name(name: str) -> str:
    """Titlecase un nom en respectant les hyphens et apostrophes (Marie-Charlotte)."""
    if not name:
        return name
    # Normalise puis titlecase mot par mot (split sur espaces, hyphens, apostrophes conservés)
    parts = re.split(r"(\s+|-|')", name.strip())
    return "".join(p.capitalize() if not re.match(r"\s+|-|'", p) else p for p in parts)


def map_genre_to_cher_chere(genre: str) -> tuple[str, str]:
    """Mappe la colonne Genre vers (cher_chere, origin).

    origin ∈ {"explicit_binary", "explicit_nb", "missing"} :
      - explicit_binary : F/H/Féminin/Masculin → Cher/Chère verrouillé
      - explicit_nb     : Non-précisé/Autre → Cher·ère verrouillé (NE PAS override)
      - missing         : vide → Cher·ère, peut être affiné par heuristique prénom
    """
    g = (genre or "").strip().lower()
    if g in ("féminin", "f"):
        return "Chère", "explicit_binary"
    if g in ("masculin", "h", "m"):
        return "Cher", "explicit_binary"
    if g in ("non-précisé", "non précisé", "autre"):
        return "Cher·ère", "explicit_nb"
    return "Cher·ère", "missing"


# Heuristique prénom → cher/chère pour les sources sans Genre fiable.
# Liste curée pour la campagne 10 ans (couvre la majorité des prénoms du CSV).
# Les prénoms non listés OU ambigus restent "Cher·ère".
PRENOMS_FEMININS = {
    "adeline", "adelphe", "agathe", "agnès", "agnes", "alice", "alima",
    "amandine", "amelie", "amélie", "angèle", "angele", "anita", "anne",
    "anne-louise", "anne-marie", "anne-sophie", "anne-laure", "anthéa",
    "anthea", "antoinette", "armelle", "aude", "audrey", "awa",
    "barbara", "béatrice", "beatrice", "bénédicte", "benedicte",
    "brigitte", "capucine", "carine", "caroline", "catherine", "cécile",
    "cecile", "celine", "céline", "cerise", "chantal", "charline",
    "charlotte", "chloé", "chloe", "christèle", "christele", "christelle",
    "christine", "claire", "clara", "clémence", "clemence",
    "constance", "corinne", "cristina", "danielle", "daniela",
    "delphine", "diane", "dorothée", "dorothee", "édith", "edith",
    "eléa", "elea", "éléonore", "eleonore", "elise", "élise",
    "elisabeth", "élisabeth", "emanuela", "emilie", "émilie",
    "emma", "emmanuelle", "erdmuthe", "estelle", "eve", "ève",
    "evelyne", "fabienne", "fanny", "fatima", "flora", "flore",
    "florence", "françoise", "francoise", "frédérique", "frederique",
    "gabriela", "gaële", "gaele", "gaëlle", "gaelle", "gaïa", "gaia",
    "geneviève", "genevieve", "gisèle", "gisele", "gwenaelle", "gwenaëlle",
    "héloïse", "heloise", "hélène", "helene", "hortense",
    "ianira", "inès", "ines", "irène", "irene", "irwina",
    "isabelle", "jamila", "jacqueline", "jeanne", "jocelyne", "joëlle",
    "joelle", "josiane", "judith", "julie", "juliette",
    "karine", "kathy", "laetitia", "laura", "laure", "laurence",
    "léa", "lea", "léonore", "leonore", "lorreine", "louisa", "louise",
    "lucie", "ludivine", "lydie", "lysiane",
    "madeleine", "magali", "manon", "marguerite", "maïa", "maia",
    "marianne", "marie", "marie-charlotte", "marie-laure",
    "marie-pierre", "marie-claude", "marie-france", "marielle",
    "marion", "marina", "martine", "mathilde", "maud", "maxine",
    "maya", "maëva", "maeva", "marylène", "marylene", "mélanie",
    "melanie", "mélissa", "melissa", "mewenne", "michele", "michèle",
    "monique", "morgane", "muriel", "myriam", "nadine", "nancy",
    "nathalie", "nicole", "nina", "noémie", "noemie", "ophélie",
    "ophelie", "oriane", "pascale", "patricia", "pauline", "philippine",
    "rachel", "roxane", "sandra", "sandrine", "sarah", "scarlett",
    "séverine", "severine", "simel", "simone", "sophie", "stéphanie",
    "stephanie", "sylvie", "sylvine", "tiphaine", "valérie", "valerie",
    "vanessa", "vera", "véra", "véronique", "veronique",
    "virginie", "yvette", "yveline", "yvonne", "zoulikha",
    "émeline", "emeline", "élise",
}

PRENOMS_MASCULINS = {
    "adrien", "alain", "alex", "alexandre", "alexis", "alphonse",
    "anthony", "antoine", "arnaud", "arnaut", "arthur", "aurélien",
    "aurelien", "baptiste", "basile", "bastien", "benjamin", "benoît",
    "benoit", "bernard", "bertrand", "brahim", "bruno",
    "charles", "charles-aymeric", "christian", "christophe",
    # NB: "claude", "camille", "dominique", "alex" sont volontairement absents
    # (ambigus) — ils retombent en Cher·ère.
    "clément", "clement", "colas", "cyril",
    "damien", "daniel", "david", "denis", "didier", "dimitri",
    "edgar", "édouard", "edouard", "emmanuel", "eric", "éric",
    "ernest", "etienne", "étienne", "eum", "evan", "fabien",
    "fabrice", "florent", "florentin", "florian", "floriant",
    "francis", "franck", "frank", "françois", "francois", "frédéric",
    "frederic",
    "gabriel", "gaétan", "gaetan", "geoffrey", "georges", "gérard",
    "gerard", "ghislain", "gilbert", "gilles", "glenn", "grégoire",
    "gregoire", "grégory", "gregory", "gustavo", "guillaume", "guy",
    "hassan", "henri", "hervé", "herve", "hugo", "hugues", "hyung",
    "hyungsik", "ibrahim", "isaac", "ismaël", "ismael",
    "chahin", "joackim", "johan", "jonathan", "joseph",
    "jacques", "jacques-françois", "jacques-francois", "jamal", "jan",
    "jean", "jean-baptiste", "jean-charles", "jean-christophe",
    "jean-claude", "jean-david", "jean-françois", "jean-francois",
    "jean-louis", "jean-luc", "jean-marc", "jean-marie", "jean-michel",
    "jean-paul", "jean-philippe", "jean-pierre", "jean-yves",
    "jérémie", "jeremie", "jérémy", "jeremy", "jérôme", "jerome",
    "jules", "julien", "kévin", "kevin",
    "laurent", "léon", "leon", "loïc", "loic", "louis", "luc", "luca",
    "lucas", "ludovic", "luigi", "lukas",
    "marc", "marcel", "martin", "matei", "mathieu", "matti",
    "maurice", "max", "maxime", "maximilien", "medhi", "mehdi",
    "mewen", "michael", "michaël", "michel", "mikael", "moïse", "moise",
    "nathan", "nicolas", "noah", "norbert", "olivier",
    "pablo", "pascal", "patrick", "paul", "paul-henri", "philippe",
    "pierre", "pierre-françois", "pierre-francois", "pierre-louis",
    "pierre-marie", "pierre-yves", "pierre-yvon",
    "quentin", "raphaël", "raphael", "rainer", "régis", "regis",
    "rémi", "remi", "rémy", "remy", "renaud", "richard",
    "robert", "robin", "rodolphe", "roger", "roland", "romain",
    "ronan", "samuel", "sébastien", "sebastien", "serge", "séverin",
    "severin", "simon", "stéphane", "stephane", "stéphan", "stephan",
    "sylvain", "tarik", "tebben", "théo", "theo", "thibault",
    "thibaut", "thierry", "thomas", "timothée", "timothee", "titouan",
    "tristan", "valentin", "valérian", "valerian", "victor", "vincent",
    "virgile", "wassim", "william", "wojtek", "xavier", "yann",
    "yannick", "yoan", "yoann", "yoric", "youcef", "yvan", "yves",
    "yvon", "zacharie",
}


def infer_cher_chere_from_prenom(prenom: str) -> str | None:
    """Devine Cher/Chère depuis le prénom. Retourne None si ambigu/inconnu.

    Pour les prénoms composés (Marie-Pierre), on teste le prénom complet
    puis le 1er composant en fallback.
    """
    if not prenom:
        return None
    p = prenom.strip().lower()
    # Test direct
    if p in PRENOMS_FEMININS:
        return "Chère"
    if p in PRENOMS_MASCULINS:
        return "Cher"
    # Fallback: 1er composant pour les prénoms composés
    if "-" in p:
        first = p.split("-", 1)[0]
        if first in PRENOMS_FEMININS:
            return "Chère"
        if first in PRENOMS_MASCULINS:
            return "Cher"
    return None


def parse_annuaire(path: Path) -> tuple[list[dict], dict[str, int]]:
    """Lit l'annuaire CSV. Filtre désinscrits + emails invalides."""
    rows: list[dict] = []
    stats = defaultdict(int)
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            stats["total"] += 1
            email = normalize_email(raw.get("E-mail", "") or "")
            prenom = (raw.get("Prénom", "") or "").strip()
            nom = (raw.get("Nom", "") or "").strip()
            desinscrit = (raw.get("désinscrit liste membres", "") or "").strip().lower()
            genre = raw.get("Genre", "") or ""

            if not email:
                stats["no_email"] += 1
                continue
            if not is_valid_email(email):
                stats["invalid_email"] += 1
                print(f"  [annuaire] email invalide: {email!r} ({prenom} {nom})", file=sys.stderr)
                continue
            if desinscrit == "oui":
                stats["unsubscribed"] += 1
                continue
            if not prenom:
                stats["no_prenom"] += 1
                continue

            cher_chere, genre_origin = map_genre_to_cher_chere(genre)
            rows.append({
                "mail": email,
                "prenom": titlecase_name(prenom),
                "nom": titlecase_name(nom),
                "cher_chere": cher_chere,
                "genre_origin": genre_origin,
                "source": "annuaire",
            })
    stats["kept"] = len(rows)
    return rows, dict(stats)


def parse_inscrits(path: Path) -> tuple[list[dict], dict[str, int]]:
    """Lit le CSV des inscrits Rencontre Com Numérique."""
    rows: list[dict] = []
    stats = defaultdict(int)
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            stats["total"] += 1
            email = normalize_email(raw.get("Email", "") or "")
            name = (raw.get("Name", "") or "").strip()

            if not email:
                stats["no_email"] += 1
                continue
            if not is_valid_email(email):
                stats["invalid_email"] += 1
                print(f"  [inscrits] email invalide: {email!r} ({name})", file=sys.stderr)
                continue
            if not name:
                stats["no_name"] += 1
                continue

            tokens = name.split()
            prenom = titlecase_name(tokens[0]) if tokens else ""
            nom = titlecase_name(" ".join(tokens[1:])) if len(tokens) > 1 else ""

            rows.append({
                "mail": email,
                "prenom": prenom,
                "nom": nom,
                "cher_chere": "Cher·ère",
                "genre_origin": "missing",
                "source": "inscrits",
            })
    stats["kept"] = len(rows)
    return rows, dict(stats)


def parse_partenaires(path: Path) -> tuple[list[dict], dict[str, int]]:
    """Extraction best-effort depuis le markdown partenaires (texte libre)."""
    rows: list[dict] = []
    stats = defaultdict(int)
    invalid_emails: list[str] = []
    with open(path, encoding="utf-8") as f:
        for raw_line in f:
            stats["total"] += 1
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if not stripped:
                continue

            # Skip dividers (em-dashes, etc.)
            if re.fullmatch(r"[—\-_\s]+", stripped):
                continue

            # Skip "déjà inclus(e)" lines même si elles ont un @ (rare)
            if DEJA_INCLUS_RE.search(stripped):
                stats["deja_inclus"] += 1
                continue

            # Normalise les hyphens Unicode dans toute la ligne
            line_norm = stripped.replace("‑", "-").replace("‐", "-")

            # Cherche tous les emails de la ligne, garde le 1er valide
            candidates = EMAIL_FINDALL_RE.findall(line_norm)
            if not candidates:
                stats["no_email_in_line"] += 1
                continue

            # Nettoyage des candidats : strip ponctuation parasite
            email = None
            for cand in candidates:
                clean = normalize_email(cand)
                if is_valid_email(clean):
                    email = clean
                    break
            if email is None:
                stats["invalid_email"] += 1
                invalid_emails.append(f"{candidates[0]!r}  (ligne: {stripped[:80]})")
                continue

            # Le prénom est en première position selon la convention de la source.
            # On prend le texte avant le 1er email comme bloc "nom complet",
            # on strip les guillemets/quotes parasites, puis on prend le 1er token.
            before_email = line_norm.split(email, 1)[0]
            before_email = before_email.strip().strip('"\'')
            # Évite les artéfacts de ponctuation
            before_email = re.sub(r"[<>\";]", " ", before_email).strip()

            tokens = before_email.split()
            if not tokens:
                stats["no_prenom"] += 1
                continue

            prenom_raw = tokens[0]
            # Strip les caractères non-alpha en début/fin (ex: virgule)
            prenom_raw = prenom_raw.strip(".,;:")
            prenom = titlecase_name(prenom_raw)

            nom_tokens = tokens[1:]
            # Filtre les tokens "déjà"/"inclus"/etc. qui peuvent traîner
            nom_tokens = [t for t in nom_tokens if not DEJA_INCLUS_RE.search(t)]
            nom = titlecase_name(" ".join(nom_tokens)) if nom_tokens else ""

            rows.append({
                "mail": email,
                "prenom": prenom,
                "nom": nom,
                "cher_chere": "Cher·ère",
                "genre_origin": "missing",
                "source": "partenaires",
            })

    stats["kept"] = len(rows)
    if invalid_emails:
        print("\n  [partenaires] emails invalides détectés (à corriger manuellement) :", file=sys.stderr)
        for e in invalid_emails:
            print(f"    - {e}", file=sys.stderr)

    return rows, dict(stats)


def merge_and_dedupe(sources: list[list[dict]]) -> tuple[list[dict], dict]:
    """Fusionne en respectant l'ordre de priorité (1ère source = gagne en cas de conflit)."""
    seen_emails: dict[str, dict] = {}
    dupes_resolved: list[tuple[str, str, str]] = []  # (email, kept_source, dropped_source)
    for source_rows in sources:
        for row in source_rows:
            key = row["mail"].strip().lower()
            if key in seen_emails:
                dupes_resolved.append((key, seen_emails[key]["source"], row["source"]))
                continue
            seen_emails[key] = row

    rows = list(seen_emails.values())

    # Détection de doublons probables par nom (warn, ne fusionne pas)
    name_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        if row["prenom"] and row["nom"]:
            name_groups[(row["prenom"].lower(), row["nom"].lower())].append(row)
    name_dupes = {k: v for k, v in name_groups.items() if len(v) > 1}

    return rows, {"dupes_resolved": dupes_resolved, "name_dupes": name_dupes}


def write_csv(rows: list[dict], path: Path) -> None:
    """Écrit le CSV final (cols: mail,prenom,cher_chere)."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["mail", "prenom", "cher_chere"])
        for r in rows:
            writer.writerow([r["mail"], r["prenom"], r["cher_chere"]])


def main():
    print("=" * 80)
    print("📋 Construction CSV destinataires '10 ans membres'")
    print("=" * 80)

    print(f"\n📄 Source 1: {ANNUAIRE.name}")
    annuaire_rows, annuaire_stats = parse_annuaire(ANNUAIRE)
    print(f"   Total brut: {annuaire_stats.get('total', 0)}")
    print(f"   Skippés: no_email={annuaire_stats.get('no_email', 0)}, "
          f"invalid_email={annuaire_stats.get('invalid_email', 0)}, "
          f"unsubscribed={annuaire_stats.get('unsubscribed', 0)}, "
          f"no_prenom={annuaire_stats.get('no_prenom', 0)}")
    print(f"   ✅ Gardés: {annuaire_stats.get('kept', 0)}")

    print(f"\n📄 Source 2: {INSCRITS.name}")
    inscrits_rows, inscrits_stats = parse_inscrits(INSCRITS)
    print(f"   Total brut: {inscrits_stats.get('total', 0)}")
    print(f"   Skippés: no_email={inscrits_stats.get('no_email', 0)}, "
          f"invalid_email={inscrits_stats.get('invalid_email', 0)}, "
          f"no_name={inscrits_stats.get('no_name', 0)}")
    print(f"   ✅ Gardés: {inscrits_stats.get('kept', 0)}")

    print(f"\n📄 Source 3: {PARTENAIRES.name}")
    partenaires_rows, partenaires_stats = parse_partenaires(PARTENAIRES)
    print(f"   Total brut (lignes): {partenaires_stats.get('total', 0)}")
    print(f"   Skippés: no_email_in_line={partenaires_stats.get('no_email_in_line', 0)}, "
          f"invalid_email={partenaires_stats.get('invalid_email', 0)}, "
          f"deja_inclus={partenaires_stats.get('deja_inclus', 0)}, "
          f"no_prenom={partenaires_stats.get('no_prenom', 0)}")
    print(f"   ✅ Extraits: {partenaires_stats.get('kept', 0)}")

    # Dédup inter-sources (priorité annuaire > inscrits > partenaires)
    merged, dedup_info = merge_and_dedupe([annuaire_rows, inscrits_rows, partenaires_rows])

    print("\n" + "=" * 80)
    print("🔁 Déduplication inter-sources")
    print("=" * 80)
    print(f"   Doublons inter-sources résolus: {len(dedup_info['dupes_resolved'])}")
    for email, kept, dropped in dedup_info["dupes_resolved"][:20]:
        print(f"     - {email}  [gardé: {kept}, droppé: {dropped}]")
    if len(dedup_info["dupes_resolved"]) > 20:
        print(f"     ... et {len(dedup_info['dupes_resolved']) - 20} autre(s)")

    if dedup_info["name_dupes"]:
        print(f"\n   ⚠️  Doublons probables par nom (à inspecter, pas de fusion auto) :")
        for (p, n), entries in dedup_info["name_dupes"].items():
            mails = [e["mail"] for e in entries]
            print(f"     - {p.title()} {n.title()}: {mails}")

    # Exclusion des destinataires déjà invités (campagne intervenants)
    print("\n" + "=" * 80)
    print(f"🚫 Exclusion des déjà invités ({ALREADY_INVITED.name})")
    print("=" * 80)
    with open(ALREADY_INVITED, encoding="utf-8") as f:
        already = {(row.get("mail") or "").strip().lower()
                   for row in csv.DictReader(f)
                   if (row.get("mail") or "").strip()}
    excluded = [r for r in merged if r["mail"].strip().lower() in already]
    merged = [r for r in merged if r["mail"].strip().lower() not in already]
    print(f"   Déjà invités (intervenants): {len(already)} emails")
    print(f"   Retirés du CSV membres: {len(excluded)}")
    for r in excluded:
        print(f"     - {r['mail']}  ({r['prenom']})")

    # Heuristique prénom : affine Cher·ère → Cher/Chère pour les rangs où le
    # genre n'est PAS un choix explicite (annuaire avec Genre vide, inscrits,
    # partenaires). On ne touche jamais aux rangs avec Genre explicite
    # (binaire ou non-binaire).
    print("\n" + "=" * 80)
    print("🔮 Affinage heuristique prénom → cher/chère")
    print("=" * 80)
    inferred_count = 0
    inferred_unknown: set[str] = set()
    for row in merged:
        if row.get("genre_origin") == "missing" and row["cher_chere"] == "Cher·ère":
            guess = infer_cher_chere_from_prenom(row["prenom"])
            if guess:
                row["cher_chere"] = guess
                inferred_count += 1
            else:
                inferred_unknown.add(row["prenom"])
    print(f"   Affinés: {inferred_count}")
    print(f"   Restent en Cher·ère (prénom inconnu/ambigu): {len(inferred_unknown)} prénoms uniques")
    if inferred_unknown:
        sample = sorted(inferred_unknown)[:25]
        print(f"   Échantillon: {', '.join(sample)}{'...' if len(inferred_unknown) > 25 else ''}")

    # Garantie finale
    emails_lower = [r["mail"].strip().lower() for r in merged]
    assert len(emails_lower) == len(set(emails_lower)), \
        "❌ DOUBLON DÉTECTÉ APRÈS DÉDUP — bug dans le script"

    write_csv(merged, OUTPUT)

    print("\n" + "=" * 80)
    print(f"✅ CSV écrit: {OUTPUT}")
    print(f"   Total destinataires uniques: {len(merged)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
