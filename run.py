"""Wekelijkse run: vacatures ophalen en het overzicht maken.

Gebruik:  python run.py            (ophalen + rapport)
          python run.py --report   (alleen rapport opnieuw maken)
"""

import argparse
import datetime as dt
from pathlib import Path

import yaml

from leadinsights import banenrijk, db, export, report

ROOT = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="alleen rapport, niet scrapen")
    ap.add_argument("--backfill", action="store_true",
                    help="details (o.a. vacaturetekst) ophalen voor bekende vacatures zonder tekst")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text()) or {}
    con = db.connect(ROOT / "data" / "vacatures.db")

    if args.backfill:
        todo = [(r["id"], r["url"]) for r in con.execute(
            "SELECT id, url FROM vacancies WHERE description IS NULL")]
        print(f"Backfill: {len(todo)} vacatures")
        rows = banenrijk.fetch_many(todo)
        db.update_details(con, rows)
        print(f"Bijgewerkt: {len(rows)}")
        return

    if not args.report:
        active = banenrijk.list_active()
        new = [(i, u) for i, u in active.items() if i not in db.known_ids(con)]
        print(f"Banenrijk: {len(active)} actief, {len(new)} nieuw op te halen")
        rows = banenrijk.fetch_many(new)
        db.insert_vacancies(con, rows, args.date)
        stored = db.known_ids(con)
        db.mark_seen(con, [i for i in active if i in stored], args.date, banenrijk.SOURCE)
        print(f"Opgehaald: {len(rows)} van {len(new)}")

    week = dt.date.fromisoformat(args.date).isocalendar()
    out = ROOT / "reports" / f"vacatures_{week.year}-W{week.week:02d}.xlsx"
    s = report.build(con, cfg, args.date, out)
    print(f"\nWeek {week.week}: {s['relevant']} relevante vacatures bij {s['companies']} bedrijven"
          + (f", {s['new']} nieuw t.o.v. {s['previous_run']}" if s["previous_run"] else ""))
    for company, n in s["top"]:
        print(f"  {n:4d}  {company}")
    rows = export.export(con, cfg, args.date, ROOT / "reports" / "dashboard.json")
    print(f"\nRapport: {out}\nDashboard-data: reports/dashboard.json ({len(rows)} vacatures)")


if __name__ == "__main__":
    main()
