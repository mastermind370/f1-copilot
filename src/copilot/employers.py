"""Visa-sponsor lookup built from official U.S. government data files.

Two sources, both free downloads you import once with `copilot employers import`:

* USCIS H-1B Employer Data Hub (CSV or Excel): petitions approved and denied per employer
  and fiscal year, split into new employment and continuing employment.
* DOL OFLC LCA disclosure data (Excel or CSV): every Labor Condition Application, with job
  title, worksite and the wage offered. We keep certified, full-time H-1B rows.

The importer recognizes each file by its column headers, so it works across fiscal years
whose column names differ slightly. Employer names are normalized ("Google LLC" and
"GOOGLE, L.L.C." become one employer) so the two sources line up.
"""

from __future__ import annotations

import codecs
import csv
import datetime as dt
import io
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

SUFFIXES = {
    "INC", "INCORPORATED", "LLC", "LLP", "LP", "LTD", "LIMITED", "CORP", "CORPORATION", "CO", "COMPANY",
    "PLLC", "PC", "PA", "THE", "USA", "US", "NA", "GROUP", "HOLDINGS", "SERVICES",
}
# Words like GROUP or SERVICES are dropped only at the end of a name, and only if a name remains.
TAIL_ONLY = {"GROUP", "HOLDINGS", "SERVICES", "USA", "US", "NA"}

ANNUAL = {"YEAR": 1, "YR": 1, "MONTH": 12, "MTH": 12, "BI-WEEKLY": 26, "BIWEEKLY": 26, "WEEK": 52, "WK": 52, "HOUR": 2080, "HR": 2080}


def normalize_name(name: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", name.upper().replace("&", " AND ").replace("L.L.C", "LLC"))
    words = s.split()
    while words and words[0] == "THE":
        words.pop(0)
    while len(words) > 1 and (words[-1] in SUFFIXES or words[-1] == "AND"):
        words.pop()
    words = [w for w in words if w not in SUFFIXES - TAIL_ONLY] or words
    return " ".join(words)


def _norm_header(h: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(h or "").lower()).strip()


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^0-9.\-]", "", str(v))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _int(v: Any) -> int:
    n = _num(v)
    return int(n) if n is not None else 0


def _date(v: Any) -> dt.date | None:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def fiscal_year(d: dt.date) -> int:
    """U.S. federal fiscal years start October 1."""
    return d.year + 1 if d.month >= 10 else d.year


def annual_wage(amount: Any, unit: Any) -> float | None:
    a = _num(amount)
    if a is None or a <= 0:
        return None
    mult = ANNUAL.get(str(unit or "Year").strip().upper())
    if mult is None:
        return None
    wage = a * mult
    return wage if 10_000 <= wage <= 2_000_000 else None  # drop obvious data-entry errors


# ---------- reading files ----------

def _open_text(path: Path) -> io.TextIOBase:
    raw = path.read_bytes()[:4]
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        enc = "utf-16"
    elif raw.startswith(codecs.BOM_UTF8):
        enc = "utf-8-sig"
    else:
        enc = "utf-8"
    return open(path, encoding=enc, errors="replace", newline="")  # noqa: SIM115


def read_rows(path: Path) -> Iterator[dict[str, Any]]:
    """Yield rows as {normalized header: value} from a .csv/.tsv/.txt or .xlsx file."""
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("Reading Excel files needs openpyxl: pip install openpyxl") from exc
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        rows = wb.worksheets[0].iter_rows(values_only=True)
        headers = [_norm_header(h) for h in next(rows, [])]
        for r in rows:
            yield dict(zip(headers, r, strict=False))
        wb.close()
        return
    with _open_text(path) as f:
        sample = f.read(64_000)
        f.seek(0)
        try:
            dialect: Any = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        headers = [_norm_header(h) for h in next(reader, [])]
        for r in reader:
            yield dict(zip(headers, r, strict=False))


def _first(headers: Iterable[str], *candidates: str) -> str | None:
    hs = list(headers)
    for c in candidates:
        if c in hs:
            return c
    return None


def detect_kind(headers: list[str]) -> str | None:
    if any("approval" in h for h in headers) and any("employer" in h or "petitioner name" in h for h in headers):
        return "uscis"
    if "case status" in headers and "employer name" in headers:
        return "lca"
    return None


# ---------- database ----------

SCHEMA = """
CREATE TABLE IF NOT EXISTS employers (key TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT, state TEXT);
CREATE TABLE IF NOT EXISTS uscis (key TEXT, fy INTEGER, new_approved INTEGER, new_denied INTEGER,
  cont_approved INTEGER, cont_denied INTEGER, city TEXT, state TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS lca (key TEXT, fy INTEGER, job_title TEXT, soc_title TEXT, city TEXT, state TEXT,
  wage REAL, source TEXT);
CREATE TABLE IF NOT EXISTS sources (file TEXT PRIMARY KEY, kind TEXT, rows INTEGER, imported_at TEXT);
CREATE INDEX IF NOT EXISTS uscis_key ON uscis(key);
CREATE INDEX IF NOT EXISTS lca_key ON lca(key);
"""


