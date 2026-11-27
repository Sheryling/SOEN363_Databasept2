"""
Task 5: Post-import validation of hospital.db.
Run after load_db.py, from the SOEN363_PROJECT2_part2 folder:
    python3 validate_db.py
"""

import sqlite3

DB_FILE = "hospital.db"

PRIMARY_KEYS = {
    "Source_System": "source_code", "ICD9_Code": "icd9_code",
    "Healthcare_Professional": "staff_id", "Unit": "unit_id", "Patient": "patient_id",
    "Uncertain_Patient_Match": "match_id", "Admission": "admission_id",
    "TriageAssessment": "triage_id", "ClinicalNote": "note_id", "Diagnosis": "diagnosis_id",
    "SurgicalProcedure": "procedure_id", "DischargeRecord": "discharge_id",
    "DiagnosticOrder": "order_id", "RadiologyExamination": "exam_id",
    "RadiologyReport": "report_id", "DiagnosticExamination": "diag_exam_id",
    "UnitStay": "unit_stay_id", "CriticalCareRecord": "record_id",
    "GeneralWardRecord": "ward_record_id", "Source_ID_Mapping": "mapping_id",
}

COMPLETED = "('Discharged', 'Transferred', 'Deceased')"

# Each check: (description, query returning the violating rows)
CHECKS = [
    ("Every admission belongs to an existing patient",
     """SELECT a.admission_id FROM Admission a
        LEFT JOIN Patient p ON p.patient_id = a.patient_id
        WHERE p.patient_id IS NULL"""),

    ("Every diagnosis references an existing admission",
     """SELECT d.diagnosis_id FROM Diagnosis d
        LEFT JOIN Admission a ON a.admission_id = d.admission_id
        WHERE a.admission_id IS NULL"""),

    ("Every diagnosis references an existing ICD-9 code",
     """SELECT d.diagnosis_id, d.icd9_code FROM Diagnosis d
        LEFT JOIN ICD9_Code i ON i.icd9_code = d.icd9_code
        WHERE i.icd9_code IS NULL"""),

    ("Diagnosis: patient_id matches the admission's patient",
     """SELECT d.diagnosis_id, d.patient_id, a.patient_id FROM Diagnosis d
        JOIN Admission a ON a.admission_id = d.admission_id
        WHERE d.patient_id <> a.patient_id"""),

    ("DiagnosticOrder: patient_id matches the admission's patient",
     """SELECT o.order_id, o.patient_id, a.patient_id FROM DiagnosticOrder o
        JOIN Admission a ON a.admission_id = o.admission_id
        WHERE o.patient_id <> a.patient_id"""),

    ("Discharge time is after admission time",
     """SELECT admission_id, admission_datetime, discharge_datetime FROM Admission
        WHERE discharge_datetime IS NOT NULL
          AND discharge_datetime <= admission_datetime"""),

    ("Unit exit time is after unit entry time",
     """SELECT unit_stay_id, entry_datetime, exit_datetime FROM UnitStay
        WHERE exit_datetime IS NOT NULL AND exit_datetime <= entry_datetime"""),

    ("Surgical procedures occur within the admission period",
     """SELECT s.procedure_id, s.procedure_datetime, a.admission_datetime, a.discharge_datetime
        FROM SurgicalProcedure s JOIN Admission a ON a.admission_id = s.admission_id
        WHERE s.procedure_datetime < a.admission_datetime
           OR (a.discharge_datetime IS NOT NULL AND s.procedure_datetime > a.discharge_datetime)"""),

    ("Radiology examinations occur within the admission period",
     """SELECT r.exam_id, r.exam_datetime, a.admission_datetime, a.discharge_datetime
        FROM RadiologyExamination r JOIN Admission a ON a.admission_id = r.admission_id
        WHERE r.exam_datetime < a.admission_datetime
           OR (a.discharge_datetime IS NOT NULL AND r.exam_datetime > a.discharge_datetime)"""),

    ("Diagnostic examinations occur within the admission period",
     """SELECT e.diag_exam_id, e.exam_datetime, a.admission_datetime, a.discharge_datetime
        FROM DiagnosticExamination e
        JOIN DiagnosticOrder o ON o.order_id = e.order_id
        JOIN Admission a ON a.admission_id = o.admission_id
        WHERE e.exam_datetime < a.admission_datetime
           OR (a.discharge_datetime IS NOT NULL AND e.exam_datetime > a.discharge_datetime)"""),

    ("Unit stays occur within the admission period",
     """SELECT s.unit_stay_id, s.entry_datetime, s.exit_datetime,
               a.admission_datetime, a.discharge_datetime
        FROM UnitStay s JOIN Admission a ON a.admission_id = s.admission_id
        WHERE s.entry_datetime < a.admission_datetime
           OR (a.discharge_datetime IS NOT NULL
               AND COALESCE(s.exit_datetime, s.entry_datetime) > a.discharge_datetime)"""),

    ("Every completed admission has at least one primary ICD-9 diagnosis",
     f"""SELECT a.admission_id, a.admission_status FROM Admission a
        WHERE a.admission_status IN {COMPLETED}
          AND NOT EXISTS (SELECT 1 FROM Diagnosis d
                          WHERE d.admission_id = a.admission_id
                            AND d.diagnosis_type = 'Primary')"""),

    ("Completed admissions have a discharge time",
     f"""SELECT admission_id, admission_status FROM Admission
        WHERE admission_status IN {COMPLETED} AND discharge_datetime IS NULL"""),

    ("Still-admitted patients have no discharge time",
     """SELECT admission_id, discharge_datetime FROM Admission
        WHERE admission_status = 'Admitted' AND discharge_datetime IS NOT NULL"""),

    ("Still-admitted patients have no discharge record",
     """SELECT a.admission_id FROM Admission a
        JOIN DischargeRecord r ON r.admission_id = a.admission_id
        WHERE a.admission_status = 'Admitted'"""),

    ("Discharge condition 'Deceased' only on Deceased admissions (and vice versa)",
     """SELECT a.admission_id, a.admission_status, r.condition_at_discharge
        FROM Admission a JOIN DischargeRecord r ON r.admission_id = a.admission_id
        WHERE (r.condition_at_discharge = 'Deceased') <> (a.admission_status = 'Deceased')"""),

    ("Deceased admissions belong to patients marked Deceased",
     """SELECT a.admission_id, p.patient_id, p.life_status FROM Admission a
        JOIN Patient p ON p.patient_id = a.patient_id
        WHERE a.admission_status = 'Deceased' AND p.life_status <> 'Deceased'"""),

    ("condition_on_arrival uses a standard label",
     """SELECT admission_id, condition_on_arrival FROM Admission
        WHERE condition_on_arrival NOT IN ('Critical', 'Serious', 'Fair', 'Stable')"""),

    ("Radiology exam_type uses a standard label",
     """SELECT exam_id, exam_type FROM RadiologyExamination
        WHERE exam_type NOT IN ('CT', 'MRI', 'X-Ray', 'Ultrasound')"""),
]


def main():
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON")
    failed = 0

    print("=== TASK 5: DATA INTEGRITY VALIDATION ===\n")

    # 1. Primary keys unique and non-null
    print("[Primary keys are unique and non-null]")
    for table, pk in PRIMARY_KEYS.items():
        total, distinct, nulls = con.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT {pk}), SUM({pk} IS NULL) FROM {table}"
        ).fetchone()
        ok = total == distinct and not nulls
        failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {table}.{pk}: {total} rows, "
              f"{distinct} distinct, {nulls or 0} null")

    # 2. All foreign keys reference existing records
    broken = con.execute("PRAGMA foreign_key_check").fetchall()
    failed += bool(broken)
    print(f"\n[Foreign keys reference existing records]\n"
          f"  {'PASS' if not broken else 'FAIL'}  {len(broken)} violations")

    # 3. Rule-by-rule checks
    for description, query in CHECKS:
        rows = con.execute(query).fetchall()
        failed += bool(rows)
        print(f"\n[{description}]\n  {'PASS' if not rows else 'FAIL'}  {len(rows)} violations")
        for row in rows[:3]:
            print(f"    e.g. {row}")

    print(f"\n=== {failed} check(s) failed ===")
    con.close()


if __name__ == "__main__":
    main()
