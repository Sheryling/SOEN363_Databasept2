PRAGMA foreign_keys = ON;

CREATE TABLE Source_System(
    source_code CHAR(1) PRIMARY KEY,
    continent VARCHAR(30) NOT NULL
);

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
    date_of_death DATETIME,
    CHECK (gender IS NULL OR gender IN ('Female', 'Male', 'Other')),
    CHECK (life_status IN ('Alive', 'Deceased')),
    CHECK (date_of_death IS NULL OR life_status = 'Deceased'),
    CHECK (date_of_death IS NULL OR date_of_death >= date_of_birth)
);

CREATE TABLE Healthcare_Professional(
    staff_id INTEGER PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    staff_type VARCHAR(30) NOT NULL,
    specialty VARCHAR(50),
    CHECK (staff_type IN ('Physician', 'Nurse', 'Surgeon', 'Radiologist',
                          'Radiology Technician', 'Lab Technician'))
);

CREATE TABLE Unit(
    unit_id INTEGER PRIMARY KEY,
    unit_name VARCHAR(50) NOT NULL,
    unit_type VARCHAR(20) NOT NULL,
    CHECK (unit_type IN ('Emergency', 'General Ward', 'ICU', 'MICU', 'SICU', 'CCU', 'Step-Down'))
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
    admitting_healthcare_professional INTEGER REFERENCES Healthcare_Professional(staff_id),
    admission_datetime DATETIME NOT NULL,
    admission_type VARCHAR(20) NOT NULL,
    admission_source VARCHAR(50) NOT NULL,
    reason VARCHAR(50) NOT NULL,
    insurance_info VARCHAR(50),
    condition_on_arrival VARCHAR(50) NOT NULL,
    discharge_datetime DATETIME,
    admission_status VARCHAR(50) NOT NULL,
    UNIQUE (admission_id, patient_id),
    CHECK (admission_type IN ('Emergency', 'Urgent', 'Elective')),
    CHECK (admission_source IN ('Emergency Department', 'Clinic', 'Physician Referral',
                                'Transfer from Another Hospital')),
    CHECK (admission_status IN ('Admitted', 'Discharged', 'Transferred', 'Deceased')),
    CHECK (discharge_datetime IS NULL OR discharge_datetime > admission_datetime)
);

CREATE TABLE TriageAssessment(
    triage_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    nurse_id INTEGER REFERENCES Healthcare_Professional(staff_id),
    triage_datetime DATETIME NOT NULL,
    blood_pressure VARCHAR(10) NOT NULL,
    heart_rate INTEGER NOT NULL,
    pain_level INTEGER NOT NULL,
    symptoms VARCHAR(200) NOT NULL,
    allergies VARCHAR(200) NOT NULL,
    current_medication VARCHAR(200) NOT NULL,
    priority_level VARCHAR(20) NOT NULL,
    body_temp DECIMAL(3,1) NOT NULL,
    oxygen_sat INTEGER NOT NULL,
    CHECK (priority_level IN ('High', 'Medium', 'Low')),
    CHECK (heart_rate BETWEEN 1 AND 300),
    CHECK (pain_level BETWEEN 0 AND 10),
    CHECK (body_temp BETWEEN 25 AND 45),
    CHECK (oxygen_sat > 0 AND oxygen_sat <= 100)
);

CREATE TABLE ClinicalNote(
    note_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    physician_id INTEGER REFERENCES Healthcare_Professional(staff_id),
    note_type VARCHAR(100) NOT NULL,
    note_datetime DATETIME NOT NULL,
    symptoms VARCHAR(200),
    physical_exam VARCHAR(200),
    initial_findings VARCHAR(200),
    suspected_condition VARCHAR(200) NOT NULL,
    planned_examinations VARCHAR(200),
    initial_treatment VARCHAR(200),
    note_text VARCHAR(200),
    CHECK (note_type IN ('Admission Note', 'Progress Note', 'Consultation Note', 'Discharge Summary'))
);

CREATE TABLE Diagnosis(
    diagnosis_id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES Patient(patient_id),
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    icd9_code VARCHAR(20) NOT NULL REFERENCES ICD9_Code(icd9_code),
    diagnosis_datetime DATETIME NOT NULL,
    diagnosis_type VARCHAR(50) NOT NULL,
    diagnosing_physician_id INTEGER REFERENCES Healthcare_Professional(staff_id),
    FOREIGN KEY (admission_id, patient_id) REFERENCES Admission(admission_id, patient_id),
    CHECK (diagnosis_type IN ('Primary', 'Secondary'))
);

