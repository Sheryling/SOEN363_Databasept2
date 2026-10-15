-- SQLite 3.51
PRAGMA foreign_keys = ON;
 
-- tables 
CREATE TABLE Patient(
    patient_id INTEGER PRIMARY KEY,
    health_insurance_num VARCHAR(20) NOT NULL UNIQUE,
    full_name VARCHAR(50) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(20),
    address VARCHAR(50),
    phone_number VARCHAR(20),
    emergency_contact_name VARCHAR(50),
    emergency_contact_number VARCHAR(20),
    life_status VARCHAR(10) NOT NULL,
    date_of_death DATETIME
);
 
CREATE TABLE Healthcare_Professional(
    staff_id INTEGER PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    staff_type VARCHAR(30) NOT NULL,
    specialty VARCHAR(50)
);
 
CREATE TABLE Unit(
    unit_id INTEGER PRIMARY KEY,
    unit_name VARCHAR(50) NOT NULL,
    unit_type VARCHAR(20) NOT NULL
);
 
CREATE TABLE ICD9_Code(
    icd9_code VARCHAR(10) PRIMARY KEY,
    official_title VARCHAR(200) NOT NULL,
    description VARCHAR(200) NOT NULL,
    disease_category VARCHAR(200) NOT NULL
);

CREATE TABLE Admission(
    admission_id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES Patient(patient_id),
    admitting_healthcare_professional INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    admission_datetime DATETIME NOT NULL,
    admission_type VARCHAR(20) NOT NULL,
    admission_source VARCHAR(50) NOT NULL,
    reason VARCHAR(50) NOT NULL,
    insurance_info VARCHAR(50),
    condition_on_arrival VARCHAR(50) NOT NULL,
    discharge_datetime DATETIME,
    admission_status VARCHAR(50) NOT NULL
);
 
CREATE TABLE TriageAssessment(
    triage_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    nurse_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    triage_datetime DATETIME NOT NULL,
    blood_pressure VARCHAR(10) NOT NULL,
    heart_rate INTEGER NOT NULL,
    pain_level INTEGER NOT NULL,
    symptoms VARCHAR(200) NOT NULL,
    allergies VARCHAR(200) NOT NULL,
    current_medication VARCHAR(200) NOT NULL,
    priority_level VARCHAR(20) NOT NULL,
    body_temp DECIMAL(3,1) NOT NULL,
    oxygen_sat INTEGER NOT NULL
);

CREATE TABLE ClinicalNote(
    note_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    physician_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    note_type VARCHAR(100) NOT NULL,
    note_datetime DATETIME NOT NULL,
    symptoms VARCHAR(200),
    physical_exam VARCHAR(200),
    initial_findings VARCHAR(200),
    suspected_condition VARCHAR(200) NOT NULL,
    planned_examinations VARCHAR(200),
    initial_treatment VARCHAR(200),
    note_text VARCHAR(200)
);
 
CREATE TABLE Diagnosis(
    diagnosis_id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES Patient(patient_id),
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    icd9_code VARCHAR(20) NOT NULL REFERENCES ICD9_Code(icd9_code),
    diagnosis_datetime DATETIME NOT NULL,
    diagnosis_type VARCHAR(50) NOT NULL,
    diagnosing_physician_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id)
);
 
CREATE TABLE SurgicalProcedure(
    procedure_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    surgeon_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    procedure_type VARCHAR(100) NOT NULL,
    procedure_datetime DATETIME NOT NULL,
    outcome VARCHAR(200)
);
 
CREATE TABLE DischargeRecord(
    discharge_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL UNIQUE REFERENCES Admission(admission_id),
    discharge_destination VARCHAR(50),
    condition_at_discharge VARCHAR(50) NOT NULL,
    prescribed_medications VARCHAR(200),
    follow_up_instructions VARCHAR(200),
    follow_up_appointments VARCHAR(200),
    responsible_physician_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id)
);

CREATE TABLE DiagnosticOrder(
    order_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    patient_id INTEGER NOT NULL REFERENCES Patient(patient_id),
    requesting_physician_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    requested_exam VARCHAR(50) NOT NULL,
    request_datetime DATETIME NOT NULL,
    clinical_reason VARCHAR(200),
    priority VARCHAR(10),
    order_status VARCHAR(20) NOT NULL
);
 
CREATE TABLE RadiologyExamination(
    exam_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    exam_type VARCHAR(30) NOT NULL,
    order_id INTEGER NOT NULL REFERENCES DiagnosticOrder(order_id),
    exam_datetime DATETIME NOT NULL,
    body_area VARCHAR(50) NOT NULL,
    referring_physician_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    rad_tech_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    exam_status VARCHAR(20) NOT NULL,
    image_link VARCHAR(255)
);
 
CREATE TABLE RadiologyReport(
    report_id INTEGER PRIMARY KEY,
    rad_exam_id INTEGER NOT NULL UNIQUE REFERENCES RadiologyExamination(exam_id),
    radiologist_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    report_datetime DATETIME NOT NULL,
    findings VARCHAR(200),
    interpretation VARCHAR(200),
    conclusion VARCHAR(200)
);
 
CREATE TABLE DiagnosticExamination(
    diag_exam_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES DiagnosticOrder(order_id),
    exam_type VARCHAR(50) NOT NULL,
    exam_datetime DATETIME NOT NULL,
    performed_by_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    result TEXT,
    exam_status VARCHAR(20) NOT NULL
);
 
CREATE TABLE UnitStay(
    unit_stay_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    unit_id INTEGER NOT NULL REFERENCES Unit(unit_id),
    ward_room VARCHAR(10) NOT NULL,
    bed_number VARCHAR(10),
    entry_datetime DATETIME NOT NULL,
    exit_datetime DATETIME,
    responsible_physician_id INTEGER NOT NULL REFERENCES Healthcare_Professional(staff_id),
    transfer_reason VARCHAR(200) NOT NULL
);
 
CREATE TABLE CriticalCareRecord(
    record_id INTEGER PRIMARY KEY,
    unit_stay_id INTEGER NOT NULL REFERENCES UnitStay(unit_stay_id),
    record_datetime DATETIME NOT NULL,
    vital_signs TEXT,
    medications TEXT,
    observations TEXT,
    response_to_treatment TEXT,
    physician_progress_notes TEXT,
    additional_diagnostic_exams TEXT,
    transferred VARCHAR(10)
);
 
CREATE TABLE GeneralWardRecord(
    ward_record_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    record_datetime DATETIME NOT NULL,
    follow_up_examinations TEXT,
    medications_treatments TEXT,
    progress_notes TEXT,
    additional_tests TEXT,
    recovery_eval TEXT
);


