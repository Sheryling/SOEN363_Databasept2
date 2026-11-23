import numbers
import re
import xml.etree.ElementTree as ET

import pandas as pd

tables = {}
malformed = {}
extra_lines = []

# Handles lines with too many values
def save_bad_line(bad_line):
    extra_lines.append({"file": key, "line": "|".join(bad_line)})
    return None

# ======================= SOURCE A =======================

files_A = ["ADMISSIONS.txt", "CLINICAL_NOTES.txt", "DIAG_ORDERS.txt", "DIAGNOSES.txt", "DISCHARGES.txt", "ICD9_DICT.txt",
           "ICU_RECORDS.txt", "LAB_EXAMS.txt", "PATIENTS.txt", "RAD_EXAMS.txt", "RAD_REPORTS.txt", "STAFF.txt",
           "SURGERIES.txt", "TRIAGE.txt", "UNIT_STAYS.txt", "UNITS.txt", "WARD_RECORDS.txt"]

for file in files_A:
    key = "A_" + file.replace(".txt", "")
    df = pd.read_csv("source_A_north_america/" + file, sep="|", on_bad_lines=save_bad_line, keep_default_na=False, engine="python")

    # Cutoff lines (lines with empty/missing cells)
    broken = df[df.isna().any(axis=1)]
    if len(broken) > 0:
        malformed[key] = broken
        df = df.dropna()

    tables[key] = df

# ======================= SOURCE B =======================

files_B = ["critical_care_obs.csv", "diagnoses.csv", "discharges.csv", "episodes.csv", "icd9_codes.csv", "imaging_reports.csv",
           "imaging.csv", "investigations.csv", "notes.csv", "operations.csv", "orders.csv", "patients.csv",
           "staff.csv", "triage.csv", "ward_obs.csv", "ward_stays.csv", "wards.csv"]

for file in files_B:
    key = "B_" + file.replace(".csv", "")
    df = pd.read_csv("source_B_europe/" + file, sep=";", on_bad_lines=save_bad_line, keep_default_na=False, engine="python")

    broken = df[df.isna().any(axis=1)]
    if len(broken) > 0:
        malformed[key] = broken
        df = df.dropna()

    tables[key] = df

# ======================= SOURCE C =======================
# One XML file. Each tag below is one entity; read_xml finds every element with that tag,
# at any depth in the tree, and makes one row per element.

tags_C = ["staff", "ward", "icdEntry", "patient", "admission", "triage", "diagnosis",
          "note", "surgery", "discharge", "order", "labExam", "imaging", "report",
          "wardStay", "ccRecord", "wardRound"]

root_C = ET.parse("source_C_asia/sakura_bay_export.xml").getroot()
c_element_context = {}


def collect_c_context(element, inherited):
    context = inherited.copy()
    context_columns = {
        "patient": ("pid", "pid"),
        "admission": ("aid", "aid"),
        "order": ("orderId", "orderId"),
        "imaging": ("examId", "examId"),
        "wardStay": ("stayId", "stayId"),
    }
    if element.tag in context_columns:
        context_column, attribute = context_columns[element.tag]
        context[context_column] = element.get(attribute)

    c_element_context[id(element)] = context
    for child in element:
        collect_c_context(child, context)


collect_c_context(root_C, {})

for tag in tags_C:
    key = "C_" + tag
    if tag == "triage":
        records = []
        for element in root_C.findall(".//triage"):
            record = {"triageId": element.get("triageId")}
            for child in element:
                if child.tag == "bloodPressure":
                    systolic = child.findtext("systolic")
                    diastolic = child.findtext("diastolic")
                    record["bloodPressure"] = (
                        f"{systolic}/{diastolic}"
                        if systolic is not None and diastolic is not None
                        else None
                    )
                    record["bloodPressure.systolic"] = systolic
                    record["bloodPressure.diastolic"] = diastolic
                else:
                    record[child.tag] = child.text
            records.append(record)
        df = pd.DataFrame.from_records(records)
    else:
        df = pd.read_xml("source_C_asia/sakura_bay_export.xml",
                         xpath=".//" + tag, parser="etree")

    elements = root_C.findall(".//" + tag)
    if len(elements) == len(df):
        context_columns = set().union(
            *(c_element_context[id(element)].keys() for element in elements)
        ) if elements else set()
        for column in context_columns:
            if column not in df.columns:
                df[column] = [
                    c_element_context[id(element)].get(column)
                    for element in elements
                ]

    # Records with no usable ID (missing, or not a number)
    # Ward codes (W01) and ICD-9 codes (V58.11) are not numbers on purpose, so they are only checked for missing
    id_col = df.columns[0]
    if tag in ["ward", "icdEntry"]:
        broken = df[df[id_col].isna()]
    else:
        broken = df[pd.to_numeric(df[id_col], errors="coerce").isna()]

    if len(broken) > 0:
        malformed[key] = broken
        df = df.drop(broken.index)

    tables[key] = df

# ======================= SOURCE D =======================
# One JSON file. Top level: staff, units, icd9Dictionary, patients.
# patients -> encounters -> triage, diagnoses, notes, procedures, discharge, orders, movements, wardRounds
#                           orders -> imaging (-> report), labResults
#                           movements -> criticalCareObservations
# Child records don't store their parent's ID (it's implied by nesting), so we add it as a column.

data = pd.read_json("source_D_africa/highveld_export.json", typ="series")

# One empty list per entity; rows get added as we walk through the file
rows_D = {"staff": [], "units": [], "icd9Dictionary": [], "patients": [], "encounters": [],
          "triage": [], "diagnoses": [], "notes": [], "procedures": [], "discharge": [],
          "orders": [], "imaging": [], "report": [], "labResults": [], "movements": [],
          "criticalCareObservations": [], "wardRounds": []}
bad_D = {"patients": [], "encounters": []}

# Adds one record to an entity's list: keeps its own fields, skips its child lists,
# and adds the parent's ID as an extra column
def add_row(entity, record, parent_col=None, parent_id=None):
    row = {}
    for field, value in record.items():
        if field in rows_D:          # a child entity (e.g. "triage" inside an encounter) -> its own table
            continue
        row[field] = value
    if parent_col is not None:
        row[parent_col] = parent_id
    rows_D[entity].append(row)

for record in data["staff"]:
    add_row("staff", record)
for record in data["units"]:
    add_row("units", record)
for record in data["icd9Dictionary"]:
    add_row("icd9Dictionary", record)

for p in data["patients"]:
    # Malformed: not a record (e.g. a piece of text), or no patient ID
    if not isinstance(p, dict) or p.get("patientRef") in (None, "", "unknown"):
        bad_D["patients"].append(str(p))
        continue
    add_row("patients", p)
    pid = p["patientRef"]

    for e in p.get("encounters", []):
        if not isinstance(e, dict):
            bad_D["encounters"].append(str(e) + "  (inside patientRef " + str(pid) + ")")
            continue
        add_row("encounters", e, "patientRef", pid)
        eid = e.get("encounterId")

        for child in ["triage", "diagnoses", "notes", "procedures", "wardRounds"]:
            for c in e.get(child, []):
                add_row(child, c, "encounterId", eid)
        if "discharge" in e:
            add_row("discharge", e["discharge"], "encounterId", eid)

        for o in e.get("orders", []):
            add_row("orders", o, "encounterId", eid)
            for im in o.get("imaging", []):
                add_row("imaging", im, "orderId", o.get("orderId"))
                if "report" in im:
                    add_row("report", im["report"], "examId", im.get("examId"))
            for lab in o.get("labResults", []):
                add_row("labResults", lab, "orderId", o.get("orderId"))

        for m in e.get("movements", []):
            add_row("movements", m, "encounterId", eid)
            for cc in m.get("criticalCareObservations", []):
                add_row("criticalCareObservations", cc, "movementId", m.get("movementId"))

# Turn each list into a table (json_normalize also splits nested values like name -> name.first, name.last)
for entity in rows_D:
    key = "D_" + entity
    tables[key] = pd.json_normalize(rows_D[entity])

for entity in bad_D:
    if len(bad_D[entity]) > 0:
        malformed["D_" + entity] = pd.DataFrame({"entry": bad_D[entity]})

# ======================= CHECKS =======================

# Prints all tables and their sizes
for key in tables:
    print(key, tables[key].shape)

print("\nMalformed (removed from tables):")
for key in malformed:
    print(key, len(malformed[key]))

print("\nLines with too many values:", len(extra_lines))

# ============================================================
#           Task 2: Clean and Standardize the Data
# ============================================================

# 1 - Missing Values
# ---------------------------------- missing value rules ----------------------------------------------
# 1. correct missing value only when it can be recovered with certainty from existing source data
# 2. retain the record with pd.NA when the missing field is optional (according to phase 1 schema)
# 3. reject/quarantine the record when a required field is missing and cant be recovered with certainty
# 4. no invention of missing clinical information
# -----------------------------------------------------------------------------------------------------
# no missing required values were able to be recovered with certainty from existing source data
# therefore, 0 records were corrected and all unresolved required-missing records were quarantined

required_attributes = {
    "Patient": ["patient_id", "health_insurance_num", "full_name", "date_of_birth", "life_status"],
    "Healthcare_Professional": ["staff_id", "first_name", "last_name", "staff_type"],
    "Unit": ["unit_id", "unit_name", "unit_type"],
    "ICD9_Code": ["icd9_code", "official_title", "description", "disease_category"],
    "Admission": ["admission_id", "patient_id", "admitting_healthcare_professional", "admission_datetime", "admission_type", "admission_source", "reason", "condition_on_arrival", "admission_status"],
    "TriageAssessment": ["triage_id", "admission_id", "nurse_id", "triage_datetime", "blood_pressure", "heart_rate", "pain_level", "symptoms", "allergies", "current_medication", "priority_level", "body_temp", "oxygen_sat"],
    "ClinicalNote": ["note_id", "admission_id", "physician_id", "note_type", "note_datetime", "suspected_condition"],
    "Diagnosis": ["diagnosis_id", "patient_id", "admission_id", "icd9_code", "diagnosis_datetime", "diagnosis_type", "diagnosing_physician_id"],
    "SurgicalProcedure": ["procedure_id", "admission_id", "surgeon_id", "procedure_type", "procedure_datetime"],
    "DischargeRecord": ["discharge_id", "admission_id", "condition_at_discharge", "responsible_physician_id"],
    "DiagnosticOrder": ["order_id", "admission_id", "patient_id", "requesting_physician_id", "requested_exam", "request_datetime", "order_status"],
    "RadiologyExamination": ["exam_id", "admission_id", "exam_type", "order_id", "exam_datetime", "body_area", "referring_physician_id", "rad_tech_id", "exam_status"],
    "RadiologyReport": ["report_id", "rad_exam_id", "radiologist_id", "report_datetime"],
    "DiagnosticExamination": ["diag_exam_id", "order_id", "exam_type", "exam_datetime", "performed_by_id", "exam_status"],
    "UnitStay": ["unit_stay_id", "admission_id", "unit_id", "ward_room", "entry_datetime", "responsible_physician_id", "transfer_reason"],
    "CriticalCareRecord": ["record_id", "unit_stay_id", "record_datetime"],
    "GeneralWardRecord": ["ward_record_id", "admission_id", "record_datetime"]
}

# source-specific attributes for every entity
patient_required_attributes = {
    "A_PATIENTS": ["PatID", "HealthCardNo", "PatientName", "DOB", "VitalStatus"],
    "B_patients": ["patient_no", "insurance_number", "patient_name", "birth_date", "vital_status"],
    "C_patient": ["pid", "insuranceNo", "name", "birthDate", "vitalStatus"],
    "D_patients": ["patientRef", "medicalAidNumber", "name.first", "name.last", "dob", "isDeceased"]
}

