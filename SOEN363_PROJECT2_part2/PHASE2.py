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

for tag in tags_C:
    key = "C_" + tag
    df = pd.read_xml("source_C_asia/sakura_bay_export.xml", xpath=".//" + tag, parser="etree")

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
    "D_patients": ["dob"],
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