class EmployersNotLoaded(Exception):
    pass


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    return con


def import_file(con: sqlite3.Connection, path: Path, log: Any = print) -> tuple[str, int]:
    rows = read_rows(path)
    first = next(rows, None)
    if first is None:
        raise ValueError(f"{path.name}: file is empty")
    headers = list(first.keys())
    kind = detect_kind(headers)
    if kind is None:
        raise ValueError(f"{path.name}: not a USCIS Data Hub or DOL LCA file (headers: {', '.join(headers[:8])}...)")
    con.execute(f"DELETE FROM {kind} WHERE source = ?", (path.name,))  # re-importing replaces, never duplicates
    names: dict[str, Counter[str]] = defaultdict(Counter)
    places: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    n = 0
    batch: list[tuple[Any, ...]] = []
    insert = (
        "INSERT INTO uscis VALUES (?,?,?,?,?,?,?,?,?)" if kind == "uscis" else "INSERT INTO lca VALUES (?,?,?,?,?,?,?,?)"
    )

    def all_rows() -> Iterator[dict[str, Any]]:
        yield first
        yield from rows

    if kind == "uscis":
        emp = next(h for h in headers if ("employer" in h or "petitioner name" in h) and "tax" not in h)
        fy_h = _first(headers, "fiscal year")
        city_h = next((h for h in headers if "city" in h), None)
        state_h = next((h for h in headers if "state" in h), None)
        appr = [h for h in headers if "approval" in h]
        deny = [h for h in headers if "denial" in h]
        is_new = lambda h: "initial" in h or "new employment" in h or "new concurrent" in h  # noqa: E731
        for r in all_rows():
            raw = str(r.get(emp) or "").strip()
            key = normalize_name(raw)
            if not key:
                continue
            city, state = str(r.get(city_h) or "").strip().title(), str(r.get(state_h) or "").strip().upper()
            batch.append((key, _int(r.get(fy_h)),
                          sum(_int(r.get(h)) for h in appr if is_new(h)), sum(_int(r.get(h)) for h in deny if is_new(h)),
                          sum(_int(r.get(h)) for h in appr if not is_new(h)), sum(_int(r.get(h)) for h in deny if not is_new(h)),
                          city, state, path.name))
            names[key][raw] += 1
            places[key][(city, state)] += 1
            n += 1
            if len(batch) >= 5000:
                con.executemany(insert, batch)
                batch.clear()
    else:
        h = {
            "status": "case status", "emp": "employer name",
            "visa": _first(headers, "visa class", "program"),
            "title": _first(headers, "job title"), "soc": _first(headers, "soc title", "soc name"),
            "city": _first(headers, "worksite city", "worksite city 1", "employer city"),
            "state": _first(headers, "worksite state", "worksite state 1", "employer state"),
            "wage": _first(headers, "wage rate of pay from", "wage rate of pay from 1"),
            "unit": _first(headers, "wage unit of pay", "wage unit of pay 1"),
            "full": _first(headers, "full time position"),
            "date": _first(headers, "decision date", "received date", "begin date"),
        }
        for r in all_rows():
            if not str(r.get(h["status"]) or "").strip().upper().startswith("CERTIFIED"):
                continue
            if "WITHDRAWN" in str(r.get(h["status"]) or "").upper():
                continue
            if h["visa"] and str(r.get(h["visa"]) or "H-1B").strip().upper() not in {"H-1B", "H1B"}:
                continue
            if h["full"] and str(r.get(h["full"]) or "Y").strip().upper()[:1] == "N":
                continue
            raw = str(r.get(h["emp"]) or "").strip()
            key = normalize_name(raw)
            if not key:
                continue
            d = _date(r.get(h["date"])) if h["date"] else None
            city, state = str(r.get(h["city"]) or "").strip().title(), str(r.get(h["state"]) or "").strip().upper()
            batch.append((key, fiscal_year(d) if d else 0, str(r.get(h["title"]) or "").strip().upper()[:120],
                          str(r.get(h["soc"]) or "").strip().title()[:120], city, state,
                          annual_wage(r.get(h["wage"]), r.get(h["unit"])), path.name))
            names[key][raw] += 1
            places[key][(city, state)] += 1
            n += 1
            if len(batch) >= 5000:
                con.executemany(insert, batch)
                batch.clear()
    if batch:
        con.executemany(insert, batch)
    for key, counter in names.items():
        name = counter.most_common(1)[0][0]
        (city, state) = places[key].most_common(1)[0][0]
        con.execute(
            "INSERT INTO employers(key, name, city, state) VALUES (?,?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET name = COALESCE(employers.name, excluded.name)",
            (key, name, city, state),
        )
    con.execute("INSERT OR REPLACE INTO sources VALUES (?,?,?,?)",
                (path.name, kind, n, dt.datetime.now(dt.UTC).isoformat(timespec="seconds")))
    con.commit()
    log(f"{path.name}: imported {n:,} {'employer-year rows' if kind == 'uscis' else 'certified H-1B job filings'}")
    return kind, n