healthcare_professional_required_attributes = {
    "A_STAFF": ["StaffID", "FirstName", "LastName", "StaffType"],
    "B_staff": ["staff_no", "first_name", "last_name", "role"],
    "C_staff": ["staffNo", "firstName", "lastName", "role"],
    "D_staff": ["staffRef", "firstName", "lastName", "cadre"]
}

unit_required_attributes = {
    "A_UNITS": ["UnitID", "UnitName", "UnitType"],
    "B_wards": ["ward_no", "ward_name", "ward_category"],
    "C_ward": ["wardCode", "wardName", "wardCategory"],
    "D_units": ["unitCode", "unitName", "unitKind"]
}

icd9_code_required_attributes = {
    "A_ICD9_DICT": ["ICD9Code", "OfficialTitle", "Description", "DiseaseCategory"],
    "B_icd9_codes": ["icd9", "official_title", "description", "disease_category"],
    "C_icdEntry": ["icdCode", "officialTitle", "description", "diseaseCategory"],
    "D_icd9Dictionary": ["icd9", "officialTitle", "description", "diseaseCategory"]
}

admission_required_attributes = {
    "A_ADMISSIONS": ["AdmitID", "PatID", "AdmittingMD", "AdmitDT", "AdmissionType", "AdmissionSource", "Reason", "ConditionOnArrival", "AdmissionStatus"],
    "B_episodes": ["episode_no", "patient_no", "admitting_clinician", "episode_start", "episode_type", "referral_source", "reason", "condition_on_arrival", "episode_status"],
    "C_admission": ["aid", "admittingHealthcareProfessional", "admitTime", "admitType", "admissionSource", "reason", "conditionOnArrival", "status"],
    "D_encounters": ["encounterId", "patientRef", "admittingHealthcareProfessional", "admittedAt", "encounterType", "arrivalMode", "reason", "conditionOnArrival", "encounterStatus"]
}

triage_required_attributes = {
    "A_TRIAGE": ["TriageID", "AdmitID", "NurseID", "TriageDatetime", "BP", "HR", "PainScore", "Symptoms", "Allergies", "CurrentMedication", "TriageLevel", "TempF", "SpO2Pct"],
    "B_triage": ["triage_id", "episode_no", "nurse_id", "triage_datetime", "blood_pressure", "heart_rate", "pain_level", "symptoms", "allergies", "current_medication", "triage_category", "temp_c", "spo2"],
    "C_triage": ["triageId", "nurseId", "triageDatetime", "bloodPressure", "heartRate", "painLevel", "symptoms", "allergies", "triageLevel", "temperatureC", "spo2"],
    "D_triage": ["triageId", "encounterId", "nurseId", "triageDatetime", "bloodPressure.systolic", "bloodPressure.diastolic", "heartRate", "painLevel", "symptoms", "allergies", "currentMedication", "triageColour", "tempCelsius", "spo2Fraction"]
}

clinical_note_required_attributes = {
    "A_CLINICAL_NOTES": ["NoteId", "AdmitID", "PhysicianId", "NoteType", "NoteDatetime", "SuspectedCondition"],
    "B_notes": ["note_id", "episode_no", "physician_id", "note_type", "note_datetime", "suspected_condition"],
    "C_note": ["noteId", "physicianId", "noteType", "noteDatetime", "suspectedCondition"],
    "D_notes": ["noteId", "encounterId", "physicianId", "noteType", "noteDatetime", "suspectedCondition"]
}

diagnosis_required_attributes = {
    "A_DIAGNOSES": ["DiagnosisId", "PatID", "AdmitID", "ICD9Code", "DiagnosisDatetime", "DiagnosisType", "DiagnosingPhysicianId"],
    "B_diagnoses": ["diagnosis_id", "patient_no", "episode_no", "icd9", "diagnosis_datetime", "diagnosis_type", "diagnosing_physician_id"],
    "C_diagnosis": ["diagnosisId", "pid", "icdCode", "diagnosisDatetime", "diagnosisType", "diagnosingPhysicianId"],
    "D_diagnoses": ["diagnosisId", "patientRef", "encounterId", "icd9", "diagnosisDatetime", "diagnosisType", "diagnosingPhysicianId"]
}

surgical_procedure_required_attributes = {
    "A_SURGERIES": ["ProcedureId", "AdmitID", "SurgeonId", "ProcedureType", "ProcedureDatetime"],
    "B_operations": ["operation_no", "episode_no", "surgeon_no", "operation", "operation_datetime"],
    "C_surgery": ["procedureId", "surgeonId", "procedureType", "procedureDatetime"],
    "D_procedures": ["procedureId", "encounterId", "surgeonId", "procedureType", "procedureDatetime"]
}

discharge_record_required_attributes = {
    "A_DISCHARGES": ["DischargeId", "AdmitID", "ConditionAtDischarge", "ResponsiblePhysicianId"],
    "B_discharges": ["discharge_id", "episode_no", "condition_at_discharge", "responsible_physician_id"],
    "C_discharge": ["dischargeId", "conditionAtDischarge", "responsiblePhysicianId"],
    "D_discharge": ["dischargeId", "encounterId", "conditionAtDischarge", "responsiblePhysicianId"]
}

diagnostic_order_required_attributes = {
    "A_DIAG_ORDERS": ["OrderID", "AdmitID", "PatID", "RequestingPhysicianId", "RequestedExam", "RequestDatetime", "OrderStatus"],
    "B_orders": ["order_id", "episode_no", "patient_no", "requesting_physician_id", "requested_exam", "request_datetime", "order_status"],
    "C_order": ["orderId", "pid", "requestingPhysicianId", "requestedExam", "requestDatetime", "orderStatus"],
    "D_orders": ["orderId", "patientRef", "encounterId", "requestingPhysicianId", "requestedExam", "requestDatetime", "orderStatus"]
}

radiology_examination_required_attributes = {
    "A_RAD_EXAMS": ["RadExamID", "AdmitID", "ExamType", "OrderID", "ExamDatetime", "BodyArea", "ReferringPhysicianId", "RadTechId", "ExamStatus"],
    "B_imaging": ["exam_id", "episode_no", "exam_type", "order_id", "exam_datetime", "body_area", "referring_physician_id", "rad_tech_id", "exam_status"],
    "C_imaging": ["examId", "aid", "examType", "examDatetime", "bodyArea", "referringPhysicianId", "radTechId", "examStatus"],
    "D_imaging": ["examId", "encounterId", "orderId", "examType", "examDatetime", "bodyArea", "referringPhysicianId", "radTechId", "examStatus"]
}

radiology_report_required_attributes = {
    "A_RAD_REPORTS": ["ReportId", "RadExamID", "RadiologistId", "ReportDatetime"],
    "B_imaging_reports": ["report_id", "rad_exam_id", "radiologist_id", "report_datetime"],
    "C_report": ["reportId", "radiologistId", "reportDatetime"],
    "D_report": ["reportId", "examId", "radiologistId", "reportDatetime"]
}

diagnostic_examination_required_attributes = {
    "A_LAB_EXAMS": ["LabExamID", "OrderID", "ExamType", "ExamDatetime", "PerformedById", "ExamStatus"],
    "B_investigations": ["diag_exam_id", "order_id", "exam_type", "exam_datetime", "performed_by_id", "exam_status"],
    "C_labExam": ["diagExamId", "examType", "examDatetime", "performedById", "examStatus"],
    "D_labResults": ["diagExamId", "orderId", "examType", "examDatetime", "performedById", "examStatus"]
}

unit_stay_required_attributes = {
    "A_UNIT_STAYS": ["StayID", "AdmitID", "UnitID", "WardRoom", "InDT", "ResponsiblePhysicianId", "TransferReason"],
    "B_ward_stays": ["ward_stay_no", "episode_no", "ward_no", "ward_room", "ward_in", "responsible_physician_id", "transfer_reason"],
    "C_wardStay": ["stayId", "wardCode", "wardRoom", "inTime", "responsiblePhysicianId", "transferReason"],
    "D_movements": ["movementId", "encounterId", "unitCode", "wardRoom", "inAt", "responsiblePhysicianId", "transferReason"]
}

critical_care_record_required_attributes = {
    "A_ICU_RECORDS": ["RecordId", "StayID", "RecordDatetime"],
    "B_critical_care_obs": ["record_id", "ward_stay_no", "record_datetime"],
    "C_ccRecord": ["recordId", "recordDatetime"],
    "D_criticalCareObservations": ["recordId", "movementId", "recordDatetime"]
}

general_ward_record_required_attributes = {
    "A_WARD_RECORDS": ["WardRecordId", "AdmitID", "RecordDatetime"],
    "B_ward_obs": ["ward_record_id", "episode_no", "record_datetime"],
    "C_wardRound": ["wardRecordId", "recordDatetime"],
    "D_wardRounds": ["wardRecordId", "encounterId", "recordDatetime"]
}

# mapping the source-specific attributes to the phase 1 attributes
required_attribute_mappings = {}
required_attribute_mappings.update(patient_required_attributes)
required_attribute_mappings.update(healthcare_professional_required_attributes)
required_attribute_mappings.update(unit_required_attributes)
required_attribute_mappings.update(icd9_code_required_attributes)
required_attribute_mappings.update(admission_required_attributes)
required_attribute_mappings.update(triage_required_attributes)
required_attribute_mappings.update(clinical_note_required_attributes)
required_attribute_mappings.update(diagnosis_required_attributes)
required_attribute_mappings.update(surgical_procedure_required_attributes)
required_attribute_mappings.update(discharge_record_required_attributes)
required_attribute_mappings.update(diagnostic_order_required_attributes)
required_attribute_mappings.update(radiology_examination_required_attributes)
required_attribute_mappings.update(radiology_report_required_attributes)
required_attribute_mappings.update(diagnostic_examination_required_attributes)
required_attribute_mappings.update(unit_stay_required_attributes)
required_attribute_mappings.update(critical_care_record_required_attributes)
required_attribute_mappings.update(general_ward_record_required_attributes)

# source-specific missing value markers (to normalize later)
missing_value_markers = {
    "A": ["N/A", ""],
    "B": ["NULL", ""],
    "C": ["-", ""],
    "D": ["unknown", ""]
}

# making sure that we preserve original source files as they are
cleaned_tables = {}
for key, df in tables.items():
    cleaned_tables[key] = df.copy()

# normalizing missing values of all sources for consistency
for table_name, table in cleaned_tables.items():
    source = table_name[0]
    table.replace(missing_value_markers[source], pd.NA, inplace=True)

# counting how many missing values exist in each table after normalizing
for table_name, table in cleaned_tables.items():
    missing_count = table.isna().sum().sum()
    if missing_count > 0:
        print(table_name, missing_count)

# finding records that are missing at least one required attribute
missing_required_records = {}
for table_name, required_columns in required_attribute_mappings.items():
    table = cleaned_tables[table_name]
    missing_required = table[required_columns].isna().any(axis=1)
    missing_required_records[table_name] = table[missing_required].copy()
    if missing_required.sum() > 0:
        print(table_name, "records missing required values:", missing_required.sum())

# quarantining records that have missing required attributes
quarantined_records = {}
for table_name, records in missing_required_records.items():
    if len(records) > 0:
        quarantined_records[table_name] = records.copy()

# giving a reason for why each record was quarantined
for table_name, records in quarantined_records.items():
    required_columns = required_attribute_mappings[table_name]
    records["quarantine_reason"] = records[required_columns].apply(lambda row: "Missing required attribute(s): " + ", ".join(row.index[row.isna()]), axis=1)

