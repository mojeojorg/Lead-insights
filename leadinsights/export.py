"""Exporteert de relevante vacatures van een run als JSON voor het dashboard."""

import datetime as dt
import json

from . import report


def function_group(title, cfg):
    t = (title or "").lower()
    for group, terms in (cfg.get("function_groups") or {}).items():
        if any(term.lower() in t for term in terms):
            return group
    return "Overig"


def export(con, cfg, run_date, out_path):
    week_ago = (dt.date.fromisoformat(run_date) - dt.timedelta(days=7)).isoformat()
    rows = []
    for v in report._active(con, run_date):
        if not report.is_relevant(v, cfg):
            continue
        rows.append({
            "id": v["id"],
            "week": run_date,
            "functie": v["title"],
            "groep": function_group(v["title"], cfg),
            "bedrijf": v["company"],
            "sector": report.sector(v, cfg),
            "branche": (v["industry"] or "").replace("|,|", ", "),
            "plaats": v["city"],
            "regio": v["region"],
            "geplaatst": v["date_posted"],
            "nieuw": v["date_posted"] >= week_ago,
            "geldig_tot": "" if (v["valid_through"] or "") >= "2030" else v["valid_through"],
            "salaris_min": v.get("salary_min"),
            "salaris_max": v.get("salary_max"),
            "url": v["url"],
        })
    rows.sort(key=lambda r: (r["sector"], r["bedrijf"], r["functie"]))
    with open(out_path, "w") as f:
        f.write("[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n")
    return rows