# ---------- queries ----------

def _median(values: list[float]) -> int | None:
    return int(statistics.median(values)) if values else None


class EmployerDB:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _con(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise EmployersNotLoaded("Employer data hasn't been imported yet")
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        return con

    def status(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return {"loaded": False, "sources": []}
        with self._con() as con:
            src = [dict(r) for r in con.execute("SELECT * FROM sources ORDER BY file")]
            n = con.execute("SELECT COUNT(*) FROM employers").fetchone()[0]
        return {"loaded": n > 0, "employers": n, "sources": src}

    def search(self, q: str, state: str = "", limit: int = 20) -> list[dict[str, Any]]:
        tokens = normalize_name(q).split()[:6]
        if not tokens or len(" ".join(tokens)) < 2:
            return []
        # Match ignoring spaces too, so "JPMorgan" finds "J P MORGAN" and "J.P. Morgan".
        where = " AND ".join("REPLACE(e.key, ' ', '') LIKE ?" for _ in tokens)
        params: list[Any] = [f"%{t}%" for t in tokens]
        if state:
            where += " AND e.state = ?"
            params.append(state.upper()[:2])
        with self._con() as con:
            if con.execute("SELECT COUNT(*) FROM employers").fetchone()[0] == 0:
                raise EmployersNotLoaded("The employer database is empty; the import didn't load any rows")
            latest = con.execute("SELECT MAX(fy) FROM uscis").fetchone()[0] or 0
            sql = f"""
              SELECT e.key, e.name, e.city, e.state,
                COALESCE((SELECT SUM(new_approved) FROM uscis u WHERE u.key = e.key AND u.fy > ?), 0) AS new_recent,
                COALESCE((SELECT SUM(new_approved + cont_approved) FROM uscis u WHERE u.key = e.key), 0) AS approved,
                (SELECT COUNT(*) FROM lca l WHERE l.key = e.key) AS filings
              FROM employers e WHERE {where}
              ORDER BY (e.key = ?) DESC, new_recent DESC, filings DESC, approved DESC LIMIT ?"""
            rows = [dict(r) for r in con.execute(sql, [latest - 3, *params, " ".join(tokens), limit])]
            for r in rows:
                wages = [w for (w,) in con.execute("SELECT wage FROM lca WHERE key = ? AND wage IS NOT NULL", (r["key"],))]
                r["medianWage"] = _median(wages)
        return rows

    def detail(self, key: str) -> dict[str, Any] | None:
        with self._con() as con:
            e = con.execute("SELECT * FROM employers WHERE key = ?", (key,)).fetchone()
            if not e:
                return None
            years = [dict(r) for r in con.execute(
                "SELECT fy, SUM(new_approved) AS new_approved, SUM(new_denied) AS new_denied, "
                "SUM(cont_approved) AS cont_approved, SUM(cont_denied) AS cont_denied "
                "FROM uscis WHERE key = ? AND fy > 0 GROUP BY fy ORDER BY fy DESC LIMIT 8", (key,))]
            by_title: dict[str, list[float]] = defaultdict(list)
            counts: Counter[str] = Counter()
            states: Counter[str] = Counter()
            lca_years: Counter[int] = Counter()
            for title, wage, state, fy in con.execute("SELECT job_title, wage, state, fy FROM lca WHERE key = ?", (key,)):
                counts[title] += 1
                if wage:
                    by_title[title].append(wage)
                if state:
                    states[state] += 1
                if fy:
                    lca_years[fy] += 1
            jobs = [{"title": t.title(), "filings": c, "medianWage": _median(by_title[t]),
                     "low": int(min(by_title[t])) if by_title[t] else None,
                     "high": int(max(by_title[t])) if by_title[t] else None}
                    for t, c in counts.most_common(12) if t]
            all_wages = [w for ws in by_title.values() for w in ws]
            sources = [dict(r) for r in con.execute("SELECT file, kind FROM sources ORDER BY file")]
        return {
            "key": key, "name": e["name"], "city": e["city"], "state": e["state"],
            "years": years, "jobs": jobs, "filings": sum(counts.values()), "medianWage": _median(all_wages),
            "states": [{"state": s, "filings": c} for s, c in states.most_common(6)],
            "lcaYears": sorted(lca_years), "sources": sources,
        }