# removing quarantined records from our cleaned tables
for table_name, records in quarantined_records.items():
    cleaned_tables[table_name] = cleaned_tables[table_name].drop(index=records.index)

# making sure that no cleaned record is still missing a required attribute
for table_name, required_columns in required_attribute_mappings.items():
    remaining_missing_required = cleaned_tables[table_name][required_columns].isna().any(axis=1).sum()
    if remaining_missing_required > 0:
        print(table_name, "records still missing required values:", remaining_missing_required)

# giving a summary of quarantined records due to missing required values
total_quarantined = 0
for table_name, records in quarantined_records.items():
    quarantined_count = len(records)
    total_quarantined += quarantined_count
    print(table_name, "quarantined records:", quarantined_count)
print("Total quarantined records:", total_quarantined)

# counting optional missing values that were retained
total_optional_nulls = 0
for table_name, table in cleaned_tables.items():
    required_columns = required_attribute_mappings[table_name]
    optional_columns = [
        column for column in table.columns
        if column not in required_columns
    ]
    optional_nulls = table[optional_columns].isna().sum().sum()
    total_optional_nulls += optional_nulls
    if optional_nulls > 0:
        print(table_name, "retained optional nulls:", optional_nulls)
print("Total retained optional nulls:", total_optional_nulls)

# 2 - Duplicates
# ---------------------------------- duplicate entity rule -----------------------------------------
# duplicate entity candidates are detected when the same entity ID appears more than once.
# duplicate candidates are inspected for conflicting substantive values.
# no substantive conflicts were found in this dataset, so the first occurrence is kept.
# redundant copies are removed.
# --------------------------------------------------------------------------------------------------

# finding exact duplicate records
exact_duplicate_records = {}
for table_name, table in cleaned_tables.items():
    duplicates = table[table.duplicated(keep=False)]
    if len(duplicates) > 0:
        exact_duplicate_records[table_name] = duplicates.copy()
        print(table_name, "exact duplicate records:", len(duplicates))

# removing exact duplicate records while keeping one copy of the record
exact_duplicates_removed = 0
for table_name, table in cleaned_tables.items():
    before_count = len(table)
    cleaned_tables[table_name] = table.drop_duplicates(keep="first")
    after_count = len(cleaned_tables[table_name])
    removed_count = before_count - after_count
    exact_duplicates_removed += removed_count
    if removed_count > 0:
        print(table_name, "exact duplicates removed:", removed_count)
print("Total exact duplicates removed:", exact_duplicates_removed)

# finding duplicate entities based on repeated entity IDs
duplicate_entity_records = {}
for table_name, required_columns in required_attribute_mappings.items():
    table = cleaned_tables[table_name]
    id_column = required_columns[0]
    duplicate_entities = table[table.duplicated(subset=[id_column], keep=False)]
    if len(duplicate_entities) > 0:
        duplicate_entity_records[table_name] = duplicate_entities.copy()
        print(table_name, "duplicate entity records:", len(duplicate_entities))

# removing redundant copies and keeping only one copy
duplicate_entities_removed = 0
for table_name, records in duplicate_entity_records.items():
    id_column = required_attribute_mappings[table_name][0]
    before_count = len(cleaned_tables[table_name])
    cleaned_tables[table_name] = cleaned_tables[table_name].drop_duplicates(subset=[id_column], keep="first")
    after_count = len(cleaned_tables[table_name])
    removed_count = before_count - after_count
    duplicate_entities_removed += removed_count
    print(table_name, "duplicate entities removed:", removed_count)
print("Total duplicate entities removed:", duplicate_entities_removed)

# making sure that duplicate records were successfully removed
for table_name, table in cleaned_tables.items():
    exact_duplicates_left = table.duplicated().sum()
    if exact_duplicates_left > 0:
        print(table_name, "exact duplicates left:", exact_duplicates_left)
for table_name, required_columns in required_attribute_mappings.items():
    id_column = required_columns[0]
    duplicate_ids_left = cleaned_tables[table_name].duplicated(subset=[id_column]).sum()
    if duplicate_ids_left > 0:
        print(table_name, "duplicate ids left:", duplicate_ids_left)

# 3 - Text
# ---------------------------------- text standardization rules -----------------------------------------
# 1. remove leading and trailing whitespace from text values
# 2. convert empty strings created by whitespace cleaning to pd.NA
# 3. standardize capitalization only for appropriate descriptive text fields
# 4. standardize categorical labels to uppercase without changing their meaning
# 5. no modification of identifiers, codes, phone numbers, or other values where case may be significant
# -------------------------------------------------------------------------------------------------------

# standardizing whitespace in text columns
for table_name, table in cleaned_tables.items():
    for column in table.select_dtypes(include="str").columns:
        table[column] = table[column].str.strip()
        table[column] = table[column].replace("", pd.NA)

# checking if whitespace cleaning might have created any new missing required values
text_missing_required_records = {}
for table_name, required_columns in required_attribute_mappings.items():
    table = cleaned_tables[table_name]
    missing_required = table[required_columns].isna().any(axis=1)
    if missing_required.any():
        text_missing_required_records[table_name] = table[missing_required].copy()
        print(table_name, "records missing required values after text cleaning:", missing_required.sum())

# standardizing capitalization in appropriate text columns
capitalization_columns = ["PatientName", "patient_name", "name", "FirstName", "LastName", "first_name", "last_name", "firstName", "lastName", "UnitName", "unit_name", "ward_name", "wardName"]
for table_name, table in cleaned_tables.items():
    for column in capitalization_columns:
        if column in table.columns:
            table[column] = table[column].str.title()

# standardizing categorical labels
categorical_columns = ["VitalStatus", "vital_status", "vitalStatus", "StaffType", "role", "cadre", "UnitType", "unit_type", "ward_category", "wardCategory", "unitKind", "AdmissionType", "episode_type", "admitType", "encounterType", "AdmissionSource", "referral_source", "admissionSource", "arrivalMode", "AdmissionStatus", "episode_status", "status", "encounterStatus", "NoteType", "note_type", "noteType", "DiagnosisType", "diagnosis_type", "diagnosisType", "OrderStatus", "order_status", "orderStatus", "ExamStatus", "exam_status", "examStatus"]
for table_name, table in cleaned_tables.items():
    for column in categorical_columns:
        if column in table.columns:
            table[column] = table[column].str.upper()

# 4 - Dates and Timestamps
# ---------------------------------- date/time standardization rules ------------------------------------
# 1. convert valid dates and timestamps to pandas datetime representation for consistency
# 2. preserve missing dates as pd.NA/NaT
# 3. dont guess ambiguous dates when their interpretation cant be determined with certainty
# 4. invalid or unresolved required dates must be quarantined instead of invented
# 5. document each source's timezone and how unknown/ambiguous timezones are treated
# -------------------------------------------------------------------------------------------------------
#                                          for timezones:
# sources A, B, and C dont provide timezone information, so no timezone is guessed.
# their timestamps remain as timezone-naive.
# source D does provide an explicit UTC offset in ISO-8601 timestamps.
# source D timestamps are converted to UTC for consistency
# ambiguous or invalid dates arent guessed and are identified for review/quarantine.

# date and timestamp columns for every table
date_time_columns = {
    "A_ADMISSIONS": ["AdmitDT", "DischDT"],
    "A_CLINICAL_NOTES": ["NoteDatetime"],
    "A_DIAG_ORDERS": ["RequestDatetime"],
    "A_DIAGNOSES": ["DiagnosisDatetime"],
    "A_ICU_RECORDS": ["RecordDatetime"],
    "A_LAB_EXAMS": ["ExamDatetime"],
    "A_PATIENTS": ["DOB", "DeathDT"],
    "A_RAD_EXAMS": ["ExamDatetime"],
    "A_RAD_REPORTS": ["ReportDatetime"],
    "A_SURGERIES": ["ProcedureDatetime"],
    "A_TRIAGE": ["TriageDatetime"],
    "A_UNIT_STAYS": ["InDT", "OutDT"],
    "A_WARD_RECORDS": ["RecordDatetime"],
    "B_critical_care_obs": ["record_datetime"],
    "B_episodes": ["episode_start", "episode_end"],
    "B_diagnoses": ["diagnosis_datetime"],
    "B_imaging_reports": ["report_datetime"],
    "B_imaging": ["exam_datetime"],
    "B_investigations": ["exam_datetime"],
    "B_notes": ["note_datetime"],
    "B_operations": ["operation_datetime"],
    "B_orders": ["request_datetime"],
    "B_patients": ["birth_date", "date_of_death"],
    "B_triage": ["triage_datetime"],
    "B_ward_obs": ["record_datetime"],
    "B_ward_stays": ["ward_in", "ward_out"],
    "C_patient": ["birthDate", "deathTime"],
    "C_admission": ["admitTime", "dischargeTime"],
    "C_triage": ["triageDatetime"],
    "C_diagnosis": ["diagnosisDatetime"],
    "C_note": ["noteDatetime"],
    "C_surgery": ["procedureDatetime"],
    "C_order": ["requestDatetime"],
    "C_labExam": ["examDatetime"],
    "C_imaging": ["examDatetime"],
    "C_report": ["reportDatetime"],
    "C_wardStay": ["inTime", "outTime"],
    "C_ccRecord": ["recordDatetime"],
    "C_wardRound": ["recordDatetime"],
    "D_patients": ["dob", "deceasedAt"],
    "D_encounters": ["admittedAt", "dischargedAt"],
    "D_triage": ["triageDatetime"],
    "D_diagnoses": ["diagnosisDatetime"],
    "D_notes": ["noteDatetime"],
    "D_procedures": ["procedureDatetime"],
    "D_orders": ["requestDatetime"],
    "D_imaging": ["examDatetime"],
    "D_report": ["reportDatetime"],
    "D_labResults": ["examDatetime"],
    "D_movements": ["inAt", "outAt"],
    "D_criticalCareObservations": ["recordDatetime"],
    "D_wardRounds": ["recordDatetime"]
}

# expected date/time formats for every source
date_formats = {
    "A": "%m/%d/%Y %I:%M %p",
    "B": "%d/%m/%Y %H:%M",
    "C": "%Y/%m/%d %H:%M:%S"
}

# columns that contain dates without a time
date_only_columns = {
    ("A_PATIENTS", "DOB"): "%m/%d/%Y",
    ("B_patients", "birth_date"): "%d/%m/%Y",
    ("C_patient", "birthDate"): "%Y/%m/%d",
    ("D_patients", "dob"): "%Y-%m-%d"
}

# finding invalid or inconsistent date/time values before converting them
invalid_date_values = {}
for table_name, columns in date_time_columns.items():
    table = cleaned_tables[table_name]
    source = table_name[0]
    for column in columns:
        original_values = table[column]
        # format for date-only columns
        if (table_name, column) in date_only_columns:
            expected_format = date_only_columns[(table_name, column)]
            parsed_values = pd.to_datetime(original_values, format=expected_format, errors="coerce")
        # format for sources A, B, and C
        elif source in date_formats:
            expected_format = date_formats[source]
            parsed_values = pd.to_datetime(original_values, format=expected_format, errors="coerce")
        # format for source D
        else:
            parsed_values = pd.to_datetime(original_values.astype("string"), format="ISO8601", errors="coerce",utc=True)
        invalid_mask = original_values.notna() & parsed_values.isna()
        if invalid_mask.any():
            invalid_date_values[(table_name, column)] = table.loc[invalid_mask, [column]].copy()
            print(table_name, "-", column, "invalid/inconsistent values:", invalid_mask.sum())

