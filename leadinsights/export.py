"""Export voor het dashboard.

- dashboard_vacatures.json: alle vacatures van de laatste run, met functiegroep en branche.
- dashboard_weken.json: per week (laatste 13 runs) het aantal vacatures per
  functiegroep x branche x organisatie, voor de trends en het verschil met vorige week.
"""

import datetime as dt
import json
from collections import Counter

from . import report

BRANCHES = {
    "zorg & welzijn": "Zorg & Welzijn", "techniek & productie": "Techniek & Productie",
    "onderwijs & onderzoek": "Onderwijs & Onderzoek", "horeca & detailhandel": "Horeca & Detailhandel",
    "finance": "Finance", "facilitair": "Facilitair", "logistiek & inkoop": "Logistiek & Inkoop",
    "ict & automatisering": "ICT & Automatisering",
    "kwaliteit, veiligheid & milieu": "Kwaliteit, Veiligheid & Milieu", "kwaliteit": "Kwaliteit, Veiligheid & Milieu",
    "management, beleid & directie": "Management, Beleid & Directie", "management": "Management, Beleid & Directie",
    "administratie": "Administratie", "overig": "Overig", "sales": "Sales", "hr": "HR",
    "klantenservice & receptie": "Klantenservice & Receptie", "marketing & communicatie": "Marketing & Communicatie",
    "juridisch": "Juridisch",
}
WEEKS = 13
RECON_WEEKS = 2  # weken vóór de eerste meting die we reconstrueren (ondergrens)


def function_group(title, cfg):
    t = f" {(title or '').lower()} "
    for g in cfg.get("function_groups") or []:
        if any(term.lower() in t for term in g["terms"]):
            return g["name"]
    return "Overig"


def branche(v, cfg):
    if report.sector(v, cfg) == "Overheid":
        return "Overheid"
    first = (v["industry"] or "").split("|,|")[0].strip().lower()
    return BRANCHES.get(first, "Overig")


def iso_week(date_str):
    y, w, _ = dt.date.fromisoformat(date_str).isocalendar()
    return f"{y}-W{w:02d}"


def _keep(v, cfg):
    return not report._contains_any(v["company"], cfg.get("exclude_companies") or [])


def _creation_estimator(con):
    """Schat sinds wanneer een vacature bestaat.

    Banenrijk-nummers lopen op in de tijd; de plaatsingsdatum wordt bij herplaatsen
    ververst. Per plaatsingsdatum nemen we de mediaan van de nummers als ijkpunt
    (oplopend gemaakt). Bestaansdatum = min(plaatsingsdatum, datum waarop het nummer
    volgens de ijklijn is uitgegeven).
    """
    import statistics
    by_date = {}
    for vid, dp in con.execute("SELECT id, date_posted FROM vacancies"):
        by_date.setdefault(dp, []).append(int(vid.split(":")[1]))
    curve, top = [], 0
    for dp in sorted(by_date):
        if len(by_date[dp]) < 5:
            continue
        top = max(top, statistics.median(by_date[dp]))
        curve.append((dp, top))

    def created(v):
        n = int(v["id"].split(":")[1])
        est = next((d for d, mid in curve if mid >= n), curve[-1][0] if curve else v["date_posted"])
        return min(est, v["date_posted"] or est)
    return created


def _count(rows, cfg, week, peildatum, recon):
    c = Counter((function_group(v["title"], cfg), branche(v, cfg), v["company"]) for v in rows if _keep(v, cfg))
    return [{"week": week, "peildatum": peildatum, "groep": g, "branche": b, "bedrijf": o, "vacatures": n,
             "reconstructie": recon} for (g, b, o), n in sorted(c.items())]


def export(con, cfg, run_date, out_dir):
    week_ago = (dt.date.fromisoformat(run_date) - dt.timedelta(days=7)).isoformat()
    vac = []
    for v in report._active(con, run_date):
        if not _keep(v, cfg):
            continue
        vac.append({
            "id": v["id"], "week": iso_week(run_date), "peildatum": run_date,
            "functie": v["title"], "groep": function_group(v["title"], cfg),
            "bedrijf": v["company"], "branche": branche(v, cfg),
            "plaats": v["city"], "regio": v["region"],
            "geplaatst": v["date_posted"], "nieuw": v["date_posted"] >= week_ago,
            "geldig_tot": "" if (v["valid_through"] or "") >= "2030" else v["valid_through"],
            "url": v["url"],
        })
    vac.sort(key=lambda r: (r["branche"], r["bedrijf"], r["functie"]))

    runs = [r[0] for r in con.execute(
        "SELECT run_date FROM runs WHERE run_date<=? ORDER BY run_date DESC LIMIT ?", (run_date, WEEKS))]
    weeks = []
    measured = {iso_week(rd) for rd in runs}
    first = con.execute("SELECT MIN(run_date) FROM runs").fetchone()[0]
    if first:
        # Reconstructie: vacatures uit de eerste meting die toen al bestonden.
        # Ondergrens: vacatures die intussen gesloten zijn, ontbreken.
        created = _creation_estimator(con)
        base = report._active(con, first)
        for k in range(RECON_WEEKS, 0, -1):
            pd = (dt.date.fromisoformat(first) - dt.timedelta(days=7 * k)).isoformat()
            if iso_week(pd) not in measured:
                weeks += _count([v for v in base if created(v) <= pd], cfg, iso_week(pd), pd, True)
    for rd in sorted(runs):
        weeks += _count(report._active(con, rd), cfg, iso_week(rd), rd, False)
    weeks = [w for w in weeks if w["week"] in sorted({x["week"] for x in weeks})[-WEEKS:]]

    def dump(rows, name):
        with open(out_dir / name, "w") as f:
            f.write("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n")

    dump(vac, "dashboard_vacatures.json")
    dump(weeks, "dashboard_weken.json")
    return vac, weeks


def standalone(vac, weeks, run_date, out_dir):
    """Losstaand HTML-weekrapport (geen account of internet nodig)."""
    from pathlib import Path
    tpl = (Path(__file__).parent / "template.html").read_text()
    js = lambda rows: json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    week = iso_week(run_date)
    html = (tpl.replace("/*VACATURES*/[]", js(vac))
               .replace("/*WEKEN*/[]", js(weeks))
               .replace("__WEEK__", f"week {int(week.split('-W')[1])} {week[:4]}"))
    out = out_dir / f"vacatureradar_{week}.html"
    out.write_text(html)
    return out
