#!/usr/bin/env python3
"""
Compare 3 data sources for 2026 memberships:
  1. HelloAsso CSV export (local file)
  2. Airtable PROD (Annuaire, Cotisation LCDC = "Payé 2026")
  3. Airtable DEV  (Annuaire, Cotisation LCDC = "Payé 2026")

Outputs a console summary + an HTML report for easy human review.
"""

import csv
import glob
import html
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from src.clients.airtable_client import AirtableClient

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
HELLOASSO_CSV_PATTERN = str(DATA_DIR / "export-adhesion-annee-2026-*.csv")
AIRTABLE_FILTER = "{Cotisation LCDC}='Payé 2026'"

# Fields to compare (HelloAsso CSV column -> Airtable field name)
FIELD_MAP = {
    "Prénom adhérent": "Prénom",
    "Nom adhérent": "Nom",
    "Genre": "Genre",
    "Structure": "Structure(s)",
    "Fonction au sein de votre structure": "Fonction (structure)",
    "Localisation (code postal)": "code postal",
    "Intérêts (mot-clés)": "Intérêts",
}

# Airtable fields to compare between Prod and Dev
AIRTABLE_COMPARE_FIELDS = [
    "Prénom", "Nom", "Genre", "Structure(s)",
    "Fonction (structure)", "code postal", "Intérêts",
    "Cotisation LCDC",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def norm_email(email: str) -> str:
    return email.strip().lower()


def load_helloasso_csv() -> dict:
    """Return {email_lower: {field: value, ...}} from the HelloAsso CSV."""
    files = sorted(glob.glob(HELLOASSO_CSV_PATTERN))
    if not files:
        print(f"No HelloAsso CSV found matching {HELLOASSO_CSV_PATTERN}")
        sys.exit(1)
    csv_path = files[-1]  # most recent
    print(f"Loading HelloAsso CSV: {csv_path}")

    result = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            email = row.get("E-mail", "").strip()
            if not email:
                email = row.get("Email payeur", "").strip()
            if not email:
                continue
            key = norm_email(email)
            result[key] = {
                "E-mail": email,
                "Prénom adhérent": row.get("Prénom adhérent", "").strip(),
                "Nom adhérent": row.get("Nom adhérent", "").strip(),
                "Genre": row.get("Genre", "").strip().strip('" '),
                "Structure": row.get("Structure", "").strip(),
                "Fonction au sein de votre structure": row.get(
                    "Fonction au sein de votre structure", ""
                ).strip(),
                "Localisation (code postal)": row.get(
                    "Localisation (code postal)", ""
                ).strip(),
                "Intérêts (mot-clés)": row.get("Intérêts (mot-clés)", "").strip(),
                "Tarif": row.get("Tarif", "").strip(),
                "Montant tarif": row.get("Montant tarif", "").strip(),
            }
    print(f"  -> {len(result)} members loaded")
    return result


def load_airtable(label: str, api_key: str, base_id: str) -> dict:
    """Return {email_lower: {field: value, ...}} from an Airtable base."""
    print(f"Loading Airtable {label} (base {base_id})...")
    client = AirtableClient(api_key=api_key, base_id=base_id, table_name="Annuaire")
    records = client.list_records(filter_by_formula=AIRTABLE_FILTER)
    result = {}
    for rec in records:
        fields = rec.get("fields", {})
        email = fields.get("E-mail", "").strip()
        if not email:
            continue
        key = norm_email(email)
        result[key] = fields
    print(f"  -> {len(result)} members loaded")
    return result


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------
def compare_sources(ha: dict, prod: dict, dev: dict):
    all_emails = sorted(set(ha) | set(prod) | set(dev))

    only_ha = sorted(set(ha) - set(prod) - set(dev))
    only_prod = sorted(set(prod) - set(ha) - set(dev))
    only_dev = sorted(set(dev) - set(ha) - set(prod))
    in_prod_not_dev = sorted(set(prod) - set(dev))
    in_dev_not_prod = sorted(set(dev) - set(prod))
    in_ha_not_prod = sorted(set(ha) - set(prod))
    in_ha_not_dev = sorted(set(ha) - set(dev))

    # Field diffs for records present in multiple sources
    ha_vs_prod_diffs = {}
    ha_vs_dev_diffs = {}
    prod_vs_dev_diffs = {}

    for email in all_emails:
        # HelloAsso vs Prod
        if email in ha and email in prod:
            diffs = []
            for ha_col, at_col in FIELD_MAP.items():
                ha_val = ha[email].get(ha_col, "").strip()
                prod_val = str(prod[email].get(at_col, "") or "").strip()
                if ha_val.lower() != prod_val.lower():
                    diffs.append((at_col, ha_val, prod_val))
            if diffs:
                ha_vs_prod_diffs[email] = diffs

        # HelloAsso vs Dev
        if email in ha and email in dev:
            diffs = []
            for ha_col, at_col in FIELD_MAP.items():
                ha_val = ha[email].get(ha_col, "").strip()
                dev_val = str(dev[email].get(at_col, "") or "").strip()
                if ha_val.lower() != dev_val.lower():
                    diffs.append((at_col, ha_val, dev_val))
            if diffs:
                ha_vs_dev_diffs[email] = diffs

        # Prod vs Dev
        if email in prod and email in dev:
            diffs = []
            for field in AIRTABLE_COMPARE_FIELDS:
                prod_val = str(prod[email].get(field, "") or "").strip()
                dev_val = str(dev[email].get(field, "") or "").strip()
                if prod_val != dev_val:
                    diffs.append((field, prod_val, dev_val))
            if diffs:
                prod_vs_dev_diffs[email] = diffs

    return {
        "all_emails": all_emails,
        "only_ha": only_ha,
        "only_prod": only_prod,
        "only_dev": only_dev,
        "in_prod_not_dev": in_prod_not_dev,
        "in_dev_not_prod": in_dev_not_prod,
        "in_ha_not_prod": in_ha_not_prod,
        "in_ha_not_dev": in_ha_not_dev,
        "ha_vs_prod_diffs": ha_vs_prod_diffs,
        "ha_vs_dev_diffs": ha_vs_dev_diffs,
        "prod_vs_dev_diffs": prod_vs_dev_diffs,
    }


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------
def print_report(ha, prod, dev, cmp):
    print()
    print("=" * 90)
    print("  3-WAY COMPARISON REPORT  —  Cotisation LCDC = 'Payé 2026'")
    print("=" * 90)

    print(f"\nTotals:  HelloAsso={len(ha)}  |  Airtable PROD={len(prod)}  |  Airtable DEV={len(dev)}")
    print(f"Unique emails across all sources: {len(cmp['all_emails'])}")

    # Presence matrix
    print("\n--- PRESENCE MATRIX ---")
    print(f"{'Email':<45} {'HA':>4} {'PROD':>5} {'DEV':>5}")
    print("-" * 62)
    for email in cmp["all_emails"]:
        ha_flag = "Y" if email in ha else "-"
        prod_flag = "Y" if email in prod else "-"
        dev_flag = "Y" if email in dev else "-"
        name = ""
        if email in ha:
            name = f"{ha[email].get('Prénom adhérent','')} {ha[email].get('Nom adhérent','')}"
        elif email in prod:
            name = f"{prod[email].get('Prénom','')} {prod[email].get('Nom','')}"
        elif email in dev:
            name = f"{dev[email].get('Prénom','')} {dev[email].get('Nom','')}"
        print(f"{email:<45} {ha_flag:>4} {prod_flag:>5} {dev_flag:>5}  {name}")

    def _print_email_list(title, emails, source_data, source_key_prefix=""):
        if not emails:
            return
        print(f"\n--- {title} ({len(emails)}) ---")
        for e in emails:
            name = ""
            for src in [ha, prod, dev]:
                if e in src:
                    first = src[e].get("Prénom adhérent", src[e].get("Prénom", ""))
                    last = src[e].get("Nom adhérent", src[e].get("Nom", ""))
                    name = f"{first} {last}".strip()
                    break
            print(f"  {e:<45} {name}")

    _print_email_list("IN HELLOASSO BUT NOT IN PROD", cmp["in_ha_not_prod"], ha)
    _print_email_list("IN HELLOASSO BUT NOT IN DEV", cmp["in_ha_not_dev"], ha)
    _print_email_list("IN PROD BUT NOT IN HELLOASSO", sorted(set(prod) - set(ha)), prod)
    _print_email_list("IN DEV BUT NOT IN HELLOASSO", sorted(set(dev) - set(ha)), dev)
    _print_email_list("IN PROD BUT NOT IN DEV", cmp["in_prod_not_dev"], prod)
    _print_email_list("IN DEV BUT NOT IN PROD", cmp["in_dev_not_prod"], dev)

    def _print_diffs(title, diffs):
        if not diffs:
            return
        print(f"\n--- {title} ({len(diffs)} records with differences) ---")
        for email, fields in sorted(diffs.items()):
            print(f"\n  {email}:")
            for field, val_a, val_b in fields:
                print(f"    {field:<25} | {val_a!r:<40} | {val_b!r}")

    _print_diffs("FIELD DIFFS: HelloAsso vs PROD", cmp["ha_vs_prod_diffs"])
    _print_diffs("FIELD DIFFS: HelloAsso vs DEV", cmp["ha_vs_dev_diffs"])
    _print_diffs("FIELD DIFFS: PROD vs DEV", cmp["prod_vs_dev_diffs"])


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------
def generate_html_report(ha, prod, dev, cmp, output_path):
    h = html.escape

    css = """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 2em; background: #f8f9fa; }
    h1 { color: #2c3e50; }
    h2 { color: #34495e; margin-top: 2em; border-bottom: 2px solid #3498db; padding-bottom: 0.3em; }
    h3 { color: #7f8c8d; }
    table { border-collapse: collapse; width: 100%; margin: 1em 0; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    th { background: #3498db; color: white; padding: 8px 12px; text-align: left; position: sticky; top: 0; }
    td { padding: 6px 12px; border-bottom: 1px solid #ecf0f1; }
    tr:hover { background: #f1f8ff; }
    .yes { color: #27ae60; font-weight: bold; }
    .no  { color: #e74c3c; font-weight: bold; }
    .diff-old { background: #ffeaea; }
    .diff-new { background: #eaffea; }
    .summary { display: flex; gap: 2em; margin: 1em 0; }
    .summary-box { background: white; padding: 1em 2em; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }
    .summary-box .number { font-size: 2em; font-weight: bold; color: #3498db; }
    .summary-box .label { color: #7f8c8d; }
    .email-list { margin: 0.5em 0; }
    .email-list li { margin: 0.2em 0; }
    """

    lines = []
    lines.append(f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Comparison Report</title><style>{css}</style></head><body>")
    lines.append("<h1>3-Way Comparison Report &mdash; Cotisation LCDC = 'Pay&eacute; 2026'</h1>")
    lines.append(f"<p>Generated on {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}</p>")

    # Summary boxes
    lines.append("<div class='summary'>")
    for label, count in [("HelloAsso", len(ha)), ("Airtable PROD", len(prod)), ("Airtable DEV", len(dev)), ("Total unique emails", len(cmp["all_emails"]))]:
        lines.append(f"<div class='summary-box'><div class='number'>{count}</div><div class='label'>{h(label)}</div></div>")
    lines.append("</div>")

    # Presence matrix
    lines.append("<h2>Presence Matrix</h2>")
    lines.append("<table><tr><th>Email</th><th>Name</th><th>HelloAsso</th><th>PROD</th><th>DEV</th></tr>")
    for email in cmp["all_emails"]:
        name = ""
        for src in [ha, prod, dev]:
            if email in src:
                first = src[email].get("Prénom adhérent", src[email].get("Prénom", ""))
                last = src[email].get("Nom adhérent", src[email].get("Nom", ""))
                name = f"{first} {last}".strip()
                break
        def _flag(present):
            return "<span class='yes'>&#10003;</span>" if present else "<span class='no'>&#10007;</span>"
        lines.append(f"<tr><td>{h(email)}</td><td>{h(name)}</td><td>{_flag(email in ha)}</td><td>{_flag(email in prod)}</td><td>{_flag(email in dev)}</td></tr>")
    lines.append("</table>")

    # Missing sections
    def _email_section(title, emails):
        if not emails:
            return
        lines.append(f"<h2>{h(title)} ({len(emails)})</h2><ul class='email-list'>")
        for e in emails:
            name = ""
            for src in [ha, prod, dev]:
                if e in src:
                    first = src[e].get("Prénom adhérent", src[e].get("Prénom", ""))
                    last = src[e].get("Nom adhérent", src[e].get("Nom", ""))
                    name = f"{first} {last}".strip()
                    break
            lines.append(f"<li><strong>{h(e)}</strong> &mdash; {h(name)}</li>")
        lines.append("</ul>")

    _email_section("In HelloAsso but NOT in PROD", cmp["in_ha_not_prod"])
    _email_section("In HelloAsso but NOT in DEV", cmp["in_ha_not_dev"])
    _email_section("In PROD but NOT in HelloAsso", sorted(set(prod) - set(ha)))
    _email_section("In DEV but NOT in HelloAsso", sorted(set(dev) - set(ha)))
    _email_section("In PROD but NOT in DEV", cmp["in_prod_not_dev"])
    _email_section("In DEV but NOT in PROD", cmp["in_dev_not_prod"])

    # Diff tables
    def _diff_section(title, diffs, label_a, label_b):
        if not diffs:
            return
        lines.append(f"<h2>{h(title)} ({len(diffs)} records)</h2>")
        for email, fields in sorted(diffs.items()):
            name = ""
            for src in [ha, prod, dev]:
                if email in src:
                    first = src[email].get("Prénom adhérent", src[email].get("Prénom", ""))
                    last = src[email].get("Nom adhérent", src[email].get("Nom", ""))
                    name = f"{first} {last}".strip()
                    break
            lines.append(f"<h3>{h(email)} &mdash; {h(name)}</h3>")
            lines.append(f"<table><tr><th>Field</th><th>{h(label_a)}</th><th>{h(label_b)}</th></tr>")
            for field, val_a, val_b in fields:
                lines.append(f"<tr><td>{h(field)}</td><td class='diff-old'>{h(val_a)}</td><td class='diff-new'>{h(val_b)}</td></tr>")
            lines.append("</table>")

    _diff_section("Field Differences: HelloAsso vs PROD", cmp["ha_vs_prod_diffs"], "HelloAsso", "PROD")
    _diff_section("Field Differences: HelloAsso vs DEV", cmp["ha_vs_dev_diffs"], "HelloAsso", "DEV")
    _diff_section("Field Differences: PROD vs DEV", cmp["prod_vs_dev_diffs"], "PROD", "DEV")

    lines.append("</body></html>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nHTML report written to: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    api_key = os.getenv("AIRTABLE_API_KEY")
    api_key_prod = os.getenv("AIRTABLE_API_KEY_PROD", api_key)
    base_id_dev = os.getenv("AIRTABLE_BASE_ID")
    base_id_prod = os.getenv("AIRTABLE_BASE_ID_PROD")

    if not api_key or not base_id_dev or not base_id_prod:
        print("Missing AIRTABLE env vars in .env")
        sys.exit(1)

    ha = load_helloasso_csv()
    prod = load_airtable("PROD", api_key_prod, base_id_prod)
    dev = load_airtable("DEV", api_key, base_id_dev)

    cmp = compare_sources(ha, prod, dev)
    print_report(ha, prod, dev, cmp)

    html_path = DATA_DIR / "comparison_report.html"
    generate_html_report(ha, prod, dev, cmp, html_path)


if __name__ == "__main__":
    main()