# valid date/time formats that can be corrected safely
alternative_date_formats = {
    "A": ["%m/%d/%y %I:%M %p", "%Y-%m-%d %H:%M", "%d/%m/%Y %I:%M %p"],
    "B": ["%Y-%m-%dT%H:%M", "%d %b %Y %H:%M", "%m/%d/%Y %H:%M"],
    "C": ["%Y%m%d%H%M%S"]
}
alternative_date_only_formats = {
    ("A_PATIENTS", "DOB"): ["%m/%d/%y"]
}

# converting valid and safely correctable dates/timestamps
unresolved_date_values = {}
for table_name, columns in date_time_columns.items():
    table = cleaned_tables[table_name]
    source = table_name[0]
    for column in columns:
        # remembering which values were originally present
        original_non_missing = table[column].notna()
        converted_values = []
        for value in table[column]:
            # retain missing values
            if pd.isna(value):
                converted_values.append(pd.NaT)
                continue
            parsed_value = pd.NaT
            # date-only columns
            if (table_name, column) in date_only_columns:
                formats_to_try = [date_only_columns[(table_name, column)]]
                if (table_name, column) in alternative_date_only_formats:
                    formats_to_try += alternative_date_only_formats[(table_name, column)]
                for date_format in formats_to_try:
                    parsed_value = pd.to_datetime(value, format=date_format, errors="coerce")
                    if not pd.isna(parsed_value):
                        break
            # source D
            elif source == "D":
                if isinstance(value, (int, float)):
                    parsed_value = pd.to_datetime(value, unit="ms", errors="coerce", utc=True)
                else:
                    parsed_value = pd.to_datetime(str(value), format="ISO8601", errors="coerce", utc=True)
            # normal date/time columns for A, B, and C
            else:
                formats_to_try = [date_formats[source]] + alternative_date_formats[source]
                for date_format in formats_to_try:
                    parsed_value = pd.to_datetime(value, format=date_format, errors="coerce")
                    if not pd.isna(parsed_value):
                        break
            converted_values.append(parsed_value)
        # replacing original values with standardized datetime values
        table[column] = converted_values
        # values that existed originally but could not be interpreted
        unresolved_mask = original_non_missing & table[column].isna()
        if unresolved_mask.any():
            unresolved_date_values[(table_name, column)] = table.index[unresolved_mask].tolist()
print("\nUnresolved date/time values:")
for (table_name, column), count in unresolved_date_values.items():
    print(table_name, "-", column, ":", count)

# quarantining records that have unresolved required date/time values
date_quarantined_records = {}
for (table_name, column), row_indexes in unresolved_date_values.items():
    # only quarantine if this date/time field is required
    if column in required_attribute_mappings.get(table_name, []):
        if table_name not in date_quarantined_records:
            date_quarantined_records[table_name] = {}
        for row_index in row_indexes:
            if row_index not in date_quarantined_records[table_name]:
                date_quarantined_records[table_name][row_index] = []
            date_quarantined_records[table_name][row_index].append(column)

# creating quarantine records with reasons for their unresolved required dates
date_quarantine_tables = {}
for table_name, row_info in date_quarantined_records.items():
    row_indexes = list(row_info.keys())
    records = cleaned_tables[table_name].loc[row_indexes].copy()
    reasons = []
    for row_index in row_indexes:
        columns = row_info[row_index]
        reason = "Unresolved required date/time value(s): " + ", ".join(columns)
        reasons.append(reason)
    records["quarantine_reason"] = reasons
    date_quarantine_tables[table_name] = records

# removing records with unresolved required date/time values from cleaned tables
for table_name, records in date_quarantine_tables.items():
    cleaned_tables[table_name] = cleaned_tables[table_name].drop(index=records.index)

# making sure that no unresolved required date/time values remain
for table_name, columns in date_time_columns.items():
    table = cleaned_tables[table_name]
    for column in columns:
        if column in required_attribute_mappings.get(table_name, []):
            remaining_missing = table[column].isna().sum()
            if remaining_missing > 0:
                print(table_name, "-", column, "still has unresolved required dates:", remaining_missing)

# summarizing date/time cleaning
total_date_issues = sum(len(records) for records in invalid_date_values.values())
total_unresolved_dates = sum(len(indexes) for indexes in unresolved_date_values.values())
total_corrected_dates = total_date_issues - total_unresolved_dates
total_date_quarantined = sum(len(records) for records in date_quarantine_tables.values())
print("\nDate/time cleaning summary:")
print("Invalid/inconsistent date values detected:", total_date_issues)
print("Safely corrected date values:", total_corrected_dates)
print("Unresolved date values:", total_unresolved_dates)
print("Records quarantined due to required invalid dates:", total_date_quarantined)

# 5 - Numeric Values and Units
# ---------------------------------- numeric value and unit rules ---------------------------------------
# 1. plausibility bounds are broad and flag data-quality issues, not clinical decision thresholds
# 2. invalid values are set to pd.NA in the standardized columns
# 3. original source columns remain unchanged
# -------------------------------------------------------------------------------------------------------
triage_columns = {
    "A_TRIAGE": {
        "id": "TriageID", "blood_pressure": "BP", "heart_rate": "HR",
        "pain_level": "PainScore", "body_temp": "TempF", "oxygen_sat": "SpO2Pct",
    },
    "B_triage": {
        "id": "triage_id", "blood_pressure": "blood_pressure", "heart_rate": "heart_rate",
        "pain_level": "pain_level", "body_temp": "temp_c", "oxygen_sat": "spo2",
    },
    "C_triage": {
        "id": "triageId", "blood_pressure": "bloodPressure",
        "systolic": "bloodPressure.systolic", "diastolic": "bloodPressure.diastolic",
        "heart_rate": "heartRate", "pain_level": "painLevel",
        "body_temp": "temperatureC", "oxygen_sat": "spo2",
    },
    "D_triage": {
        "id": "triageId", "systolic": "bloodPressure.systolic",
        "diastolic": "bloodPressure.diastolic", "heart_rate": "heartRate",
        "pain_level": "painLevel", "body_temp": "tempCelsius",
        "oxygen_sat": "spo2Fraction",
    },
}

numeric_quality_flags = []
numeric_conversion_counts = {}

def parse_numeric_value(value):
    if pd.isna(value):
        return None
    text = str(value).strip().lower().replace(",", ".")
    text = re.sub(r"\s*(?:mmhg|bpm|%|°c|°f|c|f)\s*$", "", text)
    try:
        return float(text)
    except ValueError:
        return None

def add_numeric_flag(table_name, row, field, raw_value, flag, details):
    numeric_quality_flags.append({
        "table": table_name,
        "record_id": row[triage_columns[table_name]["id"]],
        "field": field,
        "raw_value": raw_value,
        "flag": flag,
        "details": details,
    })

def is_in_range(value, minimum, maximum):
    return value is not None and minimum <= value <= maximum

for table_name, columns in triage_columns.items():
    table = cleaned_tables[table_name]
    source = table_name[0]
    systolic_values = []
    diastolic_values = []
    heart_rate_values = []
    pain_level_values = []
    body_temp_values = []
    oxygen_sat_values = []
    normal_unit_conversions = 0

    for _, row in table.iterrows():
        if "systolic" in columns:
            systolic_raw = row[columns["systolic"]]
            diastolic_raw = row[columns["diastolic"]]
            systolic = parse_numeric_value(systolic_raw)
            diastolic = parse_numeric_value(diastolic_raw)
            blood_pressure_raw = f"{systolic_raw}/{diastolic_raw}"
        else:
            blood_pressure_raw = row[columns["blood_pressure"]]
            pressure_match = re.fullmatch(
                r"\s*([-+]?\d+(?:[.,]\d+)?)\s*/\s*([-+]?\d+(?:[.,]\d+)?)"
                r"(?:\s*mmhg)?\s*",
                str(blood_pressure_raw),
                flags=re.IGNORECASE,
            )
            if pressure_match:
                systolic = parse_numeric_value(pressure_match.group(1))
                diastolic = parse_numeric_value(pressure_match.group(2))
            else:
                systolic = diastolic = None

        if systolic is None or diastolic is None:
            add_numeric_flag(
                table_name, row, "blood_pressure", blood_pressure_raw,
                "invalid_numeric", "Expected numeric systolic/diastolic values in mmHg.",
            )
            systolic_values.append(pd.NA)
            diastolic_values.append(pd.NA)
        elif not (40 <= systolic <= 300 and 20 <= diastolic <= 200 and systolic > diastolic):
            add_numeric_flag(
                table_name, row, "blood_pressure", blood_pressure_raw,
                "invalid_numeric",
                "Expected systolic 40-300 mmHg, diastolic 20-200 mmHg, and systolic greater than diastolic.",
            )
            systolic_values.append(pd.NA)
            diastolic_values.append(pd.NA)
        else:
            systolic_values.append(systolic)
            diastolic_values.append(diastolic)

        heart_rate_raw = row[columns["heart_rate"]]
        heart_rate = parse_numeric_value(heart_rate_raw)
        if not is_in_range(heart_rate, 1, 300):
            add_numeric_flag(
                table_name, row, "heart_rate", heart_rate_raw, "invalid_numeric",
                "Expected a numeric heart rate from 1 to 300 beats per minute.",
            )
            heart_rate_values.append(pd.NA)
        else:
            heart_rate_values.append(heart_rate)

        pain_level_raw = row[columns["pain_level"]]
        pain_level = parse_numeric_value(pain_level_raw)
        if not is_in_range(pain_level, 0, 10):
            add_numeric_flag(
                table_name, row, "pain_level", pain_level_raw, "invalid_numeric",
                "Expected a numeric pain score from 0 to 10.",
            )
            pain_level_values.append(pd.NA)
        else:
            pain_level_values.append(pain_level)

        body_temp_raw = row[columns["body_temp"]]
        body_temp = parse_numeric_value(body_temp_raw)
        standardized_temp = None
        if source == "A" and is_in_range(body_temp, 25, 45):
            standardized_temp = body_temp
            add_numeric_flag(
                table_name, row, "body_temp", body_temp_raw, "unit_inconsistency_corrected",
                "Celsius value found in the Fahrenheit field; retained as Celsius.",
            )
        elif source in ("B", "C") and is_in_range(body_temp, 80, 120):
            standardized_temp = (body_temp - 32) * 5 / 9
            add_numeric_flag(
                table_name, row, "body_temp", body_temp_raw, "unit_inconsistency_corrected",
                "Fahrenheit value found in the Celsius field; converted to Celsius.",
            )
        elif source == "D" and is_in_range(body_temp, 273.15, 373.15):
            standardized_temp = body_temp - 273.15
            add_numeric_flag(
                table_name, row, "body_temp", body_temp_raw, "unit_inconsistency_corrected",
                "Kelvin value found in the Celsius field; converted to Celsius.",
            )
        elif source == "A" and is_in_range(body_temp, 80, 120):
            standardized_temp = (body_temp - 32) * 5 / 9
            normal_unit_conversions += 1
        elif is_in_range(body_temp, 25, 45):
            standardized_temp = body_temp

        if standardized_temp is None or not is_in_range(standardized_temp, 25, 45):
            add_numeric_flag(
                table_name, row, "body_temp", body_temp_raw, "invalid_numeric",
                "Could not interpret a valid body temperature in the source's expected units.",
            )
            body_temp_values.append(pd.NA)
        else:
            body_temp_values.append(standardized_temp)

        oxygen_sat_raw = row[columns["oxygen_sat"]]
        oxygen_sat = parse_numeric_value(oxygen_sat_raw)
        if source == "D" and is_in_range(oxygen_sat, 0.000001, 1):
            standardized_oxygen_sat = oxygen_sat * 100
            normal_unit_conversions += 1
        elif source == "D" and is_in_range(oxygen_sat, 50, 100):
            standardized_oxygen_sat = oxygen_sat
            add_numeric_flag(
                table_name, row, "oxygen_sat", oxygen_sat_raw, "unit_inconsistency_corrected",
                "Percent value found in the fraction field; converted to a 0-1 fraction then standardized to percent.",
            )
        elif source == "D" and oxygen_sat is not None and 1 < oxygen_sat < 50:
            standardized_oxygen_sat = None
        elif source != "D" and is_in_range(oxygen_sat, 0.000001, 1):
            standardized_oxygen_sat = oxygen_sat * 100
            add_numeric_flag(
                table_name, row, "oxygen_sat", oxygen_sat_raw, "unit_inconsistency_corrected",
                "Fraction found in a percent field; converted to percentage.",
            )
        else:
            standardized_oxygen_sat = oxygen_sat

        if not is_in_range(standardized_oxygen_sat, 0.000001, 100):
            add_numeric_flag(
                table_name, row, "oxygen_sat", oxygen_sat_raw, "invalid_numeric",
                "Expected oxygen saturation greater than 0 and at most 100 percent.",
            )
            oxygen_sat_values.append(pd.NA)
        else:
            oxygen_sat_values.append(standardized_oxygen_sat)

    table["blood_pressure_systolic_mmhg"] = pd.array(systolic_values, dtype="Float64")
    table["blood_pressure_diastolic_mmhg"] = pd.array(diastolic_values, dtype="Float64")
    table["heart_rate_bpm"] = pd.array(heart_rate_values, dtype="Float64")
    table["pain_level_0_10"] = pd.array(pain_level_values, dtype="Float64")
    table["body_temp_c"] = pd.array(body_temp_values, dtype="Float64")
    table["oxygen_sat_pct"] = pd.array(oxygen_sat_values, dtype="Float64")
    numeric_conversion_counts[table_name] = normal_unit_conversions

