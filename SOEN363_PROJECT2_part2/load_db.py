"""Task 4: Import the cleaned and integrated data into the SQL database."""

import os
import sqlite3

import PHASE2  # runs Tasks 1-3 and builds PHASE2.integrated_tables

DB_FILE = "hospital.db"
SCHEMA_FILE = "integrated_schema.sql"

# Parents before children, so every foreign key points to a row already loaded.
LOAD_ORDER = [
    # independent tables (no foreign keys)
    "Source_System",
    "ICD9_Code",
    "Healthcare_Professional",
    "Unit",
    "Patient",
    # depend on Patient / Healthcare_Professional
    "Uncertain_Patient_Match",
    "Admission",
    # depend on Admission
    "TriageAssessment",
    "ClinicalNote",
    "Diagnosis",            # also needs Patient, ICD9_Code
    "SurgicalProcedure",
    "DischargeRecord",
    "DiagnosticOrder",      # also needs Patient
    # depend on DiagnosticOrder
    "RadiologyExamination",
    "DiagnosticExamination",
    # depends on RadiologyExamination
    "RadiologyReport",
    # depend on Admission / Unit
    "UnitStay",
    "GeneralWardRecord",
    # depends on UnitStay
    "CriticalCareRecord",
    # depends on Source_System
    "Source_ID_Mapping",
]


def build_database():
    # 1. Rebuild from scratch so reruns never duplicate data
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON")  # SQLite has FK checks off by default

    try:
        # 2. Create empty tables with all PKs, FKs and constraints
        with open(SCHEMA_FILE) as f:
            con.executescript(f.read())

        # 3. Load each table in dependency order.
        #    to_sql uses parameterized INSERTs; if_exists="append" keeps our schema
        #    (with "replace", pandas would drop it and lose the constraints).
        for table in LOAD_ORDER:
            df = PHASE2.integrated_tables[table]
            df.to_sql(table, con, if_exists="append", index=False)
            print(f"  {table}: {len(df)} rows loaded")

        # 4. Verify: row counts match and no foreign key is broken
        print("\nVerification:")
        for table in LOAD_ORDER:
            in_db = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            expected = len(PHASE2.integrated_tables[table])
            status = "OK" if in_db == expected else "MISMATCH"
            print(f"  {table}: {in_db} in DB / {expected} expected  {status}")

        broken = con.execute("PRAGMA foreign_key_check").fetchall()
        print(f"\nForeign key violations: {len(broken)}")

    except Exception as e:
        # to_sql commits table by table, so undo a partial load by deleting the file
        con.close()
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        print(f"\nLoad FAILED, partial database removed: {e}")
        raise

    con.close()
    print(f"\nDatabase written to {DB_FILE}")


if __name__ == "__main__":
    print("\n=== TASK 4: LOADING INTO SQL DATABASE ===")
    build_database()