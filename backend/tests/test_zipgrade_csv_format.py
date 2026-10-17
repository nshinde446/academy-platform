"""ZipGrade results-CSV parser — real export formats.

ZipGrade's own export uses CamelCase headers (ZipGradeID, ExternalID, EarnedPts,
PossiblePts, PercentCorrect) with no spaces, and academies here type the student
PRN as the Student ID on the sheet — so it lands in ZipGradeID while ExternalID
stays blank. These guard that the parser reads that export (it previously failed
with "Could not find a Student ID / PRN column").
"""

from app.modules.tests.services import zipgrade_csv as z

# A trimmed real ZipGrade export: PRN sits in ZipGradeID, ExternalID is blank,
# marks in EarnedPts / PossiblePts / PercentCorrect.
REAL_EXPORT = (
    "QuizName,QuizClass,FirstName,LastName,ZipGradeID,ExternalID,EarnedPts,"
    "PossiblePts,PercentCorrect,QuizCreated\n"
    '"NEET BIO","","Manisha","Sirvi",2801503,"",152.0,200.0,76.0,"Oct 07 2026"\n'
    '"NEET BIO","","Jayesh","Dhake",2801298,"",140.0,200.0,70.0,"Oct 07 2026"\n'
).encode("utf-8")


def test_parses_zipgrade_camelcase_export_with_prn_in_zipgradeid():
    rows = z.parse_zipgrade_csv(REAL_EXPORT)
    assert len(rows) == 2
    first = rows[0]
    assert first["prn"] == "2801503"          # from ZipGradeID (ExternalID blank)
    assert first["name"] == "Manisha Sirvi"   # FirstName + LastName
    assert first["score"] == 152.0            # EarnedPts
    assert first["total"] == 200.0            # PossiblePts
    assert first["percent"] == 76.0           # PercentCorrect
    assert all(r["prn"] for r in rows)        # no blank PRNs


def test_external_id_takes_precedence_over_zipgrade_id():
    csv = (
        "FirstName,LastName,ZipGradeID,ExternalID,EarnedPts,PossiblePts\n"
        '"A","B",999,"PRN-100",10,20\n'      # ExternalID present -> wins
        '"C","D",888,"",12,20\n'             # ExternalID blank -> fall back to ZipGradeID
    ).encode("utf-8")
    rows = z.parse_zipgrade_csv(csv)
    assert rows[0]["prn"] == "PRN-100"
    assert rows[1]["prn"] == "888"


def test_spaced_header_export_still_parses():
    csv = (
        "Student Name,Student ID,Earned Points,Possible Points,Percent Correct\n"
        "Aarohi A,PRNA,186,200,93\n"
    ).encode("utf-8")
    rows = z.parse_zipgrade_csv(csv)
    assert rows[0]["prn"] == "PRNA"
    assert rows[0]["score"] == 186.0 and rows[0]["total"] == 200.0


def test_rejects_csv_with_no_id_column():
    import pytest
    csv = b"FirstName,LastName,EarnedPts\nA,B,10\n"
    with pytest.raises(z.ZipGradeCsvError):
        z.parse_zipgrade_csv(csv)