print("\nNumeric/unit standardization:")
for table_name, table in triage_columns.items():
    table_flags = [flag for flag in numeric_quality_flags if flag["table"] == table_name]
    invalid_count = sum(flag["flag"] == "invalid_numeric" for flag in table_flags)
    unit_count = sum(flag["flag"] == "unit_inconsistency_corrected" for flag in table_flags)
    print(table_name, "standardized records:", len(cleaned_tables[table_name]),
          "invalid values flagged:", invalid_count, "unit inconsistencies corrected:", unit_count,
          "routine unit conversions:", numeric_conversion_counts[table_name])

print("Total invalid numeric values flagged:",
      sum(flag["flag"] == "invalid_numeric" for flag in numeric_quality_flags))
print("Total unit inconsistencies corrected:",
      sum(flag["flag"] == "unit_inconsistency_corrected" for flag in numeric_quality_flags))
for flag in numeric_quality_flags:
    print(
        flag["table"], "record", flag["record_id"], flag["field"],
        "raw value:", repr(flag["raw_value"]), "-", flag["flag"] + ":",
        flag["details"],
    )


# 6 - Clinical Categories
# ---------------------------------- clinical category mapping rules ------------------------------------
# 1. map source-specific labels to one documented set of canonical values
# 2. unknown or invalid categories are converted to pd.NA
# 3. each unknown or invalid category is preserved as a flag for review
# -------------------------------------------------------------------------------------------------------

category_quality_flags= []

# Admission types
admission_type_mappings = {
    "A_ADMISSIONS": {"column": "AdmissionType",
                     "map": {"ELECTIVE": "ELECTIVE",
                             "URGENT": "URGENT",
                             "EMERGENCY": "EMERGENCY"}},
    "B_episodes": {"column": "episode_type",
                   "map": {"PLANNED": "ELECTIVE",
                           "URGENT": "URGENT",
                           "EMERGENCY": "EMERGENCY"}},
    "C_admission": {"column": "admitType",
                    "map": {"ELE": "ELECTIVE",
                            "URG": "URGENT",
                            "EMG": "EMERGENCY"}},
    "D_encounters": {"column": "encounterType",
                     "map": {"elective": "ELECTIVE",
                             "urgent": "URGENT",
                             "emergency": "EMERGENCY"}},
}

for table_name, config in admission_type_mappings.items():
    table = cleaned_tables[table_name]
    column = config["column"]
    canonical_values = []

    for raw_value in table[column]:
        normalized = str(raw_value).strip().upper()
        canonical = config["map"].get(normalized)

        if pd.isna(raw_value):
            canonical_values.append(pd.NA)
        elif canonical is None:
            canonical_values.append(pd.NA)
            category_quality_flags.append({
                "table": table_name,
                "field": column,
                "raw_value": raw_value,
                "flag": "unknown_admission_type",
            })
        else:
            canonical_values.append(canonical)

    table["admission_type_canonical"] = pd.array(
        canonical_values,
        dtype="string",
    )

#Triage Priorities
triage_priority_mappings = {
    "A_TRIAGE": {
        "column": "TriageLevel",
        "map": {
            "LOW": "LOW",
            "MEDIUM": "MEDIUM",
            "HIGH": "HIGH",
        },
    },
    "B_triage": {
        "column": "triage_category",
        "map": {
            "P1": "HIGH",
            "P2": "MEDIUM",
            "P3": "LOW",
        },
    },
    "C_triage": {
        "column": "triageLevel",
        "map": {
            "1": "HIGH",
            "2": "MEDIUM",
            "3": "LOW",
        },
    },
    "D_triage": {
        "column": "triageColour",
        "map": {
            "red": "HIGH",
            "yellow": "MEDIUM",
            "green": "LOW",
        },
    },
}

for table_name, config in triage_priority_mappings.items():
    table = cleaned_tables[table_name]
    column = config["column"]
    canonical_values = []

    for raw_value in table[column]:
        if pd.isna(raw_value):
            canonical_values.append(pd.NA)
            continue

        normalized = str(raw_value).strip().upper()
        canonical = config["map"].get(normalized)

        if canonical is None:
            canonical_values.append(pd.NA)
            category_quality_flags.append({
                "table": table_name,
                "field": column,
                "raw_value": raw_value,
                "flag": "unknown_triage_priority",
            })
        else:
            canonical_values.append(canonical)

    table["triage_priority_canonical"] = pd.array(
        canonical_values,
        dtype="string",
    )

# Unit types
unit_type_mappings = {
    "A_UNITS": {
        "column": "UnitType",
        "map": {
            "ED": "EMERGENCY",
            "MICU": "MEDICAL_ICU",
            "SICU": "SURGICAL_ICU",
            "ICU": "GENERAL_ICU",
            "CCU": "CORONARY_CARE",
            "MED/SURG": "GENERAL_WARD",
            "STEPDOWN": "STEP_DOWN",
        },
    },
    "B_wards": {
        "column": "ward_category",
        "map": {
            "ED": "EMERGENCY",
            "MICU": "MEDICAL_ICU",
            "SICU": "SURGICAL_ICU",
            "ICU": "GENERAL_ICU",
            "CCU": "CORONARY_CARE",
            "MED/SURG": "GENERAL_WARD",
            "STEPDOWN": "STEP_DOWN",
        },
    },
    "C_ward": {
        "column": "wardCategory",
        "map": {
            "ER": "EMERGENCY",
            "MICU": "MEDICAL_ICU",
            "SICU": "SURGICAL_ICU",
            "ICU": "GENERAL_ICU",
            "CCU": "CORONARY_CARE",
            "GW": "GENERAL_WARD",
            "SDU": "STEP_DOWN",
        },
    },
    "D_units": {
        "column": "unitKind",
        "map": {
            "casualty": "EMERGENCY",
            "micu": "MEDICAL_ICU",
            "sicu": "SURGICAL_ICU",
            "icu": "GENERAL_ICU",
            "ccu": "CORONARY_CARE",
            "general_ward": "GENERAL_WARD",
            "high_care": "STEP_DOWN",
        },
    },
}

for table_name, config in unit_type_mappings.items():
    table = cleaned_tables[table_name]
    column = config["column"]
    canonical_values = []

    for raw_value in table[column]:
        if pd.isna(raw_value):
            canonical_values.append(pd.NA)
            continue

        normalized = str(raw_value).strip().upper()
        canonical = config["map"].get(normalized)

        if canonical is None:
            canonical_values.append(pd.NA)
            category_quality_flags.append({
                "table": table_name,
                "field": column,
                "raw_value": raw_value,
                "flag": "unknown_unit_type",
            })
        else:
            canonical_values.append(canonical)

    table["unit_type_canonical"] = pd.array(
        canonical_values,
        dtype="string",
    )

# Admission/status categories
status_mappings = {
    "AdmissionStatus": {
        "DISCHARGED": "DISCHARGED",
        "TRANSFERRED OUT": "TRANSFERRED",
        "TRANSFERRED": "TRANSFERRED",
        "ADMITTED": "ACTIVE",
        "ACTIVE": "ACTIVE",
    },
    "episode_status": {
        "DISCHARGED": "DISCHARGED",
        "TRANSFERRED OUT": "TRANSFERRED",
        "TRANSFERRED": "TRANSFERRED",
        "ADMITTED": "ACTIVE",
        "ACTIVE": "ACTIVE",
    },
    "encounterStatus": {
        "discharged": "DISCHARGED",
        "transferred": "TRANSFERRED",
        "active": "ACTIVE",
    },
}

for table_name, table in cleaned_tables.items():
    for column in table.columns:
        if column not in status_mappings:
            continue

        canonical_values = []
        mapping = status_mappings[column]

        for raw_value in table[column]:
            if pd.isna(raw_value):
                canonical_values.append(pd.NA)
                continue

            normalized = str(raw_value).strip().upper()
            canonical = mapping.get(normalized)

            if canonical is None:
                canonical_values.append(pd.NA)
                category_quality_flags.append({
                    "table": table_name,
                    "field": column,
                    "raw_value": raw_value,
                    "flag": "unknown_status",
                })
            else:
                canonical_values.append(canonical)

        table[f"{column}_canonical"] = pd.array(
            canonical_values,
            dtype="string",
        )

# Summary output
print("\nClinical category standardization:")
print("Category flags:", len(category_quality_flags))

for flag in category_quality_flags:
    print(
        flag["table"],
        "field:",
        flag["field"],
        "raw value:",
        repr(flag["raw_value"]),
        "-",
        flag["flag"],
    )


# 7 - Missing Parent Records and Inconsistent References
import math
import pandas as pd

# What to do when an OPTIONAL reference points to a parent that doesn't exist:
#   True  -> set the reference to null, keep the row, log it
#   False -> quarantine the row
NULL_DANGLING_OPTIONAL_REFS = True
MAX_PASSES = 20

# Snapshot of raw parents, used to tell whether a parent never existed or was
# removed earlier. Reference checks use the current cleaned tables.
reference_parent_snapshot = {
    name: table.copy(deep=True)
    for name, table in tables.items()
}


def reference_key(value, numeric_id=False):
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    if numeric_id:
        try:
            number = float(text)
        except ValueError:
            return text

        if math.isfinite(number) and number.is_integer():
            return str(int(number))

    return text


def key_set(dataframe, column, numeric_id):
    keys = {
        reference_key(value, numeric_id)
        for value in dataframe[column]
    }
    keys.discard(None)
    return keys


def ref(child, fk, parent, pk, field, numeric=True, required=True):
    return {
        "child": child,
        "fk": fk,
        "parent": parent,
        "pk": pk,
        "field": field,
        "numeric": numeric,
        "required": required,
    }


