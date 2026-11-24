import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS vacancies (
    id TEXT PRIMARY KEY,
    source TEXT, url TEXT, title TEXT, company TEXT,
    city TEXT, region TEXT, postal_code TEXT, industry TEXT,
    employment_type TEXT, date_posted TEXT, valid_through TEXT,
    first_seen TEXT, last_seen TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    run_date TEXT PRIMARY KEY, source TEXT, active_count INTEGER
);
CREATE TABLE IF NOT EXISTS seen (
    run_date TEXT, vacancy_id TEXT, PRIMARY KEY (run_date, vacancy_id)
);
"""

FIELDS = ["id", "source", "url", "title", "company", "city", "region", "postal_code",
          "industry", "employment_type", "date_posted", "valid_through"]


def connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def known_ids(con):
    return {r[0] for r in con.execute("SELECT id FROM vacancies")}


def insert_vacancies(con, rows, run_date):
    for v in rows:
        con.execute(
            f"INSERT OR REPLACE INTO vacancies ({','.join(FIELDS)}, first_seen, last_seen) "
            f"VALUES ({','.join('?' * len(FIELDS))}, ?, ?)",
            [v[f] for f in FIELDS] + [run_date, run_date],
        )


def mark_seen(con, ids, run_date, source):
    con.executemany("INSERT OR IGNORE INTO seen VALUES (?, ?)", [(run_date, i) for i in ids])
    con.executemany("UPDATE vacancies SET last_seen=? WHERE id=?", [(run_date, i) for i in ids])
    con.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, ?)", (run_date, source, len(ids)))
    con.commit()
