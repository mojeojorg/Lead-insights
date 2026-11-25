"""Scraper voor banenrijklimburg.nl.

Werkwijze: de sitemap bevat alle actieve vacatures (/vacature/<slug>-<id>).
Elke vacaturepagina bevat schema.org JobPosting JSON-LD met bedrijf, plaats,
regio, branche en datums. We halen alleen pagina's op van vacatures die we
nog niet kennen; bekende vacatures worden alleen als 'nog actief' gemarkeerd.
"""

import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "https://www.banenrijklimburg.nl"
SOURCE = "banenrijk"
UA = "Mozilla/5.0 (compatible; LeadInsightsBot/1.0)"
VAC_RE = re.compile(r"<loc>(https://www\.banenrijklimburg\.nl/vacature/[a-z0-9-]+-(\d+))</loc>")
LDJSON_RE = re.compile(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', re.S)

session = requests.Session()
session.headers["User-Agent"] = UA


def list_active():
    """Geeft {vacature_id: url} voor alle vacatures in de sitemap."""
    r = session.get(f"{BASE}/sitemap.xml", timeout=30)
    r.raise_for_status()
    return {f"{SOURCE}:{vid}": url for url, vid in VAC_RE.findall(r.text)}


def _find_jobposting(obj):
    if isinstance(obj, dict):
        if obj.get("@type") == "JobPosting":
            return obj
        for v in obj.values():
            found = _find_jobposting(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_jobposting(v)
            if found:
                return found
    return None


def _obj(x):
    """JSON-LD velden zijn soms een lijst i.p.v. een object; neem dan het eerste."""
    if isinstance(x, list):
        x = x[0] if x else {}
    return x if isinstance(x, dict) else {}


def _str(x):
    if isinstance(x, list):
        return "|,|".join(str(i) for i in x)
    return str(x) if x else ""


def _text(desc_html):
    t = re.sub(r"<(br|/p|/li|/h[1-6])[^>]*>", "\n", desc_html)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def fetch_vacancy(vid, url):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 2:
                return None
            time.sleep(2 * (attempt + 1))
    for block in LDJSON_RE.findall(r.text):
        try:
            jp = _find_jobposting(json.loads(block))
        except json.JSONDecodeError:
            continue
        if jp:
            addr = _obj(_obj(jp.get("jobLocation")).get("address"))
            sal = _obj(_obj(jp.get("baseSalary")).get("value"))
            return {
                "id": vid,
                "source": SOURCE,
                "url": url,
                "title": (jp.get("title") or "").strip(),
                "company": (_obj(jp.get("hiringOrganization")).get("name") or "").strip(),
                "city": addr.get("addressLocality") or "",
                "region": addr.get("addressRegion") or "",
                "postal_code": addr.get("postalCode") or "",
                "industry": _str(jp.get("industry")),
                "employment_type": _str(jp.get("employmentType")),
                "date_posted": (jp.get("datePosted") or "")[:10],
                "valid_through": (jp.get("validThrough") or "")[:10],
                "salary_min": sal.get("minValue"),
                "salary_max": sal.get("maxValue"),
                "salary_unit": sal.get("unitText") if (sal.get("minValue") or sal.get("maxValue")) else None,
                "work_hours": _str(jp.get("workHours")),
                "education": _obj(jp.get("educationRequirements")).get("credentialCategory") or "",
                "company_website": _obj(jp.get("hiringOrganization")).get("sameAs") or "",
                "description": _text(jp.get("description") or ""),
            }
    return None


def fetch_many(items, workers=4, delay=0.25):
    """items: lijst (id, url). Beperkte parallelliteit om de site te ontzien."""
    def job(item):
        time.sleep(delay)
        try:
            return fetch_vacancy(*item)
        except Exception as e:  # één kapotte pagina mag de run niet stoppen
            print(f"  overgeslagen {item[1]}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return [v for v in ex.map(job, items) if v]
