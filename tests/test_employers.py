"""Employer sponsor lookup: name matching, both USCIS file formats, DOL LCA files, queries."""

import datetime as dt

import pytest

from copilot.employers import (
    EmployerDB, EmployersNotLoaded, annual_wage, connect, detect_kind, fiscal_year, import_file, normalize_name,
)

USCIS_OLD = """Fiscal Year,Employer,Initial Approval,Initial Denial,Continuing Approval,Continuing Denial,NAICS,Tax ID,State,City,ZIP
2023,"GOOGLE LLC",1200,15,3000,20,54,1234,CA,MOUNTAIN VIEW,94043
2023,"Acme Robotics, Inc.",4,1,2,0,33,9999,NJ,NEWARK,07102
2022,"GOOGLE, L.L.C.",900,10,2500,12,54,1234,CA,MOUNTAIN VIEW,94043
"""

USCIS_NEW_HEADERS = ["Line by line", "Fiscal Year", "Employer (Petitioner) Name", "Tax ID", "Industry (NAICS) Code",
                     "Petitioner City", "Petitioner State", "Petitioner Zip Code", "New Employment Approval",
                     "New Employment Denial", "Continuation Approval", "Continuation Denial",
                     "Change with Same Employer Approval", "Change with Same Employer Denial",
                     "New Concurrent Approval", "New Concurrent Denial", "Change of Employer Approval",
                     "Change of Employer Denial", "Amended Approval", "Amended Denial"]
USCIS_NEW_ROW = ["1", "2025", "Google LLC", "1234", "54", "MOUNTAIN VIEW", "CA", "94043",
                 "800", "5", "2000", "10", "100", "1", "20", "0", "300", "3", "50", "0"]

LCA_HEADERS = ["CASE_NUMBER", "CASE_STATUS", "RECEIVED_DATE", "DECISION_DATE", "VISA_CLASS", "JOB_TITLE", "SOC_TITLE",
               "FULL_TIME_POSITION", "EMPLOYER_NAME", "WORKSITE_CITY", "WORKSITE_STATE",
               "WAGE_RATE_OF_PAY_FROM", "WAGE_RATE_OF_PAY_TO", "WAGE_UNIT_OF_PAY"]
LCA_ROWS = [
    ["I-1", "Certified", "2024-10-02", "2024-10-09", "H-1B", "Software Engineer", "Software Developers", "Y", "GOOGLE LLC", "NEW YORK", "NY", "150,000.00", "", "Year"],
    ["I-2", "Certified", "2024-10-02", "2024-10-09", "H-1B", "Software Engineer", "Software Developers", "Y", "Google LLC", "SUNNYVALE", "CA", "170000", "", "Year"],
    ["I-3", "Certified", "2025-01-05", "2025-01-12", "H-1B", "Data Scientist", "Data Scientists", "Y", "GOOGLE LLC", "NEW YORK", "NY", "80", "", "Hour"],
    ["I-4", "Denied", "2025-01-05", "2025-01-12", "H-1B", "Software Engineer", "Software Developers", "Y", "GOOGLE LLC", "NEW YORK", "NY", "100000", "", "Year"],
    ["I-5", "Certified - Withdrawn", "2025-01-05", "2025-01-12", "H-1B", "Software Engineer", "", "Y", "GOOGLE LLC", "", "NY", "1", "", "Year"],
    ["I-6", "Certified", "2025-01-05", "2025-01-12", "E-3 Australian", "Analyst", "", "Y", "GOOGLE LLC", "", "NY", "90000", "", "Year"],
    ["I-8", "Certified", "2025-03-01", "2025-03-04", "H-1B", "Analyst", "", "Y", "J.P. Morgan Securities LLC", "NEW YORK", "NY", "120000", "", "Year"],
    ["I-7", "Certified", "2025-03-01", "2025-03-04", "H-1B", "Robotics Engineer", "", "N", "ACME ROBOTICS INC", "NEWARK", "NJ", "95000", "", "Year"],
]


def test_normalize_name_merges_spellings():
    assert normalize_name("Google LLC") == normalize_name("GOOGLE, L.L.C.") == "GOOGLE"
    assert normalize_name("The Goldman Sachs Group, Inc.") == normalize_name("Goldman Sachs & Co. LLC") == "GOLDMAN SACHS"
    assert normalize_name("Acme Robotics, Inc.") == "ACME ROBOTICS"
    assert normalize_name("Services Inc") == "SERVICES"  # never reduced to nothing