def staff(child, fk, field, parent, pk, numeric=True):
    # Staff references are optional here; align this with the Phase 1 schema.
    return ref(child, fk, parent, pk, field, numeric, required=False)


reference_rules = [
    # Source A
    ref("A_ADMISSIONS", "PatID", "A_PATIENTS", "PatID", "patient_id"),
    staff("A_ADMISSIONS", "AdmittingMD", "admitting_healthcare_professional",
          "A_STAFF", "StaffID"),
    ref("A_TRIAGE", "AdmitID", "A_ADMISSIONS", "AdmitID", "admission_id"),
    staff("A_TRIAGE", "NurseID", "nurse_id", "A_STAFF", "StaffID"),
    ref("A_CLINICAL_NOTES", "AdmitID", "A_ADMISSIONS", "AdmitID",
        "admission_id"),
    staff("A_CLINICAL_NOTES", "PhysicianId", "physician_id",
          "A_STAFF", "StaffID"),
    ref("A_DIAGNOSES", "AdmitID", "A_ADMISSIONS", "AdmitID",
        "admission_id"),
    ref("A_DIAGNOSES", "PatID", "A_PATIENTS", "PatID", "patient_id"),
    ref("A_DIAGNOSES", "ICD9Code", "A_ICD9_DICT", "ICD9Code",
        "icd9_code", numeric=False),
    staff("A_DIAGNOSES", "DiagnosingPhysicianId",
          "diagnosing_physician_id", "A_STAFF", "StaffID"),
    ref("A_SURGERIES", "AdmitID", "A_ADMISSIONS", "AdmitID",
        "admission_id"),
    staff("A_SURGERIES", "SurgeonId", "surgeon_id", "A_STAFF", "StaffID"),
    ref("A_DISCHARGES", "AdmitID", "A_ADMISSIONS", "AdmitID",
        "admission_id"),
    staff("A_DISCHARGES", "ResponsiblePhysicianId",
          "responsible_physician_id", "A_STAFF", "StaffID"),
    ref("A_DIAG_ORDERS", "AdmitID", "A_ADMISSIONS", "AdmitID",
        "admission_id"),
    ref("A_DIAG_ORDERS", "PatID", "A_PATIENTS", "PatID", "patient_id"),
    staff("A_DIAG_ORDERS", "RequestingPhysicianId",
          "requesting_physician_id", "A_STAFF", "StaffID"),
    ref("A_RAD_EXAMS", "AdmitID", "A_ADMISSIONS", "AdmitID",
        "admission_id"),
    ref("A_RAD_EXAMS", "OrderID", "A_DIAG_ORDERS", "OrderID", "order_id"),
    staff("A_RAD_EXAMS", "ReferringPhysicianId",
          "referring_physician_id", "A_STAFF", "StaffID"),
    staff("A_RAD_EXAMS", "RadTechId", "rad_tech_id", "A_STAFF", "StaffID"),
    ref("A_RAD_REPORTS", "RadExamID", "A_RAD_EXAMS", "RadExamID",
        "rad_exam_id"),
    staff("A_RAD_REPORTS", "RadiologistId", "radiologist_id",
          "A_STAFF", "StaffID"),
    ref("A_LAB_EXAMS", "OrderID", "A_DIAG_ORDERS", "OrderID", "order_id"),
    staff("A_LAB_EXAMS", "PerformedById", "performed_by_id",
          "A_STAFF", "StaffID"),
    ref("A_UNIT_STAYS", "AdmitID", "A_ADMISSIONS", "AdmitID",
        "admission_id"),
    ref("A_UNIT_STAYS", "UnitID", "A_UNITS", "UnitID", "unit_id"),
    staff("A_UNIT_STAYS", "ResponsiblePhysicianId",
          "responsible_physician_id", "A_STAFF", "StaffID"),
    ref("A_ICU_RECORDS", "StayID", "A_UNIT_STAYS", "StayID", "unit_stay_id"),
    ref("A_WARD_RECORDS", "AdmitID", "A_ADMISSIONS", "AdmitID",
        "admission_id"),

    # Source B
    ref("B_episodes", "patient_no", "B_patients", "patient_no", "patient_id"),
    staff("B_episodes", "admitting_clinician",
          "admitting_healthcare_professional", "B_staff", "staff_no"),
    ref("B_triage", "episode_no", "B_episodes", "episode_no", "admission_id"),
    staff("B_triage", "nurse_id", "nurse_id", "B_staff", "staff_no"),
    ref("B_notes", "episode_no", "B_episodes", "episode_no", "admission_id"),
    staff("B_notes", "physician_id", "physician_id", "B_staff", "staff_no"),
    ref("B_diagnoses", "episode_no", "B_episodes", "episode_no",
        "admission_id"),
    ref("B_diagnoses", "patient_no", "B_patients", "patient_no", "patient_id"),
    ref("B_diagnoses", "icd9", "B_icd9_codes", "icd9", "icd9_code",
        numeric=False),
    staff("B_diagnoses", "diagnosing_physician_id",
          "diagnosing_physician_id", "B_staff", "staff_no"),
    ref("B_operations", "episode_no", "B_episodes", "episode_no",
        "admission_id"),
    staff("B_operations", "surgeon_no", "surgeon_id", "B_staff", "staff_no"),
    ref("B_discharges", "episode_no", "B_episodes", "episode_no",
        "admission_id"),
    staff("B_discharges", "responsible_physician_id",
          "responsible_physician_id", "B_staff", "staff_no"),
    ref("B_orders", "episode_no", "B_episodes", "episode_no", "admission_id"),
    ref("B_orders", "patient_no", "B_patients", "patient_no", "patient_id"),
    staff("B_orders", "requesting_physician_id",
          "requesting_physician_id", "B_staff", "staff_no"),
    ref("B_imaging", "episode_no", "B_episodes", "episode_no",
        "admission_id"),
    ref("B_imaging", "order_id", "B_orders", "order_id", "order_id"),
    staff("B_imaging", "referring_physician_id",
          "referring_physician_id", "B_staff", "staff_no"),
    staff("B_imaging", "rad_tech_id", "rad_tech_id", "B_staff", "staff_no"),
    ref("B_imaging_reports", "rad_exam_id", "B_imaging", "exam_id",
        "rad_exam_id"),
    staff("B_imaging_reports", "radiologist_id", "radiologist_id",
          "B_staff", "staff_no"),
    ref("B_investigations", "order_id", "B_orders", "order_id", "order_id"),
    staff("B_investigations", "performed_by_id", "performed_by_id",
          "B_staff", "staff_no"),
    ref("B_ward_stays", "episode_no", "B_episodes", "episode_no",
        "admission_id"),
    ref("B_ward_stays", "ward_no", "B_wards", "ward_no", "unit_id"),
    staff("B_ward_stays", "responsible_physician_id",
          "responsible_physician_id", "B_staff", "staff_no"),
    ref("B_critical_care_obs", "ward_stay_no", "B_ward_stays",
        "ward_stay_no", "unit_stay_id"),
    ref("B_ward_obs", "episode_no", "B_episodes", "episode_no",
        "admission_id"),

    # Source C: explicit foreign-key columns
    ref("C_diagnosis", "pid", "C_patient", "pid", "patient_id"),
    ref("C_diagnosis", "icdCode", "C_icdEntry", "icdCode", "icd9_code",
        numeric=False),
    staff("C_diagnosis", "diagnosingPhysicianId",
          "diagnosing_physician_id", "C_staff", "staffNo"),
    ref("C_order", "pid", "C_patient", "pid", "patient_id"),
    staff("C_order", "requestingPhysicianId",
          "requesting_physician_id", "C_staff", "staffNo"),
    ref("C_imaging", "aid", "C_admission", "aid", "admission_id"),
    staff("C_imaging", "referringPhysicianId",
          "referring_physician_id", "C_staff", "staffNo"),
    staff("C_imaging", "radTechId", "rad_tech_id", "C_staff", "staffNo"),
    staff("C_labExam", "performedById", "performed_by_id",
          "C_staff", "staffNo"),
    ref("C_wardStay", "wardCode", "C_ward", "wardCode", "unit_id",
        numeric=False),

    # Source D
    ref("D_encounters", "patientRef", "D_patients", "patientRef",
        "patient_id", numeric=False),
    staff("D_encounters", "admittingHealthcareProfessional",
          "admitting_healthcare_professional", "D_staff", "staffRef",
          numeric=False),
    ref("D_triage", "encounterId", "D_encounters", "encounterId",
        "admission_id"),
    staff("D_triage", "nurseId", "nurse_id", "D_staff", "staffRef",
          numeric=False),
    ref("D_diagnoses", "patientRef", "D_patients", "patientRef",
        "patient_id", numeric=False),
    ref("D_diagnoses", "encounterId", "D_encounters", "encounterId",
        "admission_id"),
    ref("D_diagnoses", "icd9", "D_icd9Dictionary", "icd9", "icd9_code",
        numeric=False),
    staff("D_diagnoses", "diagnosingPhysicianId",
          "diagnosing_physician_id", "D_staff", "staffRef", numeric=False),
    ref("D_notes", "encounterId", "D_encounters", "encounterId",
        "admission_id"),
    staff("D_notes", "physicianId", "physician_id", "D_staff", "staffRef",
          numeric=False),
    ref("D_procedures", "encounterId", "D_encounters", "encounterId",
        "admission_id"),
    staff("D_procedures", "surgeonId", "surgeon_id", "D_staff", "staffRef",
          numeric=False),
    ref("D_discharge", "encounterId", "D_encounters", "encounterId",
        "admission_id"),
    staff("D_discharge", "responsiblePhysicianId",
          "responsible_physician_id", "D_staff", "staffRef", numeric=False),
    ref("D_orders", "patientRef", "D_patients", "patientRef",
        "patient_id", numeric=False),
    ref("D_orders", "encounterId", "D_encounters", "encounterId",
        "admission_id"),
    staff("D_orders", "requestingPhysicianId",
          "requesting_physician_id", "D_staff", "staffRef", numeric=False),
    ref("D_imaging", "encounterId", "D_encounters", "encounterId",
        "admission_id"),
    ref("D_imaging", "orderId", "D_orders", "orderId", "order_id"),
    staff("D_imaging", "referringPhysicianId",
          "referring_physician_id", "D_staff", "staffRef", numeric=False),
    staff("D_imaging", "radTechId", "rad_tech_id", "D_staff", "staffRef",
          numeric=False),
    ref("D_labResults", "orderId", "D_orders", "orderId", "order_id"),
    staff("D_labResults", "performedById", "performed_by_id",
          "D_staff", "staffRef", numeric=False),
    ref("D_report", "examId", "D_imaging", "examId", "rad_exam_id"),
    staff("D_report", "radiologistId", "radiologist_id",
          "D_staff", "staffRef", numeric=False),
    ref("D_movements", "encounterId", "D_encounters", "encounterId",
        "admission_id"),
    ref("D_movements", "unitCode", "D_units", "unitCode", "unit_id",
        numeric=False),
    staff("D_movements", "responsiblePhysicianId",
          "responsible_physician_id", "D_staff", "staffRef", numeric=False),
    ref("D_criticalCareObservations", "movementId", "D_movements",
        "movementId", "unit_stay_id"),
    ref("D_wardRounds", "encounterId", "D_encounters", "encounterId",
        "admission_id"),
]