CREATE TABLE SurgicalProcedure(
    procedure_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    surgeon_id INTEGER REFERENCES Healthcare_Professional(staff_id),
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
    responsible_physician_id INTEGER REFERENCES Healthcare_Professional(staff_id),
    CHECK (condition_at_discharge IN ('Improved', 'Stable', 'Unchanged', 'Deceased'))
);

CREATE TABLE DiagnosticOrder(
    order_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    patient_id INTEGER NOT NULL REFERENCES Patient(patient_id),
    requesting_physician_id INTEGER REFERENCES Healthcare_Professional(staff_id),
    requested_exam VARCHAR(50) NOT NULL,
    request_datetime DATETIME NOT NULL,
    clinical_reason VARCHAR(200),
    priority VARCHAR(10),
    order_status VARCHAR(20) NOT NULL,
    FOREIGN KEY (admission_id, patient_id) REFERENCES Admission(admission_id, patient_id),
    CHECK (priority IS NULL OR priority IN ('Routine', 'Urgent', 'STAT')),
    CHECK (order_status IN ('Pending', 'Completed', 'Cancelled'))
);

CREATE TABLE RadiologyExamination(
    exam_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    exam_type VARCHAR(30) NOT NULL,
    order_id INTEGER NOT NULL REFERENCES DiagnosticOrder(order_id),
    exam_datetime DATETIME NOT NULL,
    body_area VARCHAR(50) NOT NULL,
    referring_physician_id INTEGER REFERENCES Healthcare_Professional(staff_id),
    rad_tech_id INTEGER REFERENCES Healthcare_Professional(staff_id),
    exam_status VARCHAR(20) NOT NULL,
    image_link VARCHAR(255),
    CHECK (exam_status IN ('Pending', 'Completed', 'Cancelled'))
);

CREATE TABLE RadiologyReport(
    report_id INTEGER PRIMARY KEY,
    rad_exam_id INTEGER NOT NULL UNIQUE REFERENCES RadiologyExamination(exam_id),
    radiologist_id INTEGER REFERENCES Healthcare_Professional(staff_id),
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
    performed_by_id INTEGER REFERENCES Healthcare_Professional(staff_id),
    result TEXT,
    exam_status VARCHAR(20) NOT NULL,
    CHECK (exam_status IN ('Pending', 'Completed', 'Cancelled'))
);

CREATE TABLE UnitStay(
    unit_stay_id INTEGER PRIMARY KEY,
    admission_id INTEGER NOT NULL REFERENCES Admission(admission_id),
    unit_id INTEGER NOT NULL REFERENCES Unit(unit_id),
    ward_room VARCHAR(10) NOT NULL,
    bed_number VARCHAR(10),
    entry_datetime DATETIME NOT NULL,
    exit_datetime DATETIME,
    responsible_physician_id INTEGER REFERENCES Healthcare_Professional(staff_id),
    transfer_reason VARCHAR(200) NOT NULL,
    CHECK (exit_datetime IS NULL OR exit_datetime > entry_datetime)
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
    transferred VARCHAR(10),
    CHECK (transferred IS NULL OR transferred IN ('Yes', 'No'))
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

CREATE TABLE Source_ID_Mapping(
    mapping_id INTEGER PRIMARY KEY,
    entity_name VARCHAR(50) NOT NULL,
    source_code CHAR(1) NOT NULL REFERENCES Source_System(source_code),
    original_source_id VARCHAR(50) NOT NULL,
    global_id VARCHAR(50) NOT NULL,
    UNIQUE(entity_name, source_code, original_source_id)
);

CREATE TABLE Uncertain_Patient_Match(
    match_id INTEGER PRIMARY KEY,
    patient_id_1 INTEGER NOT NULL REFERENCES Patient(patient_id),
    patient_id_2 INTEGER NOT NULL REFERENCES Patient(patient_id),
    reason VARCHAR(255) NOT NULL,
    CHECK (patient_id_1 <> patient_id_2)
);