def test_wages_and_fiscal_years():
    assert annual_wage("150,000.00", "Year") == 150000
    assert annual_wage("80", "Hour") == 166400
    assert annual_wage("1", "Year") is None and annual_wage("", "Year") is None
    assert fiscal_year(dt.date(2024, 10, 1)) == 2025 and fiscal_year(dt.date(2025, 9, 30)) == 2025


def test_detect_kind():
    assert detect_kind(["fiscal year", "employer", "initial approval"]) == "uscis"
    assert detect_kind(["case status", "employer name", "job title"]) == "lca"
    assert detect_kind(["name", "address"]) is None


def write_lca_csv(path):
    import csv
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(LCA_HEADERS)
        w.writerows(LCA_ROWS)


@pytest.fixture
def db(tmp_path):
    (tmp_path / "h1b_old.csv").write_text(USCIS_OLD)
    new = "\t".join(USCIS_NEW_HEADERS) + "\n" + "\t".join(USCIS_NEW_ROW) + "\n"
    (tmp_path / "h1b_new.csv").write_bytes(new.encode("utf-16"))  # USCIS exports are UTF-16, tab-separated
    write_lca_csv(tmp_path / "lca.csv")
    con = connect(tmp_path / "employers.db")
    logs = []
    for f in ["h1b_old.csv", "h1b_new.csv", "lca.csv"]:
        import_file(con, tmp_path / f, log=logs.append)
    import_file(con, tmp_path / "lca.csv", log=logs.append)  # re-import must not duplicate
    con.close()
    return EmployerDB(tmp_path / "employers.db"), logs


def test_import_counts_and_filters(db):
    edb, logs = db
    assert "lca.csv: imported 4 certified H-1B job filings" in logs  # denied, withdrawn, E-3 and part-time dropped
    d = edb.detail("GOOGLE")
    assert d["filings"] == 3
    years = {y["fy"]: y for y in d["years"]}
    assert years[2025]["new_approved"] == 820  # new employment + new concurrent
    assert years[2025]["cont_approved"] == 2450  # continuation + change with same + change of employer + amended
    assert years[2023]["new_approved"] == 1200 and years[2022]["cont_denied"] == 12
    jobs = {j["title"]: j for j in d["jobs"]}
    assert jobs["Software Engineer"]["filings"] == 2 and jobs["Software Engineer"]["medianWage"] == 160000
    assert jobs["Data Scientist"]["medianWage"] == 166400
    assert d["states"][0] == {"state": "NY", "filings": 2}
    assert d["lcaYears"] == [2025]


def test_search_ranks_and_matches_spellings(db):
    edb, _ = db
    assert [r["key"] for r in edb.search("google llc")] == ["GOOGLE"]
    r = edb.search("goog")[0]
    assert r["name"] in {"GOOGLE LLC", "Google LLC"} and r["filings"] == 3 and r["medianWage"] == 166400
    assert edb.search("acme")[0]["filings"] == 0  # its only filing was part-time
    assert edb.search("google", state="NJ") == []
    assert edb.search("x") == []
    assert [r["name"] for r in edb.search("JPMorgan")] == ["J.P. Morgan Securities LLC"]  # dots and spaces ignored


def test_status_and_not_loaded(db, tmp_path):
    edb, _ = db
    st = edb.status()
    assert st["loaded"] and st["employers"] == 3 and len(st["sources"]) == 3
    with pytest.raises(EmployersNotLoaded):
        EmployerDB(tmp_path / "missing.db").search("google")
    assert EmployerDB(tmp_path / "missing.db").status() == {"loaded": False, "sources": []}


def test_reads_dol_excel_files(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(LCA_HEADERS)
    for r in LCA_ROWS:
        ws.append(r)
    wb.save(tmp_path / "LCA_Disclosure_Data_FY2025_Q1.xlsx")
    con = connect(tmp_path / "e.db")
    kind, n = import_file(con, tmp_path / "LCA_Disclosure_Data_FY2025_Q1.xlsx", log=lambda *_: None)
    assert (kind, n) == ("lca", 4)


def test_rejects_unrelated_files(tmp_path):
    (tmp_path / "x.csv").write_text("name,address\nBob,1 Main St\n")
    with pytest.raises(ValueError, match="not a USCIS"):
        import_file(connect(tmp_path / "e.db"), tmp_path / "x.csv")


def test_empty_database_reports_not_loaded(tmp_path):
    connect(tmp_path / "e.db").close()  # created by a failed import, but no rows
    with pytest.raises(EmployersNotLoaded):
        EmployerDB(tmp_path / "e.db").search("google")