# Source C has nested parent links only if the XML loader propagated the IDs
# into child rows. The rules are skipped with a warning if those columns are absent.
pending_reference_rules = [
    ref("C_admission", "pid", "C_patient", "pid", "patient_id"),
    ref("C_triage", "aid", "C_admission", "aid", "admission_id"),
    ref("C_clinicalNote", "aid", "C_admission", "aid", "admission_id"),
    ref("C_diagnosis", "aid", "C_admission", "aid", "admission_id"),
    ref("C_surgery", "aid", "C_admission", "aid", "admission_id"),
    ref("C_discharge", "aid", "C_admission", "aid", "admission_id"),
    ref("C_order", "aid", "C_admission", "aid", "admission_id"),
    ref("C_wardStay", "aid", "C_admission", "aid", "admission_id"),
]

# Compare patient and admission identifiers on rows that contain both.
consistency_rules = [
    ("A_DIAGNOSES", "PatID", "AdmitID",
     "A_ADMISSIONS", "AdmitID", "PatID", True, True),
    ("A_DIAG_ORDERS", "PatID", "AdmitID",
     "A_ADMISSIONS", "AdmitID", "PatID", True, True),
    ("B_diagnoses", "patient_no", "episode_no",
     "B_episodes", "episode_no", "patient_no", True, True),
    ("B_orders", "patient_no", "episode_no",
     "B_episodes", "episode_no", "patient_no", True, True),
    ("D_diagnoses", "patientRef", "encounterId",
     "D_encounters", "encounterId", "patientRef", False, True),
    ("D_orders", "patientRef", "encounterId",
     "D_encounters", "encounterId", "patientRef", False, True),
]

reference_quality_flags = []
_quarantine_parts = {}


def _id_column(table_name):
    return required_attribute_mappings[table_name][0]


def _log(table_name, dataframe, index, field, raw_value,
         parent_table, reason, action):
    id_column = _id_column(table_name)
    record_id = (
        dataframe.at[index, id_column]
        if id_column in dataframe.columns
        else None
    )

    reference_quality_flags.append({
        "table": table_name,
        "row_index": index,
        "record_id": record_id,
        "field": field,
        "raw_value": raw_value,
        "missing_parent_table": parent_table,
        "reason": reason,
        "action": action,
    })


def _quarantine(table_name, mask, reasons, rule_id):
    dataframe = cleaned_tables[table_name]
    quarantined = dataframe[mask].copy()
    quarantined["quarantine_step"] = "7_references"
    quarantined["quarantine_rule"] = rule_id
    quarantined["quarantine_reason"] = reasons[mask]
    _quarantine_parts.setdefault(table_name, []).append(quarantined)
    cleaned_tables[table_name] = dataframe[~mask]


def _check_rule(rule):
    """Check one foreign-key rule and return whether data changed."""
    child_name = rule["child"]
    fk = rule["fk"]
    parent_name = rule["parent"]
    pk = rule["pk"]

    child = cleaned_tables[child_name]
    if child.empty:
        return False

    clean_parent_keys = key_set(
        cleaned_tables[parent_name],
        pk,
        rule["numeric"],
    )
    raw_parent_keys = key_set(
        reference_parent_snapshot[parent_name],
        pk,
        rule["numeric"],
    )

    keys = child[fk].map(
        lambda value: reference_key(value, rule["numeric"])
    )
    is_null = keys.isna()
    dangling = keys.notna() & ~keys.isin(clean_parent_keys)
    parent_removed = dangling & keys.isin(raw_parent_keys)
    parent_never_existed = dangling & ~keys.isin(raw_parent_keys)
    rule_id = f"ref:{child_name}.{fk}->{parent_name}.{pk}"

    reasons = pd.Series("", index=child.index, dtype=object)
    reasons[parent_removed] = (
        f"Parent in {parent_name} was quarantined or removed earlier "
        f"({rule['field']})"
    )
    reasons[parent_never_existed] = (
        f"Referenced parent does not exist in {parent_name} "
        f"({rule['field']})"
    )

    if rule["required"]:
        reasons[is_null] = (
            f"Required parent reference is missing ({rule['field']})"
        )
        bad = is_null | dangling
        if not bad.any():
            return False

        for index in child.index[bad]:
            _log(
                child_name, child, index, rule["field"],
                child.at[index, fk], parent_name, reasons[index],
                "quarantined",
            )

        _quarantine(child_name, bad, reasons, rule_id)
        return True

    # Null optional references are allowed. Dangling values are logged and
    # nulled, unless configuration requests quarantine instead.
    if not dangling.any():
        return False

    if NULL_DANGLING_OPTIONAL_REFS:
        for index in child.index[dangling]:
            _log(
                child_name, child, index, rule["field"],
                child.at[index, fk], parent_name, reasons[index],
                "set_to_null",
            )

        cleaned_tables[child_name][fk] = (
            child[fk].astype(object).where(~dangling, None)
        )
    else:
        for index in child.index[dangling]:
            _log(
                child_name, child, index, rule["field"],
                child.at[index, fk], parent_name, reasons[index],
                "quarantined",
            )

        _quarantine(child_name, dangling, reasons, rule_id)

    return True


def _check_consistency(rule):
    """Check that the row's patient matches the referenced admission."""
    (
        child_name, patient_column, admission_column,
        admission_table, admission_id_column, admission_patient_column,
        numeric_patient_id, numeric_admission_id,
    ) = rule

    child = cleaned_tables[child_name]
    if child.empty:
        return False

    admissions = cleaned_tables[admission_table]

    # Skip ambiguous admissions that map to more than one patient.
    admission_patients = {}
    for admission_id, patient_id in zip(
        admissions[admission_id_column],
        admissions[admission_patient_column],
    ):
        normalized_admission = reference_key(
            admission_id,
            numeric_admission_id,
        )
        normalized_patient = reference_key(
            patient_id,
            numeric_patient_id,
        )

        if normalized_admission is not None and normalized_patient is not None:
            admission_patients.setdefault(normalized_admission, set()).add(
                normalized_patient
            )

    admission_patients = {
        admission_id: next(iter(patient_ids))
        for admission_id, patient_ids in admission_patients.items()
        if len(patient_ids) == 1
    }

    patients = child[patient_column].map(
        lambda value: reference_key(value, numeric_patient_id)
    )
    admission_ids = child[admission_column].map(
        lambda value: reference_key(value, numeric_admission_id)
    )
    expected_patients = admission_ids.map(admission_patients)

    mismatched = (
        patients.notna()
        & expected_patients.notna()
        & (patients != expected_patients)
    )
    if not mismatched.any():
        return False

    reasons = pd.Series(
        "Patient and admission references belong to different patients",
        index=child.index,
        dtype=object,
    )

    for index in child.index[mismatched]:
        _log(
            child_name,
            child,
            index,
            "patient_id",
            child.at[index, patient_column],
            admission_table,
            reasons[index],
            "quarantined",
        )

    _quarantine(
        child_name,
        mismatched,
        reasons,
        f"consistency:{child_name}.{patient_column}/{admission_column}",
    )
    return True


def enforce_references():
    """Run reference checks until no more rows are changed."""
    for table_name, dataframe in cleaned_tables.items():
        assert dataframe.index.is_unique, (
            f"{table_name}: index must be unique before Step 7"
        )

    active_rules = list(reference_rules)
    for rule in pending_reference_rules:
        if (
            rule["child"] in cleaned_tables
            and rule["parent"] in tables
            and rule["fk"] in cleaned_tables[rule["child"]].columns
            and rule["pk"] in tables[rule["parent"]].columns
        ):
            active_rules.append(rule)
        else:
            print(
                "WARNING: skipped nested rule "
                f"{rule['child']}.{rule['fk']} -> "
                f"{rule['parent']}.{rule['pk']} "
                "(column not available)"
            )

    # Fail clearly for typos in the main rules.
    for rule in active_rules:
        for table_name in (rule["child"], rule["parent"]):
            if table_name not in tables:
                raise KeyError(
                    f"Unknown table in reference rule: {table_name}"
                )

        if rule["fk"] not in cleaned_tables[rule["child"]].columns:
            raise KeyError(
                f"Missing column {rule['child']}.{rule['fk']}"
            )
        if rule["pk"] not in tables[rule["parent"]].columns:
            raise KeyError(
                f"Missing column {rule['parent']}.{rule['pk']}"
            )

    for pass_number in range(1, MAX_PASSES + 1):
        changed = False

        for rule in active_rules:
            changed |= _check_rule(rule)

        for rule in consistency_rules:
            changed |= _check_consistency(rule)

        print(
            f"Step 7 pass {pass_number}: "
            f"{'changes made' if changed else 'stable'}"
        )

        if not changed:
            break
    else:
        raise RuntimeError(
            "Step 7 did not converge; check for circular rules"
        )


enforce_references()

reference_quarantine_tables = {
    table_name: pd.concat(parts)
    for table_name, parts in _quarantine_parts.items()
}
reference_flags_df = pd.DataFrame(reference_quality_flags)

print("\nMissing-parent and inconsistent-reference summary:")
print("Violations logged:", len(reference_flags_df))
print(
    "Rows quarantined:",
    sum(
        len(dataframe)
        for dataframe in reference_quarantine_tables.values()
    ),
)

if not reference_flags_df.empty:
    print(
        reference_flags_df.groupby(["table", "field", "action"])
        .size()
        .rename("count")
        .reset_index()
        .to_string(index=False)
    )

# 8 - Chronology
# ---------------------------------- chronology validation rules ----------------------------------------
# 1. check admission, discharge, unit-stay, examination, procedure, and report timestamps using cleaned datetime values
# 2. quarantine admissions where the discharge time is before the admission time
# 3. quarantine unit stays where the exit time is before the entry time or outside the admission period
# 4. quarantine examinations, procedures, diagnoses, and notes that fall outside the admission period
# 5. quarantine examinations performed before their order, and reports written before their examination
# 6. quarantine patients with a date of death before an admission, or a date of birth after the first admission
# 7. a missing discharge or exit time is valid for an open stay and is not a chronology violation
# 8. skip any check where a required timestamp is missing or null; those cases are handled by earlier steps
# 9. no swapping or correction of timestamps; unresolved rows go to quarantine with a rule ID and a reason
# 10. rerun the Step 7 reference checks afterward so children of quarantined admissions are also quarantined
# -------------------------------------------------------------------------------------------------------
chronology_quality_flags = []
chronology_invalid_rows = {}


def chronology_timestamp(value):
    if pd.isna(value):
        return None
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)
    return timestamp


def chronology_reference_key(value):
    return reference_key(value, numeric_id=isinstance(value, numbers.Number))


def add_chronology_flag(table_name, row_index, field, raw_value, reason):
    id_column = required_attribute_mappings[table_name][0]
    record = cleaned_tables[table_name].loc[row_index]
    chronology_quality_flags.append({
        "table": table_name,
        "row_index": row_index,
        "record_id": record[id_column] if id_column in record.index else None,
        "field": field,
        "raw_value": raw_value,
        "reason": reason,
    })
    chronology_invalid_rows.setdefault(table_name, set()).add(row_index)


def check_timestamp_pair(table_name, earlier_column, later_column,
                         reason, violated_when):
    table = cleaned_tables[table_name]
    if earlier_column not in table.columns or later_column not in table.columns:
        return

    for row_index, row in table.iterrows():
        earlier = chronology_timestamp(row[earlier_column])
        later = chronology_timestamp(row[later_column])
        if earlier is None or later is None:
            continue

        invalid = (
            earlier > later
            if violated_when == "earlier_after_later"
            else earlier < later
        )
        if invalid:
            add_chronology_flag(
                table_name,
                row_index,
                later_column,
                row[later_column],
                reason,
            )


