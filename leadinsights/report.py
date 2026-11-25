"""Weekoverzicht: aantal relevante vacatures per bedrijf, met verschil t.o.v. vorige run."""

import re
from collections import Counter

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


def _contains_any(text, words):
    t = (text or "").lower()
    return any(w.lower() in t for w in words)


def _industries(v):
    # Banenrijk scheidt meerdere branches met "|,|"
    return {p.strip().lower() for p in (v["industry"] or "").split("|,|") if p.strip()}


def sector(v, cfg):
    """Eerste passende sector uit config (Overheid gaat voor, want herkend op naam)."""
    company = (v["company"] or "").lower()
    for name, rule in (cfg.get("sectors") or {}).items():
        if any(re.search(rf"\b{re.escape(k.lower())}\b", company)
               for k in rule.get("company_keywords") or []):
            return name
    inds = _industries(v)
    for name, rule in (cfg.get("sectors") or {}).items():
        if inds & {i.lower() for i in rule.get("industries") or []}:
            return name
    return "Overig"


def is_relevant(v, cfg):
    rel = cfg.get("relevance") or {}
    reg = cfg.get("region") or {}
    if _contains_any(v["company"], cfg.get("exclude_companies") or []):
        return False
    kw, ind = rel.get("title_keywords") or [], rel.get("industries") or []
    v_ind = _industries(v)
    if (kw or ind) and not (_contains_any(v["title"], kw) or
                            v_ind & {i.lower() for i in ind}):
        return False
    regions, cities = reg.get("regions") or [], reg.get("cities") or []
    if (regions or cities) and not (
        (v["region"] or "").lower() in [r.lower() for r in regions]
        or (v["city"] or "").lower() in [c.lower() for c in cities]
    ):
        return False
    return True


def _active(con, run_date):
    return [dict(r) for r in con.execute(
        "SELECT v.* FROM vacancies v JOIN seen s ON s.vacancy_id=v.id WHERE s.run_date=?",
        (run_date,))]


def build(con, cfg, run_date, out_path):
    prev = con.execute("SELECT MAX(run_date) FROM runs WHERE run_date<?", (run_date,)).fetchone()[0]
    now = [v for v in _active(con, run_date) if is_relevant(v, cfg)]
    before = [v for v in _active(con, prev) if is_relevant(v, cfg)] if prev else []
    prev_ids = {v["id"] for v in before}

    cnt_now = Counter(v["company"] for v in now)
    cnt_prev = Counter(v["company"] for v in before)
    cnt_new = Counter(v["company"] for v in now if v["id"] not in prev_ids)
    prio = set(cfg.get("priority_sectors") or [])
    for v in now + before:
        v["sector"] = sector(v, cfg)
        v["prioriteit"] = "ja" if v["sector"] in prio else ""
    comp_sector = {}
    for v in before + now:
        comp_sector[v["company"]] = v["sector"]
    companies = sorted(set(cnt_now) | set(cnt_prev),
                       key=lambda c: (comp_sector.get(c) not in prio, -cnt_now[c], c))

    wb = Workbook()
    ws = wb.active
    ws.title = "Per bedrijf"
    ws.append(["Bedrijf", "Sector", "Prioriteit", "Open vacatures", "Nieuw", "Vorige week", "Verschil"])
    for c in companies:
        ws.append([c, comp_sector.get(c, ""), "ja" if comp_sector.get(c) in prio else "", cnt_now[c], cnt_new[c] if prev else "", cnt_prev[c] if prev else "",
                   cnt_now[c] - cnt_prev[c] if prev else ""])

    cols = ["company", "title", "sector", "prioriteit", "city", "region", "industry",
            "salary_min", "salary_max", "work_hours", "date_posted", "valid_through", "url"]
    heads = ["Bedrijf", "Functie", "Sector", "Prioriteit", "Plaats", "Regio", "Branche",
             "Salaris min", "Salaris max", "Uren", "Geplaatst", "Geldig tot", "Link"]
    for name, rows in [("Nieuw deze week", [v for v in now if v["id"] not in prev_ids]),
                       ("Alle open vacatures", now)]:
        s = wb.create_sheet(name)
        s.append(heads)
        for v in sorted(rows, key=lambda v: (v["prioriteit"] != "ja", v["company"], v["title"])):
            s.append([v.get(c) for c in cols])

    for s in wb.worksheets:
        for cell in s[1]:
            cell.font = Font(bold=True)
        s.freeze_panes = "A2"
        s.auto_filter.ref = s.dimensions
        for i, col in enumerate(s.columns, 1):
            width = max(len(str(c.value or "")) for c in col)
            s.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)
    wb.save(out_path)

    return {
        "run_date": run_date, "previous_run": prev, "relevant": len(now),
        "new": len([v for v in now if v["id"] not in prev_ids]) if prev else None,
        "companies": len(cnt_now), "top": cnt_now.most_common(10),
    }