def check_event_against_parent(child_name, child_time_column, child_fk,
                               parent_name, parent_pk, parent_time_column,
                               violation, reason):
    child = cleaned_tables[child_name]
    parent = cleaned_tables[parent_name]
    if child.empty or parent.empty:
        return

    if child_fk not in child.columns or parent_pk not in parent.columns:
        return
    if child_time_column not in child.columns:
        return
    if parent_time_column not in parent.columns:
        return

    parent_times = {}
    for _, parent_row in parent.iterrows():
        key = chronology_reference_key(parent_row[parent_pk])
        timestamp = chronology_timestamp(parent_row[parent_time_column])
        if key is not None and timestamp is not None:
            parent_times.setdefault(key, set()).add(timestamp)

    # Do not guess if the parent identifier is duplicated with conflicting times.
    parent_times = {
        key: next(iter(values))
        for key, values in parent_times.items()
        if len(values) == 1
    }

    for row_index, row in child.iterrows():
        key = chronology_reference_key(row[child_fk])
        event_time = chronology_timestamp(row[child_time_column])
        parent_time = parent_times.get(key)
        if key is None or event_time is None or parent_time is None:
            continue

        invalid = (
            event_time < parent_time
            if violation == "before"
            else event_time > parent_time
        )
        if invalid:
            add_chronology_flag(
                child_name,
                row_index,
                child_time_column,
                row[child_time_column],
                reason,
            )


# Admission discharge must not precede admission.
for table_name, admit_column, discharge_column in [
    ("A_ADMISSIONS", "AdmitDT", "DischDT"),
    ("B_episodes", "episode_start", "episode_end"),
    ("C_admission", "admitTime", "dischargeTime"),
    ("D_encounters", "admittedAt", "dischargedAt"),
]:
    check_timestamp_pair(
        table_name,
        admit_column,
        discharge_column,
        "Discharge precedes admission",
        "earlier_after_later",
    )

# Unit exit must not precede unit entry.
for table_name, entry_column, exit_column in [
    ("A_UNIT_STAYS", "InDT", "OutDT"),
    ("B_ward_stays", "ward_in", "ward_out"),
    ("C_wardStay", "inTime", "outTime"),
    ("D_movements", "inAt", "outAt"),
]:
    check_timestamp_pair(
        table_name,
        entry_column,
        exit_column,
        "Unit exit precedes unit entry",
        "earlier_after_later",
    )

# Related-event chronology rules:
# child event must be at/after the parent event ("before"),
# or at/before it ("after").
related_time_rules = [
    # Diagnosis must not precede its admission.
    ("A_DIAGNOSES", "DiagnosisDatetime", "AdmitID",
     "A_ADMISSIONS", "AdmitID", "AdmitDT", "before",
     "Diagnosis precedes admission"),
    ("B_diagnoses", "diagnosis_datetime", "episode_no",
     "B_episodes", "episode_no", "episode_start", "before",
     "Diagnosis precedes admission"),
    ("C_diagnosis", "diagnosisDatetime", "aid",
     "C_admission", "aid", "admitTime", "before",
     "Diagnosis precedes admission"),
    ("D_diagnoses", "diagnosisDatetime", "encounterId",
     "D_encounters", "encounterId", "admittedAt", "before",
     "Diagnosis precedes admission"),

    # Procedures must not occur after discharge.
    ("A_SURGERIES", "ProcedureDatetime", "AdmitID",
     "A_ADMISSIONS", "AdmitID", "DischDT", "after",
     "Procedure occurs after discharge"),
    ("B_operations", "operation_datetime", "episode_no",
     "B_episodes", "episode_no", "episode_end", "after",
     "Procedure occurs after discharge"),
    ("C_surgery", "procedureDatetime", "aid",
     "C_admission", "aid", "dischargeTime", "after",
     "Procedure occurs after discharge"),
    ("D_procedures", "procedureDatetime", "encounterId",
     "D_encounters", "encounterId", "dischargedAt", "after",
     "Procedure occurs after discharge"),

    # Diagnostic examinations must not occur before their orders.
    ("A_LAB_EXAMS", "ExamDatetime", "OrderID",
     "A_DIAG_ORDERS", "OrderID", "RequestDatetime", "before",
     "Examination occurs before it was ordered"),
    ("B_investigations", "exam_datetime", "order_id",
     "B_orders", "order_id", "request_datetime", "before",
     "Examination occurs before it was ordered"),
    ("C_labExam", "examDatetime", "orderId",
     "C_order", "orderId", "requestDatetime", "before",
     "Examination occurs before it was ordered"),
    ("D_labResults", "examDatetime", "orderId",
     "D_orders", "orderId", "requestDatetime", "before",
     "Examination occurs before it was ordered"),

    # Radiology examinations must not occur before their orders.
    ("A_RAD_EXAMS", "ExamDatetime", "OrderID",
     "A_DIAG_ORDERS", "OrderID", "RequestDatetime", "before",
     "Examination occurs before it was ordered"),
    ("B_imaging", "exam_datetime", "order_id",
     "B_orders", "order_id", "request_datetime", "before",
     "Examination occurs before it was ordered"),
    ("C_imaging", "examDatetime", "orderId",
     "C_order", "orderId", "requestDatetime", "before",
     "Examination occurs before it was ordered"),
    ("D_imaging", "examDatetime", "orderId",
     "D_orders", "orderId", "requestDatetime", "before",
     "Examination occurs before it was ordered"),

    # Reports must not precede the examination they describe.
    ("A_RAD_REPORTS", "ReportDatetime", "RadExamID",
     "A_RAD_EXAMS", "RadExamID", "ExamDatetime", "before",
     "Report precedes examination"),
    ("B_imaging_reports", "report_datetime", "rad_exam_id",
     "B_imaging", "exam_id", "exam_datetime", "before",
     "Report precedes examination"),
    ("C_report", "reportDatetime", "examId",
     "C_imaging", "examId", "examDatetime", "before",
     "Report precedes examination"),
    ("D_report", "reportDatetime", "examId",
     "D_imaging", "examId", "examDatetime", "before",
     "Report precedes examination"),
]

for rule in related_time_rules:
    check_event_against_parent(*rule)

# Patient birth/death dates must be compatible with their first admission.
patient_admission_rules = [
    ("A_PATIENTS", "PatID", "DOB", "DeathDT",
     "A_ADMISSIONS", "PatID", "AdmitDT"),
    ("B_patients", "patient_no", "birth_date", "date_of_death",
     "B_episodes", "patient_no", "episode_start"),
    ("C_patient", "pid", "birthDate", "deathTime",
     "C_admission", "pid", "admitTime"),
    ("D_patients", "patientRef", "dob", "deceasedAt",
     "D_encounters", "patientRef", "admittedAt"),
]

for (patient_table, patient_id_column, birth_column, death_column,
     admission_table, admission_patient_column, admission_time_column) in patient_admission_rules:
    patients = cleaned_tables[patient_table]
    admissions = cleaned_tables[admission_table]

    first_admission = {}
    for _, admission in admissions.iterrows():
        patient_id = chronology_reference_key(
            admission[admission_patient_column]
        )
        admitted_at = chronology_timestamp(admission[admission_time_column])
        if patient_id is not None and admitted_at is not None:
            if patient_id not in first_admission or admitted_at < first_admission[patient_id]:
                first_admission[patient_id] = admitted_at

    for row_index, patient in patients.iterrows():
        patient_id = chronology_reference_key(patient[patient_id_column])
        first_admitted_at = first_admission.get(patient_id)
        if first_admitted_at is None:
            continue

        birth = chronology_timestamp(patient[birth_column])
        if birth is not None and birth > first_admitted_at:
            add_chronology_flag(
                patient_table,
                row_index,
                birth_column,
                patient[birth_column],
                "Date of birth is after the patient's first admission",
            )

        death = chronology_timestamp(patient[death_column])
        if death is not None and death < first_admitted_at:
            add_chronology_flag(
                patient_table,
                row_index,
                death_column,
                patient[death_column],
                "Date of death is before the patient's first admission",
            )

# Quarantine each chronology-invalid row once after all rules have run.
chronology_quarantine_tables = {}
for table_name, row_indexes in chronology_invalid_rows.items():
    rows = cleaned_tables[table_name].loc[sorted(row_indexes)].copy()
    reason_by_index = {}
    for row_index in row_indexes:
        reason_by_index[row_index] = "; ".join(
            flag["reason"]
            for flag in chronology_quality_flags
            if flag["table"] == table_name and flag["row_index"] == row_index
        )
    rows["quarantine_step"] = "8_chronology"
    rows["quarantine_reason"] = [
        reason_by_index[row_index] for row_index in rows.index
    ]
    chronology_quarantine_tables[table_name] = rows
    cleaned_tables[table_name] = cleaned_tables[table_name].drop(
        index=list(row_indexes)
    )

chronology_flags_df = pd.DataFrame(chronology_quality_flags)
print("\nChronology validation summary:")
print("Chronology violations:", len(chronology_flags_df))
print(
    "Rows quarantined:",
    sum(len(rows) for rows in chronology_quarantine_tables.values()),
)
if not chronology_flags_df.empty:
    print(
        chronology_flags_df.groupby(["table", "field"])
        .size()
        .rename("count")
        .reset_index()
        .to_string(index=False)
    )

# -------------------------------- representative before/after examples --------------------------------
print("\nRepresentative before/after cleaning examples:")

# 1. missing-value normalization example
missing_example_found = False
for table_name, original_table in tables.items():
    if table_name not in cleaned_tables:
        continue
    cleaned_table = cleaned_tables[table_name]
    source = table_name[0]
    common_indexes = original_table.index.intersection(cleaned_table.index)
    for column in original_table.columns:
        if column not in cleaned_table.columns:
            continue
        for row_index in common_indexes:
            original_value = original_table.at[row_index, column]
            cleaned_value = cleaned_table.at[row_index, column]
            if original_value in missing_value_markers[source] and pd.isna(cleaned_value):
                print("\nMissing-value normalization:")
                print("Table:", table_name)
                print("Column:", column)
                print("Before:", repr(original_value))
                print("After:", cleaned_value)
                missing_example_found = True
                break
        if missing_example_found:
            break
    if missing_example_found:
        break


# 2. text-standardization example
text_example_found = False
text_columns = capitalization_columns + categorical_columns
for table_name, original_table in tables.items():
    if table_name not in cleaned_tables:
        continue
    cleaned_table = cleaned_tables[table_name]
    common_indexes = original_table.index.intersection(cleaned_table.index)
    for column in text_columns:
        if column not in original_table.columns or column not in cleaned_table.columns:
            continue
        for row_index in common_indexes:
            original_value = original_table.at[row_index, column]
            cleaned_value = cleaned_table.at[row_index, column]
            if (not pd.isna(original_value) and not pd.isna(cleaned_value) and str(original_value) != str(cleaned_value)):
                print("\nText standardization:")
                print("Table:", table_name)
                print("Column:", column)
                print("Before:", original_value)
                print("After:", cleaned_value)
                text_example_found = True
                break
        if text_example_found:
            break
    if text_example_found:
        break


# 3. date/time standardization example
date_example_found = False
for table_name, columns in date_time_columns.items():
    original_table = tables[table_name]
    cleaned_table = cleaned_tables[table_name]
    common_indexes = original_table.index.intersection(cleaned_table.index)
    for column in columns:
        for row_index in common_indexes:
            original_value = original_table.at[row_index, column]
            cleaned_value = cleaned_table.at[row_index, column]
            if (not pd.isna(original_value)and not pd.isna(cleaned_value)and str(original_value) != str(cleaned_value)):
                print("\nDate/time standardization:")
                print("Table:", table_name)
                print("Column:", column)
                print("Before:", original_value)
                print("After:", cleaned_value)
                date_example_found = True
                break
        if date_example_found:
            break
    if date_example_found:
        break