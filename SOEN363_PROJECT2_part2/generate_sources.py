#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SOEN 363 Project Phase 2 -- synthetic hospital source generator.

ALL DATA PRODUCED BY THIS SCRIPT IS ENTIRELY FICTIONAL. It was created
exclusively for educational and learning purposes and does not describe real
patients or contain any real personal information. Names are random
combinations of common first and last names; phone numbers, addresses,
insurance numbers and hospitals are invented.

Generated with Claude (Anthropic), as permitted by Section 2 of the Phase 2
handout (generative AI may be used only to create the synthetic source data).

Run:   python3 generate_sources.py
Output: synthetic_sources/  (deterministic -- fixed random seed)

Sources
  A  North America  TXT  (pipe-delimited, one file per entity)
  B  Europe         CSV  (semicolon-delimited, one file per entity)
  C  Asia           XML  (one nested file)
  D  Africa         JSON (one nested file)
"""
import copy
import csv
import json
import os
import random
import shutil
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

SEED = 3632026
OUT = "synthetic_sources"
AS_OF = datetime(2026, 10, 31, 23, 0)   # "export time" of every source


def H(x):
    return timedelta(hours=x)


def DY(x):
    return timedelta(days=x)


# ---------------------------------------------------------------------------
# Schema bookkeeping (Phase 1 table and column names = canonical names)
# ---------------------------------------------------------------------------
TABLES = ["Healthcare_Professional", "Unit", "ICD9_Code", "Patient", "Admission",
          "TriageAssessment", "Diagnosis", "ClinicalNote", "SurgicalProcedure",
          "DischargeRecord", "DiagnosticOrder", "DiagnosticExamination",
          "RadiologyExamination", "RadiologyReport", "UnitStay",
          "CriticalCareRecord", "GeneralWardRecord"]
PK = {"Healthcare_Professional": "staff_id", "Unit": "unit_id", "ICD9_Code": "icd9_code",
      "Patient": "patient_id", "Admission": "admission_id", "TriageAssessment": "triage_id",
      "Diagnosis": "diagnosis_id", "ClinicalNote": "note_id", "SurgicalProcedure": "procedure_id",
      "DischargeRecord": "discharge_id", "DiagnosticOrder": "order_id",
      "DiagnosticExamination": "diag_exam_id", "RadiologyExamination": "exam_id",
      "RadiologyReport": "report_id", "UnitStay": "unit_stay_id",
      "CriticalCareRecord": "record_id", "GeneralWardRecord": "ward_record_id"}
STAFF_FK = {"staff_id", "admitting_healthcare_professional", "nurse_id", "physician_id",
            "diagnosing_physician_id", "surgeon_id", "responsible_physician_id",
            "requesting_physician_id", "referring_physician_id", "rad_tech_id",
            "radiologist_id", "performed_by_id"}
CRIT = ("ICU", "CCU", "MICU", "SICU")

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
# Real ICD-9-CM codes (stored as strings). Titles should still be checked
# against the official CMS ICD-9-CM v32 code list before submission.
ICD9 = [
    ("008.45", "Intestinal infection due to Clostridium difficile", "C. difficile colitis"),
    ("038.9", "Unspecified septicemia", "Bloodstream infection, organism not specified"),
    ("042", "Human immunodeficiency virus [HIV] disease", "HIV disease"),
    ("070.54", "Chronic hepatitis C without mention of hepatic coma", "Chronic hepatitis C"),
    ("153.9", "Malignant neoplasm of colon, unspecified site", "Colon cancer"),
    ("162.9", "Malignant neoplasm of bronchus and lung, unspecified", "Lung cancer"),
    ("174.9", "Malignant neoplasm of breast (female), unspecified", "Breast cancer"),
    ("185", "Malignant neoplasm of prostate", "Prostate cancer"),
    ("250.00", "Diabetes mellitus without mention of complication, type II or unspecified type, not stated as uncontrolled", "Type 2 diabetes without complication"),
    ("250.13", "Diabetes with ketoacidosis, type I [juvenile type], uncontrolled", "Diabetic ketoacidosis, type 1"),
    ("276.1", "Hyposmolality and/or hyponatremia", "Low blood sodium"),
    ("276.51", "Dehydration", "Dehydration"),
    ("285.9", "Anemia, unspecified", "Anemia"),
    ("296.20", "Major depressive affective disorder, single episode, unspecified", "Major depression, single episode"),
    ("303.00", "Acute alcoholic intoxication in alcoholism, unspecified", "Acute alcohol intoxication"),
    ("345.90", "Epilepsy, unspecified, without mention of intractable epilepsy", "Epilepsy"),
    ("401.9", "Unspecified essential hypertension", "High blood pressure"),
    ("410.11", "Acute myocardial infarction of other anterior wall, initial episode of care", "Anterior wall heart attack"),
    ("410.71", "Subendocardial infarction, initial episode of care", "NSTEMI heart attack"),
    ("414.01", "Coronary atherosclerosis of native coronary artery", "Coronary artery disease"),
    ("415.19", "Other pulmonary embolism and infarction", "Pulmonary embolism"),
    ("427.31", "Atrial fibrillation", "Atrial fibrillation"),
    ("428.0", "Congestive heart failure, unspecified", "Heart failure"),
    ("430", "Subarachnoid hemorrhage", "Subarachnoid bleed"),
    ("431", "Intracerebral hemorrhage", "Bleeding within the brain"),
    ("434.91", "Cerebral artery occlusion, unspecified with cerebral infarction", "Ischemic stroke"),
    ("453.40", "Acute venous embolism and thrombosis of unspecified deep vessels of lower extremity", "Deep vein thrombosis of leg"),
    ("486", "Pneumonia, organism unspecified", "Pneumonia"),
    ("491.21", "Obstructive chronic bronchitis with (acute) exacerbation", "COPD exacerbation"),
    ("493.92", "Asthma, unspecified type, with (acute) exacerbation", "Asthma attack"),
    ("496", "Chronic airway obstruction, not elsewhere classified", "Chronic obstructive pulmonary disease"),
    ("518.81", "Acute respiratory failure", "Acute respiratory failure"),
    ("540.9", "Acute appendicitis without mention of peritonitis", "Acute appendicitis"),
    ("550.90", "Inguinal hernia, without mention of obstruction or gangrene, unilateral or unspecified (not specified as recurrent)", "Inguinal hernia"),
    ("560.9", "Unspecified intestinal obstruction", "Bowel obstruction"),
    ("571.2", "Alcoholic cirrhosis of liver", "Alcoholic liver cirrhosis"),
    ("574.00", "Calculus of gallbladder with acute cholecystitis, without mention of obstruction", "Gallstones with acute gallbladder inflammation"),
    ("577.0", "Acute pancreatitis", "Acute pancreatitis"),
    ("578.9", "Hemorrhage of gastrointestinal tract, unspecified", "Gastrointestinal bleeding"),
    ("584.9", "Acute kidney failure, unspecified", "Acute kidney injury"),
    ("585.9", "Chronic kidney disease, unspecified", "Chronic kidney disease"),
    ("599.0", "Urinary tract infection, site not specified", "Urinary tract infection"),
    ("682.6", "Cellulitis and abscess of leg, except foot", "Leg cellulitis"),
    ("715.96", "Osteoarthrosis, unspecified whether generalized or localized, lower leg", "Knee osteoarthritis"),
    ("724.2", "Lumbago", "Low back pain"),
    ("780.2", "Syncope and collapse", "Fainting"),
    ("780.39", "Other convulsions", "Seizure"),
    ("780.60", "Fever, unspecified", "Fever"),
    ("786.50", "Chest pain, unspecified", "Chest pain"),
    ("787.01", "Nausea with vomiting", "Nausea and vomiting"),
    ("789.00", "Abdominal pain, unspecified site", "Abdominal pain"),
    ("805.4", "Closed fracture of lumbar vertebra without mention of spinal cord injury", "Lumbar spine fracture"),
    ("813.42", "Other closed fractures of distal end of radius (alone)", "Wrist fracture"),
    ("820.8", "Closed fracture of unspecified part of neck of femur", "Hip fracture"),
    ("850.9", "Concussion, unspecified", "Concussion"),
    ("852.20", "Subdural hemorrhage following injury without mention of open intracranial wound, unspecified state of consciousness", "Traumatic subdural bleed"),
    ("995.91", "Sepsis", "Sepsis"),
    ("995.92", "Severe sepsis", "Severe sepsis"),
    ("997.31", "Ventilator associated pneumonia", "Ventilator-associated pneumonia"),
    ("998.59", "Other postoperative infection", "Post-operative infection"),
    ("V58.11", "Encounter for antineoplastic chemotherapy", "Chemotherapy session"),
]
ICD_DESC = {c: d for c, _, d in ICD9}

CHAPTERS = [(1, 139, "Infectious and Parasitic Diseases"), (140, 239, "Neoplasms"),
            (240, 279, "Endocrine, Nutritional and Metabolic Diseases, and Immunity Disorders"),
            (280, 289, "Diseases of the Blood and Blood-Forming Organs"), (290, 319, "Mental Disorders"),
            (320, 389, "Diseases of the Nervous System and Sense Organs"),
            (390, 459, "Diseases of the Circulatory System"), (460, 519, "Diseases of the Respiratory System"),
            (520, 579, "Diseases of the Digestive System"), (580, 629, "Diseases of the Genitourinary System"),
            (680, 709, "Diseases of the Skin and Subcutaneous Tissue"),
            (710, 739, "Diseases of the Musculoskeletal System and Connective Tissue"),
            (780, 799, "Symptoms, Signs, and Ill-Defined Conditions"), (800, 999, "Injury and Poisoning")]


def chapter(code):
    if code.startswith("V"):
        return "Supplementary Classification of Factors Influencing Health Status and Contact with Health Services"
    n = int(code.split(".")[0])
    for lo, hi, name in CHAPTERS:
        if lo <= n <= hi:
            return name
    return "Other"


PATHWAYS = {
    "cardiac": dict(w=15, codes=["410.71", "410.11", "428.0", "427.31", "414.01", "786.50"], types=(70, 10, 20),
                    crit=0.50, crit_units=["CCU", "CCU", "CCU", "ICU"], surg=0.20,
                    surgeries=["Percutaneous Coronary Intervention", "Coronary Artery Bypass Graft", "Permanent Pacemaker Insertion"],
                    imaging=[("X-Ray", "Chest"), ("CT", "Chest"), ("Ultrasound", "Heart")],
                    labs=["Troponin Panel", "Electrocardiogram", "Lipid Panel"], mort=0.05,
                    spec="Cardiology", surg_spec="Cardiothoracic Surgery", ward="Cardiology Ward 5",
                    reasons=["Chest pain", "Shortness of breath", "Palpitations", "Syncope with chest pain"],
                    symptoms=["Chest pain radiating to left arm", "Shortness of breath on exertion",
                              "Palpitations and dizziness", "Chest tightness with sweating", "Leg swelling and orthopnea"]),
    "respiratory": dict(w=14, codes=["486", "491.21", "493.92", "518.81", "415.19", "496"], types=(65, 5, 30),
                        crit=0.40, crit_units=["MICU", "ICU", "ICU"], surg=0.03,
                        surgeries=["Bronchoscopy with Biopsy", "Chest Tube Insertion"],
                        imaging=[("X-Ray", "Chest"), ("CT", "Chest")],
                        labs=["Arterial Blood Gas", "Complete Blood Count", "Sputum Culture"], mort=0.06,
                        spec="Pulmonology", surg_spec="Cardiothoracic Surgery", ward="Medicine Ward 3A",
                        reasons=["Shortness of breath", "Productive cough and fever", "Wheezing", "Low oxygen saturation"],
                        symptoms=["Productive cough with fever", "Wheezing and shortness of breath",
                                  "Pleuritic chest pain", "Increasing breathlessness over 3 days"]),
    "sepsis": dict(w=10, codes=["038.9", "995.91", "995.92", "599.0", "682.6", "008.45", "780.60"], types=(80, 0, 20),
                   crit=0.45, crit_units=["MICU", "MICU", "ICU"], surg=0.05,
                   surgeries=["Incision and Drainage of Abscess", "Central Line Insertion"],
                   imaging=[("X-Ray", "Chest"), ("Ultrasound", "Abdomen"), ("CT", "Abdomen")],
                   labs=["Blood Culture", "Complete Blood Count", "Lactate Level", "Urinalysis"], mort=0.08,
                   spec="Infectious Disease", surg_spec="General Surgery", ward="Medicine Ward 3B",
                   reasons=["Fever and confusion", "Fever and low blood pressure", "Painful red swollen leg",
                            "Burning urination with fever"],
                   symptoms=["Fever, chills and confusion", "Fever with low blood pressure",
                             "Red, hot, swollen lower leg", "Diarrhea and abdominal cramps"]),
    "neuro": dict(w=10, codes=["434.91", "431", "430", "345.90", "780.39", "850.9", "852.20", "780.2"], types=(80, 5, 15),
                  crit=0.40, crit_units=["ICU", "ICU", "MICU"], surg=0.12,
                  surgeries=["Craniotomy", "Burr Hole Evacuation", "Mechanical Thrombectomy"],
                  imaging=[("CT", "Head"), ("MRI", "Brain"), ("CT", "Neck Vessels")],
                  labs=["Complete Blood Count", "Coagulation Panel", "Electroencephalogram"], mort=0.07,
                  spec="Neurology", surg_spec="Neurosurgery", ward="Medicine Ward 3A",
                  reasons=["Sudden weakness", "Seizure", "Head injury", "Severe headache", "Fainting episode"],
                  symptoms=["Sudden right-sided weakness and slurred speech", "Witnessed generalized seizure",
                            "Head injury after fall", "Worst headache of life", "Brief loss of consciousness"]),
    "gi": dict(w=13, codes=["540.9", "574.00", "577.0", "578.9", "560.9", "550.90", "789.00", "787.01"], types=(55, 25, 20),
               crit=0.15, crit_units=["SICU", "SICU", "ICU"], surg=0.55,
               surgeries=["Laparoscopic Appendectomy", "Laparoscopic Cholecystectomy", "Exploratory Laparotomy",
                          "Inguinal Hernia Repair", "Upper GI Endoscopy"],
               imaging=[("CT", "Abdomen"), ("Ultrasound", "Abdomen"), ("X-Ray", "Abdomen")],
               labs=["Lipase", "Liver Function Panel", "Complete Blood Count"], mort=0.02,
               spec="Gastroenterology", surg_spec="General Surgery", ward="Surgical Ward 4A",
               reasons=["Abdominal pain", "Vomiting", "Black stools", "Groin swelling"],
               symptoms=["Right lower quadrant abdominal pain", "Upper abdominal pain after meals",
                         "Vomiting and abdominal distension", "Black tarry stools", "Painful groin bulge"]),
    "ortho": dict(w=10, codes=["820.8", "805.4", "813.42", "715.96", "724.2"], types=(50, 35, 15),
                  crit=0.10, crit_units=["SICU", "ICU"], surg=0.70,
                  surgeries=["Hip Hemiarthroplasty", "Open Reduction Internal Fixation", "Total Knee Arthroplasty", "Spinal Fusion"],
                  imaging=[("X-Ray", "Hip"), ("X-Ray", "Wrist"), ("CT", "Spine"), ("X-Ray", "Knee")],
                  labs=["Complete Blood Count", "Coagulation Panel"], mort=0.02,
                  spec="Internal Medicine", surg_spec="Orthopedic Surgery", ward="Orthopedic Ward 6",
                  reasons=["Fall with hip pain", "Back pain after fall", "Wrist injury", "Knee pain"],
                  symptoms=["Hip pain, unable to bear weight after fall", "Severe lower back pain after fall",
                            "Wrist deformity after fall", "Chronic knee pain limiting walking"]),
    "renal": dict(w=10, codes=["584.9", "585.9", "250.13", "276.1", "276.51", "285.9", "250.00"], types=(60, 10, 30),
                  crit=0.20, crit_units=["MICU", "ICU"], surg=0.04,
                  surgeries=["Dialysis Catheter Insertion", "Arteriovenous Fistula Creation"],
                  imaging=[("Ultrasound", "Kidney"), ("X-Ray", "Chest")],
                  labs=["Basic Metabolic Panel", "Urinalysis", "Complete Blood Count", "Blood Glucose"], mort=0.03,
                  spec="Nephrology", surg_spec="Vascular Surgery", ward="Medicine Ward 3B",
                  reasons=["Weakness and confusion", "Reduced urine output", "High blood sugar", "Fatigue"],
                  symptoms=["Reduced urine output and swelling", "Extreme thirst and vomiting",
                            "Fatigue and dizziness", "Confusion and muscle cramps"]),
    "oncology": dict(w=8, codes=["162.9", "153.9", "174.9", "185", "V58.11"], types=(20, 60, 20),
                     crit=0.10, crit_units=["SICU", "ICU"], surg=0.45,
                     surgeries=["Lobectomy", "Colectomy", "Mastectomy", "Radical Prostatectomy", "Port-a-Cath Insertion"],
                     imaging=[("CT", "Chest"), ("CT", "Abdomen"), ("MRI", "Pelvis")],
                     labs=["Complete Blood Count", "Tumor Markers", "Liver Function Panel"], mort=0.04,
                     spec="Oncology", surg_spec="General Surgery", ward="Oncology Ward 7",
                     reasons=["Planned surgery", "Chemotherapy", "Weight loss", "Cough with blood"],
                     symptoms=["Unintentional weight loss", "Cough with blood-streaked sputum",
                               "Change in bowel habits", "Breast lump"]),
    "other": dict(w=10, codes=["296.20", "303.00", "571.2", "401.9", "070.54", "453.40", "998.59"], types=(60, 10, 30),
                  crit=0.08, crit_units=["MICU", "ICU"], surg=0.03,
                  surgeries=["Paracentesis", "Incision and Drainage of Wound"],
                  imaging=[("Ultrasound", "Abdomen"), ("Ultrasound", "Leg Veins"), ("X-Ray", "Chest")],
                  labs=["Liver Function Panel", "Complete Blood Count", "Toxicology Screen"], mort=0.02,
                  spec="Internal Medicine", surg_spec="General Surgery", ward="Medicine Ward 3B",
                  reasons=["Low mood", "Intoxication", "Abdominal swelling", "Leg swelling", "Wound redness"],
                  symptoms=["Low mood and poor sleep", "Intoxicated, vomiting", "Abdominal swelling and jaundice",
                            "Painful swollen calf", "Redness and discharge at surgical wound"]),
}
SECONDARY = ["401.9", "250.00", "428.0", "427.31", "585.9", "285.9", "276.51", "496", "303.00",
             "296.20", "724.2", "276.1"]

UNITS = [("Emergency Department", "Emergency"), ("Medical ICU", "MICU"), ("Surgical ICU", "SICU"),
         ("General ICU", "ICU"), ("Coronary Care Unit", "CCU"), ("Medicine Ward 3A", "General Ward"),
         ("Medicine Ward 3B", "General Ward"), ("Surgical Ward 4A", "General Ward"),
         ("Cardiology Ward 5", "General Ward"), ("Orthopedic Ward 6", "General Ward"),
         ("Oncology Ward 7", "General Ward"), ("Step-Down Unit", "Step-Down")]
ROOM_PREFIX = {"Emergency Department": "ED", "Medical ICU": "MI", "Surgical ICU": "SI", "General ICU": "GI",
               "Coronary Care Unit": "CC", "Medicine Ward 3A": "3A", "Medicine Ward 3B": "3B",
               "Surgical Ward 4A": "4A", "Cardiology Ward 5": "5C", "Orthopedic Ward 6": "6R",
               "Oncology Ward 7": "7N", "Step-Down Unit": "SD"}

STAFF_PLAN = [
    ("Physician", ["Emergency Medicine"] * 4 + ["Internal Medicine"] * 3 + ["Cardiology"] * 2 + ["Pulmonology"] * 2
     + ["Neurology"] * 2 + ["Critical Care"] * 3 + ["Gastroenterology", "Oncology", "Oncology", "Nephrology",
                                                     "Endocrinology", "Infectious Disease"]),
    ("Surgeon", ["General Surgery"] * 3 + ["Orthopedic Surgery"] * 2 + ["Cardiothoracic Surgery", "Neurosurgery",
                                                                         "Vascular Surgery"]),
    ("Nurse", ["Emergency"] * 6 + ["Critical Care"] * 6 + ["Ward"] * 6 + [None] * 4),
    ("Radiologist", ["Diagnostic Radiology"] * 5),
    ("Radiology Technician", ["CT", "MRI", "Ultrasound", "General Radiography", None, None]),
    ("Lab Technician", ["Clinical Chemistry", "Hematology", "Microbiology", None, None, "Clinical Chemistry", None]),
]

NAMES = {
    "NA": (["James", "Olivia", "Liam", "Emma", "Noah", "Ava", "Ethan", "Sophia", "Mason", "Isabella", "Lucas", "Mia",
            "Logan", "Charlotte", "Jacob", "Amelia", "Benjamin", "Harper", "Daniel", "Evelyn", "Samuel", "Abigail",
            "Owen", "Emily", "Nathan", "Chloe", "Ryan", "Grace", "Dylan", "Zoe"],
           ["Smith", "Johnson", "Brown", "Tremblay", "Martin", "Roy", "Wilson", "Taylor", "Anderson", "Thomas", "Moore",
            "Jackson", "White", "Harris", "Clark", "Lewis", "Walker", "Young", "King", "Wright", "Gagnon", "Campbell",
            "Mitchell", "Carter", "Morgan"]),
    "EU": (["Lukas", "Sofia", "Matteo", "Emma", "Hugo", "Lena", "Leon", "Chiara", "Mateo", "Anna", "Louis", "Marie",
            "Jan", "Eva", "Tomas", "Clara", "Felix", "Elena", "Oliver", "Julia", "Pierre", "Inès", "Marco", "Léa",
            "Nils", "Freya", "Pablo", "Alba", "Erik", "Nora"],
           ["Müller", "Rossi", "Dubois", "García", "Schmidt", "Bianchi", "Martin", "Fernández", "Novak", "Jansen",
            "Bernard", "Ricci", "Fischer", "López", "Weber", "Moreau", "Kowalski", "Andersson", "Romano", "Petit",
            "Nielsen", "Horvat", "Silva", "Lefebvre", "Wagner"]),
    "AS": (["Hiroshi", "Yuki", "Wei", "Mei", "Jun", "Hana", "Arjun", "Priya", "Min-jun", "Ji-woo", "Kenji", "Sakura",
            "Rahul", "Ananya", "Hao", "Lin", "Takeshi", "Aiko", "Vikram", "Lakshmi", "Minh", "Linh", "Somchai",
            "Malee", "Rizal", "Siti", "Daichi", "Yuna", "Ravi", "Neha"],
           ["Tanaka", "Sato", "Wang", "Li", "Zhang", "Kim", "Park", "Lee", "Sharma", "Patel", "Nguyen", "Tran",
            "Suzuki", "Chen", "Liu", "Gupta", "Singh", "Yamamoto", "Choi", "Watanabe", "Pham", "Wongsakul", "Rahman",
            "Huang", "Ito"]),
    "AF": (["Thabo", "Amara", "Kwame", "Zanele", "Sipho", "Nia", "Tendai", "Ayana", "Kofi", "Lerato", "Chinedu",
            "Fatima", "Jabari", "Naledi", "Musa", "Adaeze", "Bongani", "Imani", "Kagiso", "Zuri", "Tunde", "Palesa",
            "Abebe", "Makena", "Juma", "Nomvula", "Yaw", "Ama", "Lwazi", "Thandiwe"],
           ["Nkosi", "Mensah", "Dlamini", "Okafor", "Mokoena", "Banda", "Mwangi", "Naidoo", "Ndlovu", "Adeyemi",
            "Khumalo", "Osei", "Botha", "Tadesse", "Kamau", "Mahlangu", "Diallo", "Sithole", "Owusu", "Moyo",
            "Van der Merwe", "Achieng", "Phiri", "Zulu", "Kariuki"]),
}
FEMALE = {"Olivia", "Emma", "Ava", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia", "Harper", "Evelyn", "Abigail",
          "Emily", "Chloe", "Grace", "Zoe", "Sofia", "Lena", "Chiara", "Anna", "Marie", "Eva", "Clara", "Elena",
          "Julia", "Inès", "Léa", "Freya", "Alba", "Nora", "Yuki", "Mei", "Hana", "Priya", "Ji-woo", "Sakura",
          "Ananya", "Lin", "Aiko", "Lakshmi", "Linh", "Malee", "Siti", "Yuna", "Neha", "Amara", "Zanele", "Nia",
          "Ayana", "Lerato", "Fatima", "Naledi", "Adaeze", "Imani", "Zuri", "Palesa", "Makena", "Nomvula", "Ama",
          "Thandiwe"}

REGION_INFO = {
    "NA": dict(streets=["Maple", "Cedar", "Birch", "Lakeshore", "King", "Queen", "Elm", "Pine", "Willow", "Oak"],
               suffix=["St", "Ave", "Rd", "Dr"], cities=["Northport", "Lakeview", "Fairhaven", "Brookfield", "Clearwater"],
               insurance=["Provincial Health Plan", "Provincial Health Plan + Northwind Mutual", "Maple Shield Insurance", "Self-pay"]),
    "EU": dict(streets=["Rue des Lilas", "Via Verdi", "Lindenweg", "Calle del Olmo", "Kerkstraat", "Rosenstraße"],
               cities=["Valmont", "Rosenau", "Bellacqua", "Santa Clara de Mar", "Oosterwijk"],
               insurance=["Statutory Health Insurance", "EuroCare Mutual", "Alpina Assist (private)", "Self-pay"]),
    "AS": dict(streets=["Midori-cho", "Sakura-dori", "Hikari Avenue", "Lotus Garden Road", "Riverside Lane"],
               cities=["Kitahama", "Nanshan Bay", "Haeundo", "Sunpur"],
               insurance=["National Health Insurance", "Employee Health Insurance", "Lotus Life Private", "Self-pay"]),
    "AF": dict(streets=["Jacaranda St", "Protea Rd", "Baobab Ave", "Acacia Lane", "Marula Cres"],
               cities=["Kopanong Heights", "Ridgeview", "Lakeside", "Umzimvale"],
               insurance=["Ubuntu Medical Aid", "Savanna Health Scheme", "State Patient", "Self-pay"]),
}

ALLERGIES = ["None known"] * 6 + ["Penicillin", "Sulfa drugs", "Latex", "Peanuts", "Codeine", "Iodinated contrast"]
MEDS = ["None"] * 4 + ["Metformin", "Lisinopril", "Atorvastatin", "Aspirin", "Salbutamol inhaler", "Levothyroxine",
                       "Warfarin", "Amlodipine", "Metformin, Atorvastatin", "Furosemide"]
PE = ["Alert and oriented, mild distress", "Diaphoretic, tachycardic", "Decreased breath sounds at right base",
      "Tender right lower quadrant", "Warm, erythematous left calf", "No focal neurological deficit",
      "Right-sided weakness 3/5", "Shortened, externally rotated right leg", "Bilateral ankle edema"]
FINDINGS = ["Elevated white cell count", "ST depression on ECG", "Hypoxemia on room air", "Raised creatinine",
            "Lactate 3.1 mmol/L", "Normal initial bloods", "Hyponatremia", "Low hemoglobin"]
TREAT = ["IV fluids and analgesia", "Aspirin, heparin and nitrates", "IV antibiotics", "Nebulized bronchodilators",
         "Oxygen therapy", "Nil by mouth, IV fluids", "Insulin infusion", "Pain control and immobilization"]
PROGRESS = ["Patient stable overnight. Continue current management.",
            "Improving clinically, mobilizing with physiotherapy.",
            "Ongoing fever, antibiotics reviewed.", "Pain controlled, tolerating oral diet.",
            "Vital signs within normal limits. Plan reviewed with team."]
RECOVERY_TXT = ["Uneventful recovery. Discharged home in stable condition.",
                "Good recovery after treatment; follow-up arranged.",
                "Recovery progressing well, independent with mobility.",
                "Satisfactory post-operative recovery. Wound clean and dry.",
                "Patient made a full RECOVERY and is fit for discharge."]
OTHER_DC_TXT = ["Discharged with outpatient follow-up arranged.",
                "Symptoms resolved. Medication reconciliation completed.",
                "Discharged to rehabilitation for ongoing therapy.",
                "Stable for discharge; family informed of care plan."]
OUTCOMES = ["Successful, no complications", "Successful, minor bleeding controlled",
            "Completed; patient transferred to recovery area", "Complicated by transient arrhythmia, stabilized",
            "Successful, drain left in situ"]
ICU_MEDS = ["Norepinephrine infusion", "Propofol sedation", "IV piperacillin-tazobactam", "Heparin infusion",
            "Insulin infusion", "Furosemide IV", "Amiodarone infusion"]
ICU_OBS = ["Hemodynamically stable on low-dose vasopressors", "Ventilated, FiO2 weaned to 40%",
           "Urine output adequate", "Agitation overnight, sedation adjusted", "Afebrile for 24 hours"]
ICU_RESP = ["Improving", "Stable", "Slow improvement", "Not responding, escalated", "Good response"]
ICU_PROG = ["Continue current plan, reassess in AM", "Wean sedation, trial of spontaneous breathing",
            "Consider step-down tomorrow", "Repeat labs at 18:00", "Discussed goals of care with family"]
ICU_EXTRA = ["Repeat chest X-ray", "Arterial blood gas", "Echocardiogram", "Blood cultures x2"]
WARD_FU = ["Repeat bloods in 48 h", "Physiotherapy assessment", "Wound review", "Repeat ECG"]
WARD_MED = ["Oral antibiotics", "Analgesia as required", "Low molecular weight heparin", "Regular inhalers",
            "Oral iron supplements"]
WARD_PROG = ["Mobilizing independently", "Eating and drinking well", "Mild pain, controlled",
             "Awaiting physiotherapy clearance", "Clinically improving"]
WARD_TEST = ["Full blood count", "Renal function", "Liver function", None, None]
WARD_EVAL = ["Progressing as expected", "Slower than expected", "Ready for discharge planning", "Stable"]
LAB_RESULTS = {"Troponin Panel": ["Troponin I 2.4 ng/mL (elevated)", "Troponin I < 0.01 ng/mL (normal)"],
               "Electrocardiogram": ["Sinus tachycardia", "ST depression V4-V6", "Atrial fibrillation, rate 112"],
               "Arterial Blood Gas": ["pH 7.31, pCO2 58, pO2 62", "pH 7.42, pCO2 39, pO2 88"],
               "Blood Culture": ["Gram-negative rods isolated", "No growth at 48 hours"],
               "Urinalysis": ["Nitrite positive, leukocytes +++", "Unremarkable"],
               "Lipase": ["Lipase 1240 U/L (elevated)", "Lipase 45 U/L (normal)"]}
RAD_FIND = ["No acute abnormality", "Right lower lobe consolidation", "Small left pleural effusion",
            "Acute hypodensity in left MCA territory", "Inflamed appendix, 11 mm", "Gallstones with wall thickening",
            "Displaced subcapital femoral neck fracture", "Cardiomegaly with mild pulmonary edema",
            "3 cm spiculated mass in right upper lobe"]
RAD_INTERP = ["Findings consistent with clinical suspicion", "Findings likely represent infection",
              "Non-specific findings, clinical correlation advised", "Interval improvement compared with prior"]
RAD_CONC = ["Acute process identified", "No acute findings", "Follow-up imaging recommended",
            "Urgent surgical review advised"]


class Raw:
    """A value written to the source exactly as given (used for planted bad values)."""

    def __init__(self, v):
        self.v = v


def wchoice(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def rand_dt(rng, a, b):
    if b <= a:
        return a
    return a + timedelta(seconds=rng.uniform(0, (b - a).total_seconds()))


def rmin(dt):
    """Round to the minute (sources store minute precision)."""
    return dt.replace(second=0, microsecond=0) if dt else dt


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
SOURCES = [
    dict(code="A", continent="North America", hospital="Lakeshore General Hospital (fictional)",
         tz="America/Toronto (local time, EST/EDT, no offset stored)", fmt="TXT",
         folder="source_A_north_america", n_pat=245, region="NA"),
    dict(code="B", continent="Europe", hospital="St. Aurelia University Hospital (fictional)",
         tz="Europe/Paris (local time, CET/CEST, no offset stored)", fmt="CSV",
         folder="source_B_europe", n_pat=250, region="EU"),
    dict(code="C", continent="Asia", hospital="Sakura Bay Medical Center (fictional)",
         tz="Asia/Tokyo (local time, JST UTC+09:00, no offset stored)", fmt="XML",
         folder="source_C_asia", n_pat=240, region="AS"),
    dict(code="D", continent="Africa", hospital="Highveld Regional Hospital (fictional)",
         tz="Africa/Johannesburg (SAST, UTC+02:00, offset stored in each timestamp)", fmt="JSON",
         folder="source_D_africa", n_pat=255, region="AF"),
]
SRC = {s["code"]: s for s in SOURCES}


def make_hin(rng, code):
    if code == "A":
        return f"{rng.randint(10**9, 10**10 - 1)}-{rng.choice('ABCDEFGHJK')}{rng.choice('ABCDEFGHJK')}"
    if code == "B":
        return f"EU-{rng.randint(100, 999)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}"
    if code == "C":
        return f"JP{rng.randint(10**7, 10**8 - 1)}"
    return f"MA{rng.randint(10**8, 10**9 - 1)}"


def make_phone(rng, code):
    if code == "A":
        return f"(613) 555-{rng.randint(100, 199):04d}"
    if code == "B":
        return f"+44 20 7946 0{rng.randint(0, 999):03d}"
    if code == "C":
        return f"+81-90-0000-{rng.randint(0, 9999):04d}"
    return f"+27 82 000 {rng.randint(0, 9999):04d}"


def make_address(rng, region):
    info = REGION_INFO[region]
    if region == "NA":
        return f"{rng.randint(10, 9999)} {rng.choice(info['streets'])} {rng.choice(info['suffix'])}, {rng.choice(info['cities'])}"
    if region == "EU":
        return f"{rng.choice(info['streets'])} {rng.randint(1, 120)}, {rng.randint(10000, 99999)} {rng.choice(info['cities'])}"
    if region == "AS":
        return f"{rng.randint(1, 9)}-{rng.randint(1, 30)} {rng.choice(info['streets'])}, {rng.choice(info['cities'])}"
    return f"{rng.randint(1, 400)} {rng.choice(info['streets'])}, {rng.choice(info['cities'])}"


def make_person(rng, code, region):
    F, L = NAMES[region]
    first, last = rng.choice(F), rng.choice(L)
    if rng.random() < 0.02:
        dob = date(rng.randint(2008, 2019), rng.randint(1, 12), rng.randint(1, 28))
    else:
        dob = date(rng.randint(1932, 2004), rng.randint(1, 12), rng.randint(1, 28))
    g = "Female" if first in FEMALE else "Male"
    if rng.random() < 0.02:
        g = "Other"
    return dict(first=first, last=last, dob=dob, gender=g if rng.random() > 0.02 else None,
                hin=make_hin(rng, code),
                address=make_address(rng, region) if rng.random() > 0.05 else None,
                phone=make_phone(rng, code) if rng.random() > 0.08 else None,
                ec_name=(f"{rng.choice(F)} {last}" if rng.random() > 0.15 else None),
                ec_phone=make_phone(rng, code))


def plan_people(rng):
    """People per source, plus cross-source matches (answer key returned)."""
    people = {}
    for s in SOURCES:
        people[s["code"]] = [make_person(rng, s["code"], s["region"]) for _ in range(s["n_pat"])]
    xkey = []
    pairs = [("A", "B"), ("A", "C"), ("A", "D"), ("B", "C"), ("B", "D"), ("C", "D")]
    early = (datetime(2024, 1, 3), datetime(2025, 5, 31))
    late = (datetime(2025, 9, 1), datetime(2026, 9, 15))
    g = 0
    # 1) certain matches: travellers, same international insurance no. + name + DOB
    for i in range(24):
        s1, s2 = pairs[i % 6]
        g += 1
        p1 = people[s1][5 + i]
        intl = f"INTL-{rng.randint(10**7, 10**8 - 1)}"
        p1["hin"] = intl
        p1["_window"] = early
        p1["_nadm"] = rng.choice([1, 1, 2])
        p2 = make_person(rng, s2, SRC[s2]["region"])
        p2.update(first=p1["first"], last=p1["last"], dob=p1["dob"], gender=p1["gender"], hin=intl,
                  _window=late, _nadm=rng.choice([1, 1, 2]))
        people[s2][40 + i] = p2
        p1["_x"] = (g, "certain_match")
        p2["_x"] = (g, "certain_match")
    # 2) uncertain: same name + DOB, different insurance numbers
    for i in range(4):
        s1, s2 = pairs[(i + 2) % 6]
        g += 1
        p1 = people[s1][80 + i]
        p2 = people[s2][90 + i]
        p2.update(first=p1["first"], last=p1["last"], dob=p1["dob"], gender=p1["gender"])
        p1["_x"] = (g, "uncertain_match")
        p2["_x"] = (g, "uncertain_match")
    # 3) namesakes: same name, different person (different DOB and insurance no.)
    for i in range(12):
        s1, s2 = pairs[(i + 4) % 6]
        g += 1
        p1 = people[s1][110 + i]
        p2 = people[s2][120 + i]
        p2.update(first=p1["first"], last=p1["last"])
        while p2["dob"] == p1["dob"]:
            p2["dob"] = p2["dob"] + DY(400)
        p1["_x"] = (g, "different_person_same_name")
        p2["_x"] = (g, "different_person_same_name")
    return people


# ---------------------------------------------------------------------------
# Build the clean canonical data for one source
# ---------------------------------------------------------------------------
def build_source(S, rng, persons):
    T = {t: [] for t in TABLES}
    ctr = {t: 0 for t in TABLES}

    def nid(t):
        ctr[t] += 1
        return ctr[t]

    region = S["region"]
    F, L = NAMES[region]
    by = {}
    for role, specs in STAFF_PLAN:
        for spec in specs:
            sid = nid("Healthcare_Professional")
            T["Healthcare_Professional"].append(dict(staff_id=sid, first_name=rng.choice(F), last_name=rng.choice(L),
                                                     staff_type=role, specialty=spec))
            by.setdefault(role, []).append(sid)
            by.setdefault((role, spec), []).append(sid)

    def phys(spec):
        return rng.choice(by.get(("Physician", spec)) or by["Physician"])

    def surgeon(spec):
        return rng.choice(by.get(("Surgeon", spec)) or by["Surgeon"])

    def nurse(spec):
        return rng.choice(by.get(("Nurse", spec)) or by["Nurse"])

    unit_by_type, unit_by_name, unit_name_of = {}, {}, {}
    for name, typ in UNITS:
        uid = nid("Unit")
        T["Unit"].append(dict(unit_id=uid, unit_name=name, unit_type=typ))
        unit_by_type.setdefault(typ, []).append(uid)
        unit_by_name[name] = uid
        unit_name_of[uid] = name
    for code, title, desc in ICD9:
        T["ICD9_Code"].append(dict(icd9_code=code, official_title=title, description=desc,
                                   disease_category=chapter(code)))

    ins = REGION_INFO[region]["insurance"]

    def make_admission(pid, t0, active):
        pwn = wchoice(rng, list(PATHWAYS), [v["w"] for v in PATHWAYS.values()])
        pw = PATHWAYS[pwn]
        aid = nid("Admission")
        atype = wchoice(rng, ["Emergency", "Elective", "Urgent"], pw["types"])
        if atype == "Emergency":
            asrc = wchoice(rng, ["Emergency Department", "Transfer from Another Hospital"], [88, 12])
        elif atype == "Urgent":
            asrc = wchoice(rng, ["Emergency Department", "Physician Referral", "Transfer from Another Hospital"], [50, 30, 20])
        else:
            asrc = wchoice(rng, ["Physician Referral", "Clinic"], [60, 40])
        crit = rng.random() < pw["crit"] * (1.25 if atype == "Emergency" else 0.6)
        do_surg = rng.random() < min(0.9, pw["surg"] * (1.5 if atype == "Elective" else 1.0))
        stays = []
        t = t0
        surg_t = None
        if asrc == "Emergency Department":
            d = H(rng.uniform(1.5, 9))
            stays.append(["Emergency", t, t + d])
            t += d
        pre_op = do_surg and crit and rng.random() < 0.65
        if pre_op:
            surg_t = t + H(rng.uniform(1, 5))
            if not stays:   # direct admission: patient is on the surgical/medical ward pre-op
                stays.append(["General Ward", t0, surg_t + H(rng.uniform(2, 4))])
                t = stays[-1][2]
            else:
                stays[-1][2] = surg_t + H(rng.uniform(2, 4))
                t = stays[-1][2]
        if crit:
            if pre_op and pwn in ("gi", "ortho", "oncology"):
                cu = "SICU" if rng.random() < 0.7 else "ICU"
            else:
                cu = rng.choice(pw["crit_units"])
            days = rng.uniform(7.3, 16) if rng.random() < 0.25 else rng.uniform(0.8, 6.5)
            stays.append([cu, t, t + DY(days)])
            t += DY(days)
            if rng.random() < 0.16:
                cu2 = rng.choice([u for u in CRIT if u != cu])
                d2 = rng.uniform(1, 5)
                stays.append([cu2, t, t + DY(d2)])
                t += DY(d2)
            if rng.random() < 0.35:
                d3 = rng.uniform(0.5, 2.5)
                stays.append(["Step-Down", t, t + DY(d3)])
                t += DY(d3)
        gw = rng.uniform(0.8, 4) if atype == "Elective" else rng.uniform(1, 9)
        stays.append(["General Ward", t, t + DY(gw)])
        t += DY(gw)
        disc = t
        if do_surg and surg_t is None:
            lo, hi = t0 + H(3), disc - H(10)
            surg_t = rand_dt(rng, lo, max(hi, lo + H(1)))

        status = "Discharged"
        if active:
            status = "Admitted"
        elif rng.random() < pw["mort"] * (2.5 if crit else 0.6):
            status = "Deceased"
        elif rng.random() < 0.06:
            status = "Transferred"
        if status == "Deceased":
            cidx = [i for i, s in enumerate(stays) if s[0] in CRIT]
            if cidx:
                stays = stays[:cidx[-1] + 1]
            disc = stays[-1][2]
        if active:
            stays = [s for s in stays if s[1] < AS_OF - H(2)] or stays[:1]
            stays[-1][2] = None
            disc = None
        end = disc if disc else AS_OF
        if surg_t and surg_t >= end - H(0.5):
            surg_t = None
        # round all event times to the minute
        t0 = rmin(t0)
        for s in stays:
            s[1], s[2] = rmin(s[1]), rmin(s[2])
        stays[0][1] = t0
        disc = rmin(disc)
        surg_t = rmin(surg_t)
        los_h = (end - t0).total_seconds() / 3600

        def within(lo_h, hi_h):
            """Random time between t0+lo_h and min(t0+hi_h, end-15min)."""
            a = t0 + H(lo_h)
            b = min(t0 + H(hi_h), end - H(0.25))
            return rmin(rand_dt(rng, a, b if b > a else a + H(0.1)))

        adm_md = phys("Emergency Medicine") if asrc == "Emergency Department" else phys(pw["spec"])
        T["Admission"].append(dict(
            admission_id=aid, patient_id=pid, admitting_healthcare_professional=adm_md, admission_datetime=t0,
            admission_type=atype, admission_source=asrc, reason=rng.choice(pw["reasons"]),
            insurance_info=rng.choice(ins) if rng.random() > 0.1 else None,
            condition_on_arrival=(wchoice(rng, ["Critical", "Serious", "Fair"], [40, 45, 15]) if crit
                                  else wchoice(rng, ["Stable", "Fair", "Serious"], [50, 35, 15])),
            discharge_datetime=disc, admission_status=status))

        # unit stays + critical care / ward records
        for i, (typ, a, b) in enumerate(stays):
            usid = nid("UnitStay")
            uid = unit_by_name[pw["ward"]] if typ == "General Ward" else unit_by_type[typ][0]
            if typ in CRIT:
                resp = phys("Critical Care")
            elif typ == "Emergency":
                resp = phys("Emergency Medicine")
            else:
                resp = phys(pw["spec"])
            if i == 0:
                reason = "Arrival via emergency department" if typ == "Emergency" else "Direct admission"
            elif typ in CRIT:
                reason = ("Post-operative monitoring" if pre_op and stays[i - 1][0] not in CRIT
                          else rng.choice(["Escalation of care", "Hemodynamic instability", "Respiratory deterioration"]))
            elif typ == "Step-Down":
                reason = "Step-down after stabilization"
            else:
                reason = rng.choice(["Transfer to ward for recovery", "Clinically improved", "Bed management"])
            pref = ROOM_PREFIX[unit_name_of[uid]]
            T["UnitStay"].append(dict(unit_stay_id=usid, admission_id=aid, unit_id=uid,
                                      ward_room=f"{pref}-{rng.randint(1, 30):02d}",
                                      bed_number=rng.choice("ABCD") if rng.random() > 0.15 else None,
                                      entry_datetime=a, exit_datetime=b, responsible_physician_id=resp,
                                      transfer_reason=reason))
            b2 = b or AS_OF
            if typ in CRIT:
                n = min(4, 1 + int((b2 - a).days // 2))
                times = sorted(rmin(rand_dt(rng, a + H(0.5), b2 - H(0.5))) for _ in range(n))
                for j, rt in enumerate(times):
                    T["CriticalCareRecord"].append(dict(
                        record_id=nid("CriticalCareRecord"), unit_stay_id=usid, record_datetime=rt,
                        vital_signs=f"HR {rng.randint(70, 130)}, BP {rng.randint(90, 160)}/{rng.randint(50, 95)}, "
                                    f"SpO2 {rng.randint(88, 100)}%, T {rng.uniform(36.2, 39.2):.1f}C",
                        medications=rng.choice(ICU_MEDS), observations=rng.choice(ICU_OBS),
                        response_to_treatment=rng.choice(ICU_RESP), physician_progress_notes=rng.choice(ICU_PROG),
                        additional_diagnostic_exams=rng.choice(ICU_EXTRA) if rng.random() < 0.6 else None,
                        transferred="Yes" if (j == n - 1 and i < len(stays) - 1) else "No"))
            if typ == "General Ward":
                n = min(3, 1 + int((b2 - a).days // 3))
                for _ in range(n):
                    T["GeneralWardRecord"].append(dict(
                        ward_record_id=nid("GeneralWardRecord"), admission_id=aid,
                        record_datetime=rmin(rand_dt(rng, a + H(0.5), b2 - H(0.5))),
                        follow_up_examinations=rng.choice(WARD_FU), medications_treatments=rng.choice(WARD_MED),
                        progress_notes=rng.choice(WARD_PROG), additional_tests=rng.choice(WARD_TEST),
                        recovery_eval=rng.choice(WARD_EVAL)))

        # triage
        if asrc == "Emergency Department" or (atype != "Elective" and rng.random() < 0.6):
            prio = (wchoice(rng, ["High", "Medium", "Low"], [70, 25, 5]) if crit
                    else wchoice(rng, ["High", "Medium", "Low"], [18, 50, 32]))
            if prio == "High":
                hr, sbp, o2, pain, tmp = (rng.randint(100, 145), rng.choice([rng.randint(80, 100), rng.randint(155, 190)]),
                                          rng.randint(84, 93), rng.randint(6, 10), rng.uniform(36.0, 39.9))
            elif prio == "Medium":
                hr, sbp, o2, pain, tmp = (rng.randint(85, 110), rng.randint(110, 150), rng.randint(92, 97),
                                          rng.randint(3, 8), rng.uniform(36.4, 38.5))
            else:
                hr, sbp, o2, pain, tmp = (rng.randint(60, 95), rng.randint(105, 140), rng.randint(95, 100),
                                          rng.randint(0, 5), rng.uniform(36.2, 37.6))
            T["TriageAssessment"].append(dict(
                triage_id=nid("TriageAssessment"), admission_id=aid, nurse_id=nurse("Emergency"),
                triage_datetime=rmin(t0 + timedelta(minutes=rng.uniform(5, 40))),
                blood_pressure=(sbp, int(sbp * rng.uniform(0.55, 0.68))), heart_rate=hr, pain_level=pain,
                symptoms=rng.choice(pw["symptoms"]), allergies=rng.choice(ALLERGIES),
                current_medication=rng.choice(MEDS), priority_level=prio, body_temp=round(tmp, 1), oxygen_sat=o2))

        # diagnoses
        prim = rng.choice(pw["codes"])
        T["Diagnosis"].append(dict(diagnosis_id=nid("Diagnosis"), patient_id=pid, admission_id=aid, icd9_code=prim,
                                   diagnosis_datetime=within(1, 10), diagnosis_type="Primary",
                                   diagnosing_physician_id=phys(pw["spec"])))
        pool = sorted(set(SECONDARY + pw["codes"]) - {prim})
        for c in rng.sample(pool, wchoice(rng, [0, 1, 2, 3], [30, 35, 25, 10])):
            T["Diagnosis"].append(dict(diagnosis_id=nid("Diagnosis"), patient_id=pid, admission_id=aid, icd9_code=c,
                                       diagnosis_datetime=within(1, los_h), diagnosis_type="Secondary",
                                       diagnosing_physician_id=phys(rng.choice([pw["spec"], "Internal Medicine"]))))

        # clinical notes
        planned = sorted({f"{e} {a}" for e, a in rng.sample(pw["imaging"], 1)} | {rng.choice(pw["labs"])})
        T["ClinicalNote"].append(dict(
            note_id=nid("ClinicalNote"), admission_id=aid, physician_id=adm_md, note_type="Admission Note",
            note_datetime=within(0.5, 4), symptoms=rng.choice(pw["symptoms"]), physical_exam=rng.choice(PE),
            initial_findings=rng.choice(FINDINGS), suspected_condition=ICD_DESC[prim],
            planned_examinations=", ".join(planned), initial_treatment=rng.choice(TREAT),
            note_text=f"Admitted with {ICD_DESC[prim].lower()}. Plan discussed with patient and family."))
        for _ in range(min(3, int(los_h // 48))):
            T["ClinicalNote"].append(dict(
                note_id=nid("ClinicalNote"), admission_id=aid, physician_id=phys(pw["spec"]), note_type="Progress Note",
                note_datetime=within(12, los_h), symptoms=None, physical_exam=rng.choice(PE) if rng.random() < 0.5 else None,
                initial_findings=None, suspected_condition=ICD_DESC[prim], planned_examinations=None,
                initial_treatment=None, note_text=rng.choice(PROGRESS)))
        if rng.random() < 0.2:
            T["ClinicalNote"].append(dict(
                note_id=nid("ClinicalNote"), admission_id=aid, physician_id=phys(rng.choice(["Internal Medicine", "Critical Care", "Cardiology"])),
                note_type="Consultation Note", note_datetime=within(2, los_h), symptoms=None, physical_exam=rng.choice(PE),
                initial_findings=rng.choice(FINDINGS), suspected_condition=ICD_DESC[prim], planned_examinations=None,
                initial_treatment=None, note_text="Consulted at request of primary team. Recommendations documented."))
        if status in ("Discharged", "Transferred"):
            txt = ("Transferred to another facility for ongoing specialist care." if status == "Transferred"
                   else rng.choice(RECOVERY_TXT) if rng.random() < 0.55 else rng.choice(OTHER_DC_TXT))
            T["ClinicalNote"].append(dict(
                note_id=nid("ClinicalNote"), admission_id=aid, physician_id=adm_md, note_type="Discharge Summary",
                note_datetime=rmin(disc - H(rng.uniform(0.5, 3))), symptoms=None, physical_exam=None, initial_findings=None,
                suspected_condition=ICD_DESC[prim], planned_examinations=None, initial_treatment=None, note_text=txt))
        if status == "Deceased":
            T["ClinicalNote"].append(dict(
                note_id=nid("ClinicalNote"), admission_id=aid, physician_id=phys("Critical Care"), note_type="Progress Note",
                note_datetime=rmin(disc - H(0.25)), symptoms=None, physical_exam=None, initial_findings=None,
                suspected_condition=ICD_DESC[prim], planned_examinations=None, initial_treatment=None,
                note_text="Patient deteriorated despite maximal therapy and was pronounced dead."))

        # surgery
        if surg_t:
            T["SurgicalProcedure"].append(dict(procedure_id=nid("SurgicalProcedure"), admission_id=aid,
                                               surgeon_id=surgeon(pw["surg_spec"]), procedure_type=rng.choice(pw["surgeries"]),
                                               procedure_datetime=surg_t,
                                               outcome=rng.choice(OUTCOMES) if rng.random() > 0.1 else None))

        # diagnostic orders -> radiology / lab examinations
        def new_order(exam_name, req, prio, status_):
            oid = nid("DiagnosticOrder")
            T["DiagnosticOrder"].append(dict(order_id=oid, admission_id=aid, patient_id=pid,
                                             requesting_physician_id=phys(pw["spec"]), requested_exam=exam_name,
                                             request_datetime=req, clinical_reason=rng.choice(pw["reasons"]) if rng.random() > 0.1 else None,
                                             priority=prio, order_status=status_))
            return oid

        n_img = wchoice(rng, [0, 1, 2], [40, 45, 15])
        for k in range(n_img):
            et, area = rng.choice(pw["imaging"])
            req = ex = None
            if k == 0 and surg_t and rng.random() < 0.55:
                cand = rmin(surg_t - H(rng.uniform(1.5, 4)))
                ex_c = rmin(cand + H(rng.uniform(0.3, 1.0)))
                if cand > t0 and ex_c.date() == surg_t.date() and ex_c < surg_t:
                    req, ex = cand, ex_c
            if req is None:
                req = within(0.5, min(48, max(1, los_h - 4)))
                ex = rmin(req + H(rng.uniform(0.3, 5)))
                if ex >= end - H(0.2):
                    ex = rmin(req + (end - req) / 2)
            prio = "STAT" if crit else rng.choice(["Urgent", "Routine"])
            st = "Completed"
            if active and rng.random() < 0.3:
                st = "Pending"
            elif rng.random() < 0.05:
                st = "Cancelled"
            oid = new_order(f"{et} {area}", req, prio, st)
            if st != "Completed":
                continue
            eid = nid("RadiologyExamination")
            T["RadiologyExamination"].append(dict(
                exam_id=eid, admission_id=aid, exam_type=et, order_id=oid, exam_datetime=ex, body_area=area,
                referring_physician_id=T["DiagnosticOrder"][-1]["requesting_physician_id"],
                rad_tech_id=rng.choice(by["Radiology Technician"]), exam_status="Completed",
                image_link=f"pacs://{S['code'].lower()}-imaging/studies/{eid:06d}" if rng.random() > 0.1 else None))
            rep = rmin(ex + H(rng.uniform(0.5, 10)))
            if rep > end:
                rep = rmin(ex + (end - ex) / 2)
            T["RadiologyReport"].append(dict(
                report_id=nid("RadiologyReport"), rad_exam_id=eid, radiologist_id=rng.choice(by["Radiologist"]),
                report_datetime=rep, findings=rng.choice(RAD_FIND), interpretation=rng.choice(RAD_INTERP),
                conclusion=rng.choice(RAD_CONC) if rng.random() > 0.1 else None))
        for lab in rng.sample(pw["labs"], min(len(pw["labs"]), wchoice(rng, [0, 1, 2], [25, 50, 25]))):
            req = within(0.3, min(72, max(1, los_h - 2)))
            st = "Pending" if (active and rng.random() < 0.3) else ("Cancelled" if rng.random() < 0.04 else "Completed")
            oid = new_order(lab, req, rng.choice(["STAT", "Urgent", "Routine"]), st)
            if st != "Completed":
                continue
            ex = rmin(req + H(rng.uniform(0.2, 3)))
            if ex >= end:
                ex = rmin(req + (end - req) / 2)
            T["DiagnosticExamination"].append(dict(
                diag_exam_id=nid("DiagnosticExamination"), order_id=oid, exam_type=lab, exam_datetime=ex,
                performed_by_id=rng.choice(by["Lab Technician"]),
                result=rng.choice(LAB_RESULTS.get(lab, ["Within normal limits", "Abnormal - see comment", "Mildly abnormal"])),
                exam_status="Completed"))

        # discharge record
        if status != "Admitted":
            if status == "Deceased":
                dest, cond = None, "Deceased"
            elif status == "Transferred":
                dest, cond = "Other Hospital", wchoice(rng, ["Stable", "Unchanged"], [70, 30])
            else:
                dest = wchoice(rng, ["Home", "Home with Home Care", "Rehabilitation Facility", "Long-Term Care"], [60, 15, 15, 10])
                cond = wchoice(rng, ["Improved", "Stable", "Unchanged"], [60, 35, 5])
            T["DischargeRecord"].append(dict(
                discharge_id=nid("DischargeRecord"), admission_id=aid, discharge_destination=dest,
                condition_at_discharge=cond,
                prescribed_medications=None if status == "Deceased" else rng.choice(MEDS[4:] + [None]),
                follow_up_instructions=None if status == "Deceased" else rng.choice(
                    ["Return if symptoms worsen", "Keep wound dry for 7 days", "Daily weights, low-salt diet",
                     "Complete antibiotic course", None]),
                follow_up_appointments=None if status == "Deceased" else rng.choice(
                    [f"{pw['spec']} clinic in 2 weeks", "Family doctor in 1 week", "Surgical clinic in 10 days", None]),
                responsible_physician_id=adm_md))
        return disc, status

    # patients and their admissions
    for p in persons:
        pid = nid("Patient")
        p["_pid"] = pid
        rec = dict(patient_id=pid, health_insurance_num=p["hin"], full_name=f"{p['first']} {p['last']}",
                   _first=p["first"], _last=p["last"], date_of_birth=p["dob"], gender=p["gender"],
                   address=p["address"], phone_number=p["phone"], emergency_contact_name=p["ec_name"],
                   emergency_contact_number=p["ec_phone"] if p["ec_name"] else None,
                   life_status="Alive", date_of_death=None)
        T["Patient"].append(rec)
        n_adm = p.get("_nadm", wchoice(rng, [0, 1, 2, 3, 4, 5, 6], [3, 47, 22, 14, 8, 4, 2]))
        w0, w1 = p.get("_window", (datetime(2024, 1, 3), datetime(2026, 8, 15)))
        span = (w1 - w0) * max(0.15, 1 - 0.13 * n_adm)
        start = rand_dt(rng, w0, w0 + span)
        start = start.replace(minute=rng.choice([0, 7, 12, 25, 33, 41, 48, 56]), second=0, microsecond=0)
        active_last = "_window" not in p and rng.random() < 0.07
        prev_disc = None
        for k in range(n_adm):
            if k == n_adm - 1 and active_last:
                st = rand_dt(rng, datetime(2026, 10, 15), datetime(2026, 10, 29))
                if prev_disc is None or st > prev_disc + DY(5):
                    make_admission(pid, st, active=True)
                    break
            if start > min(w1 + DY(45), datetime(2026, 10, 10)):
                break
            disc, status = make_admission(pid, start, active=False)
            prev_disc = disc
            if status == "Deceased":
                rec["life_status"] = "Deceased"
                rec["date_of_death"] = disc
                break
            start = disc + DY(rng.uniform(10, 150))
    return T


# ---------------------------------------------------------------------------
# Logical data-quality problems (applied to the canonical records)
# ---------------------------------------------------------------------------
def apply_logical_defects(S, T, rng, log):
    code = S["code"]
    flat = S["fmt"] in ("TXT", "CSV")
    used = set()

    def L(entity, rid, field, dtype, value, note=""):
        log.append(dict(source=code, entity=entity, record_id=rid, field=field, defect_type=dtype,
                        planted_value="" if value is None else (value.v if isinstance(value, Raw) else value),
                        note=note))

    def pick(table, k, cond=None):
        cands = [r for r in T[table] if (table, r[PK[table]]) not in used and (cond is None or cond(r))]
        out = rng.sample(cands, min(k, len(cands)))
        for r in out:
            used.add((table, r[PK[table]]))
        return out

    def k_of(table, rate):
        return max(1, round(len(T[table]) * rate))

    adm = {a["admission_id"]: a for a in T["Admission"]}
    adm_of_pat = {}
    for a in T["Admission"]:
        adm_of_pat.setdefault(a["patient_id"], []).append(a)

    # near-duplicate patients (same person registered twice in the same source)
    next_pid = max(p["patient_id"] for p in T["Patient"]) + 1
    for p in pick("Patient", k_of("Patient", 0.025), lambda r: len(adm_of_pat.get(r["patient_id"], [])) >= 1
                  and r["life_status"] == "Alive"):
        d = copy.deepcopy(p)
        d["patient_id"] = next_pid
        style = rng.choice(["upper", "lower", "spaces"])
        f, l = d["_first"], d["_last"]
        f, l = {"upper": (f.upper(), l.upper()), "lower": (f.lower(), l.lower()), "spaces": (f + " ", " " + l)}[style]
        d["_first"], d["_last"], d["full_name"] = f, l, f"{f} {l}"
        if rng.random() < 0.5:
            d["phone_number"] = None
        T["Patient"].append(d)
        used.add(("Patient", next_pid))
        moved = ""
        ads = adm_of_pat[p["patient_id"]]
        if len(ads) >= 2:
            a = rng.choice(ads[1:])
            a["patient_id"] = next_pid
            for t in ("Diagnosis", "DiagnosticOrder"):
                for r in T[t]:
                    if r["admission_id"] == a["admission_id"]:
                        r["patient_id"] = next_pid
            moved = f"; admission {a['admission_id']} is filed under this duplicate"
        L("Patient", next_pid, "patient_id", "duplicate_entity", next_pid,
          f"same person as patient {p['patient_id']} (same insurance no. and DOB, name written differently){moved}")
        next_pid += 1

    # missing required values
    plan = [("Patient", "date_of_birth", 3), ("Patient", "health_insurance_num", 2),
            ("Admission", "admission_type", 0.006), ("Admission", "admission_datetime", 2),
            ("TriageAssessment", "heart_rate", 0.006), ("TriageAssessment", "priority_level", 0.006),
            ("Diagnosis", "icd9_code", 0.004), ("UnitStay", "entry_datetime", 0.003),
            ("ClinicalNote", "suspected_condition", 0.004), ("RadiologyExamination", "body_area", 0.008),
            ("Healthcare_Professional", "last_name", 1)]
    for table, field, rate in plan:
        k = rate if isinstance(rate, int) else k_of(table, rate)
        for r in pick(table, k, (lambda r: r["patient_id"] < 10**6) if table == "Patient" else None):
            r[field] = None
            L(table, r[PK[table]], field, "missing_required", None, "required (NOT NULL) value missing")

    # invalid numeric values / unit inconsistencies in triage vitals
    oxy_bad = {"A": [140, 0, -5, 101], "B": ["140%", "0%", "-5%"], "C": [140, 0, -5], "D": [1.4, 0.0, -0.95]}
    oxy_unit = {"A": None, "B": None, "C": None, "D": 97}
    temp_bad = {"A": [986.0, 0.0, -98.6], "B": ["3,72", "0,0", "-37,0"], "C": [3.7, 0.0, 373.0], "D": [-1.0, 0.0, 3.71]}
    temp_unit = {"A": (37.2, "Celsius value in Fahrenheit field"), "B": ("98,6", "Fahrenheit value in Celsius field"),
                 "C": (98.6, "Fahrenheit value in Celsius field"), "D": (310.2, "Kelvin value in Celsius field")}
    for i, r in enumerate(pick("TriageAssessment", k_of("TriageAssessment", 0.025))):
        field = "body_temp" if i < 2 else rng.choice(["heart_rate", "oxygen_sat", "pain_level", "body_temp"])
        dtype, note = "invalid_numeric", "value outside valid range or not a number"
        if field == "heart_rate":
            v = rng.choice([-12, 0, 412, 999, "eighty"])
        elif field == "pain_level":
            v = rng.choice([15, -1, 11, "severe"])
        elif field == "oxygen_sat":
            if oxy_unit[code] is not None and rng.random() < 0.5:
                v, dtype, note = oxy_unit[code], "unit_inconsistency", "percent written into a fraction field (should be 0.97)"
            else:
                v = rng.choice(oxy_bad[code])
        else:
            if i < 2 or rng.random() < 0.5:
                v, note = temp_unit[code]
                dtype = "unit_inconsistency"
            else:
                v = rng.choice(temp_bad[code])
        r[field] = Raw(v)
        L("TriageAssessment", r["triage_id"], field, dtype, v, note)

    # broken references
    max_pid = max(p["patient_id"] for p in T["Patient"])
    if flat:
        for r in pick("Admission", k_of("Admission", 0.004)):
            v = max_pid + 5000 + rng.randint(1, 900)
            r["patient_id"] = v
            L("Admission", r["admission_id"], "patient_id", "broken_reference", v, "patient does not exist")
        for r in pick("Diagnosis", k_of("Diagnosis", 0.003)):
            v = len(T["Admission"]) + 7000 + rng.randint(1, 900)
            r["admission_id"] = v
            L("Diagnosis", r["diagnosis_id"], "admission_id", "broken_reference", v, "admission does not exist")
        for r in pick("RadiologyExamination", k_of("RadiologyExamination", 0.006)):
            v = len(T["DiagnosticOrder"]) + 6000 + rng.randint(1, 900)
            r["order_id"] = v
            L("RadiologyExamination", r["exam_id"], "order_id", "broken_reference", v, "diagnostic order does not exist")
        for r in pick("GeneralWardRecord", k_of("GeneralWardRecord", 0.003)):
            v = len(T["Admission"]) + 7000 + rng.randint(1, 900)
            r["admission_id"] = v
            L("GeneralWardRecord", r["ward_record_id"], "admission_id", "broken_reference", v, "admission does not exist")
    for r in pick("Diagnosis", k_of("Diagnosis", 0.006), lambda r: r["icd9_code"] is not None):
        v = rng.choice(["410.7", "999.99", "250.5", "123.45", "V99.9"])
        r["icd9_code"] = v
        L("Diagnosis", r["diagnosis_id"], "icd9_code", "broken_reference", v, "code not in ICD-9 dictionary")
    for r in pick("UnitStay", k_of("UnitStay", 0.003)):
        v = rng.choice([98, 99])
        r["unit_id"] = v
        L("UnitStay", r["unit_stay_id"], "unit_id", "broken_reference", v, "unit does not exist")
    for table, field, rate in [("Admission", "admitting_healthcare_professional", 0.003),
                               ("SurgicalProcedure", "surgeon_id", 0.005),
                               ("Diagnosis", "diagnosing_physician_id", 0.003)]:
        for r in pick(table, k_of(table, rate)):
            v = 500 + rng.randint(1, 400)
            r[field] = v
            L(table, r[PK[table]], field, "broken_reference", v, "healthcare professional does not exist")
    pids = [p["patient_id"] for p in T["Patient"]]
    for table, rate in [("Diagnosis", 0.005), ("DiagnosticOrder", 0.004)]:
        for r in pick(table, k_of(table, rate)):
            real = adm[r["admission_id"]]["patient_id"] if r["admission_id"] in adm else None
            v = rng.choice([p for p in pids if p != real])
            r["patient_id"] = v
            L(table, r[PK[table]], "patient_id", "patient_admission_mismatch", v,
              f"admission {r['admission_id']} belongs to patient {real}")

    # chronologically inconsistent events
    for r in pick("Admission", k_of("Admission", 0.005),
                  lambda r: r["discharge_datetime"] and r["admission_datetime"] and r["admission_status"] == "Discharged"):
        v = rmin(r["admission_datetime"] - H(rng.uniform(2, 72)))
        r["discharge_datetime"] = v
        L("Admission", r["admission_id"], "discharge_datetime", "chronology", v, "discharge before admission")
    for r in pick("UnitStay", k_of("UnitStay", 0.005), lambda r: r["exit_datetime"] and r["entry_datetime"]):
        v = rmin(r["entry_datetime"] - H(rng.uniform(1, 48)))
        r["exit_datetime"] = v
        L("UnitStay", r["unit_stay_id"], "exit_datetime", "chronology", v, "unit exit before unit entry")
    for r in pick("SurgicalProcedure", k_of("SurgicalProcedure", 0.01),
                  lambda r: r["admission_id"] in adm and adm[r["admission_id"]]["discharge_datetime"]):
        v = rmin(adm[r["admission_id"]]["discharge_datetime"] + DY(rng.uniform(1, 5)))
        r["procedure_datetime"] = v
        L("SurgicalProcedure", r["procedure_id"], "procedure_datetime", "chronology", v, "procedure after discharge")
    for r in pick("RadiologyReport", k_of("RadiologyReport", 0.008)):
        ex = next(e for e in T["RadiologyExamination"] if e["exam_id"] == r["rad_exam_id"])
        v = rmin(ex["exam_datetime"] - H(rng.uniform(1, 30)))
        r["report_datetime"] = v
        L("RadiologyReport", r["report_id"], "report_datetime", "chronology", v, "report before the examination")
    for r in pick("Diagnosis", k_of("Diagnosis", 0.003),
                  lambda r: r["admission_id"] in adm and adm[r["admission_id"]]["admission_datetime"]):
        v = rmin(adm[r["admission_id"]]["admission_datetime"] - DY(rng.uniform(1, 10)))
        r["diagnosis_datetime"] = v
        L("Diagnosis", r["diagnosis_id"], "diagnosis_datetime", "chronology", v, "diagnosis before admission")
    orders = {o["order_id"]: o for o in T["DiagnosticOrder"]}
    for r in pick("DiagnosticExamination", k_of("DiagnosticExamination", 0.005)):
        v = rmin(orders[r["order_id"]]["request_datetime"] - H(rng.uniform(1, 20)))
        r["exam_datetime"] = v
        L("DiagnosticExamination", r["diag_exam_id"], "exam_datetime", "chronology", v, "exam performed before it was ordered")
    for r in pick("Patient", 2, lambda r: r["life_status"] == "Deceased" and r["date_of_death"]):
        first = min(a["admission_datetime"] for a in adm_of_pat[r["patient_id"]] if a["admission_datetime"])
        v = rmin(first - DY(rng.uniform(30, 400)))
        r["date_of_death"] = v
        L("Patient", r["patient_id"], "date_of_death", "chronology", v, "death recorded before the patient's admissions")
    for r in pick("Patient", 1, lambda r: r["patient_id"] in adm_of_pat and r["date_of_birth"]):
        first = min(a["admission_datetime"] for a in adm_of_pat[r["patient_id"]] if a["admission_datetime"])
        v = (first + DY(rng.uniform(10, 200))).date()
        r["date_of_birth"] = v
        L("Patient", r["patient_id"], "date_of_birth", "chronology", v, "born after first admission")

    # status / discharge information disagreements
    for r in pick("Admission", k_of("Admission", 0.003), lambda r: r["admission_status"] == "Discharged"):
        L("Admission", r["admission_id"], "discharge_datetime", "status_inconsistency", None,
          "status Discharged but no discharge time")
        r["discharge_datetime"] = None
    for r in pick("Admission", 2, lambda r: r["admission_status"] == "Admitted"):
        v = rmin(r["admission_datetime"] + DY(rng.uniform(1, 3)))
        r["discharge_datetime"] = v
        L("Admission", r["admission_id"], "discharge_datetime", "status_inconsistency", v,
          "status Admitted (still in hospital) but a discharge time is filled in")
    dec = [a for a in T["Admission"] if a["admission_status"] == "Deceased"]
    pat = {p["patient_id"]: p for p in T["Patient"]}
    for a in rng.sample(dec, min(1, len(dec))):
        p = pat[a["patient_id"]]
        if ("Patient", p["patient_id"]) in used:
            continue
        used.add(("Patient", p["patient_id"]))
        p["life_status"], p["date_of_death"] = "Alive", None
        L("Patient", p["patient_id"], "life_status", "status_inconsistency", "Alive",
          f"admission {a['admission_id']} ended with status Deceased")
    dec_ids = {a["admission_id"] for a in dec}
    for r in pick("DischargeRecord", 1, lambda r: r["admission_id"] in dec_ids):
        r["condition_at_discharge"] = "Improved"
        L("DischargeRecord", r["discharge_id"], "condition_at_discharge", "status_inconsistency", "Improved",
          "admission status is Deceased")

    # completed admissions with no primary diagnosis
    done = [a for a in T["Admission"] if a["admission_status"] != "Admitted"
            and ("Admission", a["admission_id"]) not in used]
    for a in rng.sample(done, max(1, round(len(done) * 0.004))):
        for d in T["Diagnosis"]:
            if d["admission_id"] == a["admission_id"] and d["diagnosis_type"] == "Primary":
                d["diagnosis_type"] = "Secondary"
                L("Diagnosis", d["diagnosis_id"], "diagnosis_type", "missing_primary_diagnosis", "Secondary",
                  f"admission {a['admission_id']} is completed but now has no primary diagnosis")


# ---------------------------------------------------------------------------
# Source-specific vocabularies, field names and formats
# ---------------------------------------------------------------------------
CAT = {
    "A": {"admission_type": {"Emergency": "EMERGENCY", "Elective": "ELECTIVE", "Urgent": "URGENT"},
          "admission_source": {"Emergency Department": "ER", "Physician Referral": "REFERRAL",
                               "Transfer from Another Hospital": "TRANSFER IN", "Clinic": "CLINIC"},
          "admission_status": {"Discharged": "DISCHARGED", "Admitted": "INPATIENT", "Deceased": "EXPIRED",
                               "Transferred": "TRANSFERRED OUT"},
          "priority_level": {"High": "HIGH", "Medium": "MEDIUM", "Low": "LOW"},
          "unit_type": {"Emergency": "ED", "MICU": "MICU", "SICU": "SICU", "ICU": "ICU", "CCU": "CCU",
                        "General Ward": "MED/SURG", "Step-Down": "STEPDOWN"},
          "gender": {"Male": "M", "Female": "F", "Other": "X"},
          "life_status": {"Alive": "ALIVE", "Deceased": "DECEASED"},
          "diagnosis_type": {"Primary": "PRIMARY", "Secondary": "SECONDARY"},
          "note_type": {"Admission Note": "ADMIT NOTE", "Progress Note": "PROGRESS", "Discharge Summary": "DC SUMMARY",
                        "Consultation Note": "CONSULT"},
          "staff_type": {"Physician": "MD", "Surgeon": "SURGEON", "Nurse": "RN", "Radiologist": "RADIOLOGIST",
                         "Radiology Technician": "RAD TECH", "Lab Technician": "LAB TECH"},
          "priority": {"STAT": "STAT", "Urgent": "URGENT", "Routine": "ROUTINE"},
          "condition_at_discharge": {"Improved": "IMPROVED", "Stable": "STABLE", "Unchanged": "UNCHANGED",
                                     "Deceased": "EXPIRED"}},
    "B": {"admission_type": {"Emergency": "Emergency", "Elective": "Planned", "Urgent": "Urgent"},
          "admission_source": {"Emergency Department": "A&E", "Physician Referral": "GP Referral",
                               "Transfer from Another Hospital": "Inter-hospital Transfer", "Clinic": "Outpatient Clinic"},
          "admission_status": {"Discharged": "Discharged", "Admitted": "In Hospital", "Deceased": "Died",
                               "Transferred": "Transferred Out"},
          "priority_level": {"High": "P1", "Medium": "P2", "Low": "P3"},
          "unit_type": {"Emergency": "A&E", "MICU": "Medical ICU", "SICU": "Surgical ICU", "ICU": "Intensive Care",
                        "CCU": "Coronary Care", "General Ward": "Ward", "Step-Down": "HDU"},
          "gender": {"Male": "Male", "Female": "Female", "Other": "Other"},
          "life_status": {"Alive": "Living", "Deceased": "Deceased"},
          "diagnosis_type": {"Primary": "Principal", "Secondary": "Additional"},
          "note_type": {"Admission Note": "Admission", "Progress Note": "Daily Review",
                        "Discharge Summary": "Discharge Letter", "Consultation Note": "Consult"},
          "staff_type": {"Physician": "Doctor", "Surgeon": "Surgeon", "Nurse": "Nurse", "Radiologist": "Radiologist",
                         "Radiology Technician": "Radiographer", "Lab Technician": "Biomedical Scientist"},
          "priority": {"STAT": "Immediate", "Urgent": "Urgent", "Routine": "Routine"},
          "condition_at_discharge": {"Improved": "Improved", "Stable": "Stable", "Unchanged": "Unchanged",
                                     "Deceased": "Died"}},
    "C": {"admission_type": {"Emergency": "EMG", "Elective": "ELE", "Urgent": "URG"},
          "admission_source": {"Emergency Department": "ED", "Physician Referral": "REF",
                               "Transfer from Another Hospital": "TRF", "Clinic": "OPD"},
          "admission_status": {"Discharged": "DC", "Admitted": "ACT", "Deceased": "DEC", "Transferred": "TRF"},
          "priority_level": {"High": "1", "Medium": "2", "Low": "3"},
          "unit_type": {"Emergency": "ER", "MICU": "MICU", "SICU": "SICU", "ICU": "ICU", "CCU": "CCU",
                        "General Ward": "GW", "Step-Down": "SDU"},
          "gender": {"Male": "M", "Female": "F", "Other": "O"},
          "life_status": {"Alive": "A", "Deceased": "D"},
          "diagnosis_type": {"Primary": "P", "Secondary": "S"},
          "note_type": {"Admission Note": "ADM", "Progress Note": "PRG", "Discharge Summary": "DCS",
                        "Consultation Note": "CON"},
          "staff_type": {"Physician": "DR", "Surgeon": "SG", "Nurse": "NS", "Radiologist": "RD",
                         "Radiology Technician": "RT", "Lab Technician": "LT"},
          "priority": {"STAT": "S", "Urgent": "U", "Routine": "R"},
          "condition_at_discharge": {"Improved": "IMP", "Stable": "STB", "Unchanged": "UNC", "Deceased": "DEC"}},
    "D": {"admission_type": {"Emergency": "emergency", "Elective": "elective", "Urgent": "urgent"},
          "admission_source": {"Emergency Department": "casualty", "Physician Referral": "referral",
                               "Transfer from Another Hospital": "transfer", "Clinic": "clinic"},
          "admission_status": {"Discharged": "discharged", "Admitted": "admitted", "Deceased": "deceased",
                               "Transferred": "transferred"},
          "priority_level": {"High": "red", "Medium": "yellow", "Low": "green"},
          "unit_type": {"Emergency": "casualty", "MICU": "micu", "SICU": "sicu", "ICU": "icu", "CCU": "ccu",
                        "General Ward": "general_ward", "Step-Down": "high_care"},
          "gender": {"Male": "male", "Female": "female", "Other": "other"},
          "diagnosis_type": {"Primary": "primary", "Secondary": "secondary"},
          "note_type": {"Admission Note": "admission_note", "Progress Note": "progress_note",
                        "Discharge Summary": "discharge_summary", "Consultation Note": "consult_note"},
          "staff_type": {"Physician": "doctor", "Surgeon": "surgeon", "Nurse": "nurse", "Radiologist": "radiologist",
                         "Radiology Technician": "radiographer", "Lab Technician": "lab_technologist"},
          "priority": {"STAT": "stat", "Urgent": "urgent", "Routine": "routine"},
          "condition_at_discharge": {"Improved": "improved", "Stable": "stable", "Unchanged": "unchanged",
                                     "Deceased": "deceased"}},
}
TEXT_CAT_FIELDS = {"admission_type", "admission_source", "admission_status", "priority_level", "unit_type", "gender",
                   "life_status", "diagnosis_type", "note_type", "staff_type", "priority", "condition_at_discharge",
                   "order_status", "exam_status", "discharge_destination", "condition_on_arrival", "exam_type",
                   "body_area", "specialty"}
NAME_FIELDS = {"first_name", "last_name", "emergency_contact_name", "unit_name"}

SYN = {
    "A": {"patient_id": "PatID", "health_insurance_num": "HealthCardNo", "full_name": "PatientName",
          "date_of_birth": "DOB", "gender": "Sex", "phone_number": "Phone", "admission_id": "AdmitID",
          "admission_datetime": "AdmitDT", "discharge_datetime": "DischDT", "admitting_healthcare_professional": "AdmittingMD",
          "staff_id": "StaffID", "icd9_code": "ICD9Code", "unit_id": "UnitID", "triage_id": "TriageID",
          "nurse_id": "NurseID", "body_temp": "TempF", "oxygen_sat": "SpO2Pct", "blood_pressure": "BP",
          "heart_rate": "HR", "pain_level": "PainScore", "priority_level": "TriageLevel", "unit_stay_id": "StayID",
          "entry_datetime": "InDT", "exit_datetime": "OutDT", "life_status": "VitalStatus", "date_of_death": "DeathDT",
          "rad_exam_id": "RadExamID", "diag_exam_id": "LabExamID", "order_id": "OrderID", "exam_id": "RadExamID"},
    "B": {"patient_id": "patient_no", "health_insurance_num": "insurance_number", "full_name": "patient_name",
          "date_of_birth": "birth_date", "gender": "sex", "admission_id": "episode_no", "admission_datetime": "episode_start",
          "discharge_datetime": "episode_end", "admission_type": "episode_type", "admission_status": "episode_status",
          "admission_source": "referral_source", "admitting_healthcare_professional": "admitting_clinician",
          "staff_id": "staff_no", "staff_type": "role", "unit_id": "ward_no", "unit_name": "ward_name",
          "unit_type": "ward_category", "unit_stay_id": "ward_stay_no", "icd9_code": "icd9", "body_temp": "temp_c",
          "oxygen_sat": "spo2", "priority_level": "triage_category", "procedure_id": "operation_no",
          "procedure_type": "operation", "procedure_datetime": "operation_datetime", "surgeon_id": "surgeon_no",
          "entry_datetime": "ward_in", "exit_datetime": "ward_out", "life_status": "vital_status"},
    "C": {"patient_id": "pid", "health_insurance_num": "insuranceNo", "date_of_birth": "birthDate", "gender": "sex",
          "phone_number": "tel", "admission_id": "aid", "admission_datetime": "admitTime",
          "discharge_datetime": "dischargeTime", "admission_type": "admitType", "admission_status": "status",
          "unit_id": "wardCode", "unit_type": "wardCategory", "unit_name": "wardName", "icd9_code": "icdCode",
          "body_temp": "temperatureC", "oxygen_sat": "spo2", "priority_level": "triageLevel",
          "life_status": "vitalStatus", "date_of_death": "deathTime", "staff_id": "staffNo", "staff_type": "role",
          "unit_stay_id": "stayId", "entry_datetime": "inTime", "exit_datetime": "outTime"},
    "D": {"patient_id": "patientRef", "health_insurance_num": "medicalAidNumber", "date_of_birth": "dob",
          "admission_id": "encounterId", "admission_datetime": "admittedAt", "discharge_datetime": "dischargedAt",
          "admission_type": "encounterType", "admission_status": "encounterStatus", "admission_source": "arrivalMode",
          "unit_id": "unitCode", "unit_type": "unitKind", "unit_stay_id": "movementId", "entry_datetime": "inAt",
          "exit_datetime": "outAt", "icd9_code": "icd9", "body_temp": "tempCelsius", "oxygen_sat": "spo2Fraction",
          "priority_level": "triageColour", "life_status": "isDeceased", "date_of_death": "deceasedAt",
          "staff_id": "staffRef", "staff_type": "cadre"},
}


def fname(code, field):
    if field in SYN[code]:
        return SYN[code][field]
    parts = field.split("_")
    if code == "A":
        return "".join(p.capitalize() for p in parts)
    if code == "B":
        return field
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def fmt_dt(code, v):
    if isinstance(v, datetime):
        return {"A": v.strftime("%m/%d/%Y %I:%M %p"), "B": v.strftime("%d/%m/%Y %H:%M"),
                "C": v.strftime("%Y/%m/%d %H:%M:%S"), "D": v.strftime("%Y-%m-%dT%H:%M:%S+02:00")}[code]
    return {"A": v.strftime("%m/%d/%Y"), "B": v.strftime("%d/%m/%Y"), "C": v.strftime("%Y/%m/%d"),
            "D": v.isoformat()}[code]


def bad_date(code, v, rng):
    """Return (bad string, defect type, note) for a date/datetime value."""
    is_dt = isinstance(v, datetime)
    y = v.year
    swapped_amb = v.day <= 12 and v.day != v.month
    if code == "A":
        opt = rng.choice(["invalid", "swap", "iso", "2digit"])
        if opt == "invalid":
            return (f"02/30/{y} 10:15 AM" if is_dt else f"02/30/{y}"), "invalid_date", "day does not exist"
        if opt == "swap":
            s = v.strftime("%d/%m/%Y %I:%M %p" if is_dt else "%d/%m/%Y")
            return (s, "ambiguous_date", "written DD/MM instead of MM/DD (day <= 12, cannot be detected)") if swapped_amb \
                else (s, "invalid_date", "written DD/MM instead of MM/DD (month > 12)")
        if opt == "iso":
            return v.strftime("%Y-%m-%d %H:%M" if is_dt else "%Y-%m-%d"), "date_format_inconsistency", "ISO format in MM/DD/YYYY source"
        return v.strftime("%m/%d/%y %I:%M %p" if is_dt else "%m/%d/%y"), "ambiguous_date", "two-digit year"
    if code == "B":
        opt = rng.choice(["invalid", "swap", "iso", "text"])
        if opt == "invalid":
            return (f"31/02/{y} 08:00" if is_dt else f"31/02/{y}"), "invalid_date", "day does not exist"
        if opt == "swap":
            s = v.strftime("%m/%d/%Y %H:%M" if is_dt else "%m/%d/%Y")
            return (s, "ambiguous_date", "written MM/DD instead of DD/MM (day <= 12, cannot be detected)") if swapped_amb \
                else (s, "invalid_date", "written MM/DD instead of DD/MM (month > 12)")
        if opt == "iso":
            return v.strftime("%Y-%m-%dT%H:%M" if is_dt else "%Y-%m-%d"), "date_format_inconsistency", "ISO format in DD/MM/YYYY source"
        return v.strftime("%d %b %Y %H:%M" if is_dt else "%d %b %Y"), "date_format_inconsistency", "month written as text"
    if code == "C":
        opt = rng.choice(["invalid", "compact", "zero"])
        if opt == "invalid":
            return (f"{y}/02/30 09:00:00" if is_dt else f"{y}/02/30"), "invalid_date", "day does not exist"
        if opt == "compact":
            return v.strftime("%Y%m%d%H%M%S" if is_dt else "%Y%m%d"), "date_format_inconsistency", "compact format without separators"
        return ("0000/00/00 00:00:00" if is_dt else "0000/00/00"), "invalid_date", "placeholder zero date"
    opt = rng.choice(["nooffset", "invalid", "epoch", "utc"]) if is_dt else rng.choice(["invalid", "slash"])
    if opt == "nooffset":
        return v.strftime("%Y-%m-%dT%H:%M:%S"), "ambiguous_date", "timestamp without time-zone offset"
    if opt == "invalid":
        return (f"{y}-02-30T08:00:00+02:00" if is_dt else f"{y}-02-30"), "invalid_date", "day does not exist"
    if opt == "epoch":
        utc = v - H(2)
        return int((utc - datetime(1970, 1, 1)).total_seconds() * 1000), "date_format_inconsistency", "epoch milliseconds (UTC)"
    if opt == "utc":
        return (v - H(2)).strftime("%Y-%m-%dT%H:%M:%SZ"), "date_format_inconsistency", "same instant written in UTC (Z) instead of +02:00"
    return v.strftime("%d/%m/%Y"), "date_format_inconsistency", "DD/MM/YYYY instead of ISO"


def text_variant(rng, s):
    s = str(s)
    opts = [s.lower(), s.upper(), " " + s, s + "  ", s.title(), "  " + s + " "]
    if " " in s.strip():
        opts.append(s.replace(" ", "  "))
    opts = [o for o in opts if o != s]
    return rng.choice(opts)


P_TEXT = 0.025
P_DATE = 0.008
NEST_FK = {"Admission": ["patient_id"], "TriageAssessment": ["admission_id"], "Diagnosis": ["admission_id"],
           "ClinicalNote": ["admission_id"], "SurgicalProcedure": ["admission_id"], "DischargeRecord": ["admission_id"],
           "DiagnosticOrder": ["admission_id"], "UnitStay": ["admission_id"], "GeneralWardRecord": ["admission_id"],
           "DiagnosticExamination": ["order_id"], "RadiologyExamination": ["order_id"],
           "RadiologyReport": ["rad_exam_id"], "CriticalCareRecord": ["unit_stay_id"]}


def render(S, table, rec, rng, log):
    code = S["code"]
    nested = S["fmt"] in ("XML", "JSON")
    rid = rec[PK[table]]
    out = {"__table": table}

    def L(field, dtype, value, note):
        log.append(dict(source=code, entity=table, record_id=rid, field=field, defect_type=dtype,
                        planted_value=value, note=note))

    for f, v in rec.items():
        if f.startswith("_"):
            continue
        if nested and f in NEST_FK.get(table, ()):
            continue
        key = fname(code, f)
        if isinstance(v, Raw):
            out[key] = v.v
            continue
        if table == "Patient" and f == "full_name":
            first, last = rec["_first"], rec["_last"]
            if rng.random() < P_TEXT:
                if rng.random() < 0.5:
                    first = text_variant(rng, first)
                else:
                    last = text_variant(rng, last)
                L("full_name", "text_format", f"{first}|{last}", "capitalization/whitespace changed")
            if code == "A":
                out[key] = f"{last}, {first}"
            elif code == "B":
                out[key] = f"{first} {last}"
            elif code == "C":
                out["name"] = {"family": last, "given": first}
            else:
                out["name"] = {"first": first, "last": last}
            continue
        if v is None:
            out[key] = None
            continue
        if f == "blood_pressure":
            s_, d_ = v
            out[key] = {"A": f"{s_}/{d_}", "B": f"{s_}/{d_} mmHg", "C": {"systolic": s_, "diastolic": d_},
                        "D": {"systolic": s_, "diastolic": d_, "unit": "mmHg"}}[code]
            continue
        if f == "body_temp":
            out[key] = {"A": round(v * 9 / 5 + 32, 1), "B": f"{v:.1f}".replace(".", ","), "C": v, "D": v}[code]
            continue
        if f == "oxygen_sat":
            out[key] = {"A": v, "B": f"{v}%", "C": v, "D": round(v / 100, 2)}[code]
            continue
        if f == "icd9_code":
            val = v
            if code == "A":
                val = v.replace(".", "")
                if table == "Diagnosis" and rng.random() < 0.01:
                    val = v
                    L(f, "icd9_format", val, "dotted code in a source whose dictionary uses undotted codes")
            elif code == "D" and table == "Diagnosis" and v.startswith("0") and rng.random() < 0.35:
                val = v.lstrip("0")
                L(f, "icd9_format", val, f"leading zero lost (should be {v})")
            out[key] = val
            continue
        if f == "life_status" and code == "D":
            out[key] = v == "Deceased"
            continue
        if f in STAFF_FK and code == "D":
            out[key] = f"ST-{v:04d}"
            continue
        if f == "unit_id" and code == "C":
            out[key] = f"W{v:02d}"
            continue
        if isinstance(v, (datetime, date)):
            p = P_DATE if isinstance(v, datetime) else P_DATE / 2
            if rng.random() < p:
                bad, dtype, note = bad_date(code, v, rng)
                out[key] = bad
                L(f, dtype, bad, note)
            else:
                out[key] = fmt_dt(code, v)
            continue
        if f in TEXT_CAT_FIELDS or f in NAME_FIELDS:
            val = v
            if f in CAT[code] and v in CAT[code][f]:
                val = CAT[code][f][v]
            elif f in TEXT_CAT_FIELDS:
                val = {"A": str(v).upper(), "B": v, "C": v, "D": str(v).lower().replace(" ", "_")}[code]
            if rng.random() < P_TEXT:
                nv = text_variant(rng, val)
                L(f, "text_format", nv, "capitalization/whitespace changed")
                val = nv
            out[key] = val
            continue
        out[key] = v
    return out


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------
FILES_A = {"Patient": "PATIENTS.txt", "Healthcare_Professional": "STAFF.txt", "Unit": "UNITS.txt",
           "ICD9_Code": "ICD9_DICT.txt", "Admission": "ADMISSIONS.txt", "TriageAssessment": "TRIAGE.txt",
           "ClinicalNote": "CLINICAL_NOTES.txt", "Diagnosis": "DIAGNOSES.txt", "SurgicalProcedure": "SURGERIES.txt",
           "DischargeRecord": "DISCHARGES.txt", "DiagnosticOrder": "DIAG_ORDERS.txt",
           "RadiologyExamination": "RAD_EXAMS.txt", "RadiologyReport": "RAD_REPORTS.txt",
           "DiagnosticExamination": "LAB_EXAMS.txt", "UnitStay": "UNIT_STAYS.txt",
           "CriticalCareRecord": "ICU_RECORDS.txt", "GeneralWardRecord": "WARD_RECORDS.txt"}
FILES_B = {"Patient": "patients.csv", "Healthcare_Professional": "staff.csv", "Unit": "wards.csv",
           "ICD9_Code": "icd9_codes.csv", "Admission": "episodes.csv", "TriageAssessment": "triage.csv",
           "ClinicalNote": "notes.csv", "Diagnosis": "diagnoses.csv", "SurgicalProcedure": "operations.csv",
           "DischargeRecord": "discharges.csv", "DiagnosticOrder": "orders.csv", "RadiologyExamination": "imaging.csv",
           "RadiologyReport": "imaging_reports.csv", "DiagnosticExamination": "investigations.csv",
           "UnitStay": "ward_stays.csv", "CriticalCareRecord": "critical_care_obs.csv",
           "GeneralWardRecord": "ward_obs.csv"}

CHILDREN = [  # child, parent, fk, C container, C item, D key, one_to_one
    ("RadiologyReport", "RadiologyExamination", "rad_exam_id", "report", None, "report", True),
    ("RadiologyExamination", "DiagnosticOrder", "order_id", "imagingExams", "imaging", "imaging", False),
    ("DiagnosticExamination", "DiagnosticOrder", "order_id", "labExams", "labExam", "labResults", False),
    ("CriticalCareRecord", "UnitStay", "unit_stay_id", "criticalCareRecords", "ccRecord", "criticalCareObservations", False),
    ("TriageAssessment", "Admission", "admission_id", "triageAssessments", "triage", "triage", False),
    ("Diagnosis", "Admission", "admission_id", "diagnoses", "diagnosis", "diagnoses", False),
    ("ClinicalNote", "Admission", "admission_id", "clinicalNotes", "note", "notes", False),
    ("SurgicalProcedure", "Admission", "admission_id", "surgeries", "surgery", "procedures", False),
    ("DiagnosticOrder", "Admission", "admission_id", "orders", "order", "orders", False),
    ("UnitStay", "Admission", "admission_id", "wardStays", "wardStay", "movements", False),
    ("GeneralWardRecord", "Admission", "admission_id", "wardRounds", "wardRound", "wardRounds", False),
    ("DischargeRecord", "Admission", "admission_id", "discharge", None, "discharge", True),
    ("Admission", "Patient", "patient_id", "admissions", "admission", "encounters", False),
]
ITEM_TAG_C = {c[3]: c[4] for c in CHILDREN if c[4]}
ITEM_TAG_C.update({"staffRegistry": "staff", "wardRegistry": "ward", "icd9Dictionary": "icdEntry", "patients": "patient"})


def nest(S, pairs):
    """Attach rendered child records to their parents. Returns top-level dict of lists."""
    code = S["code"]
    for child, parent, fk, ck, _, dk, one in CHILDREN:
        key = ck if code == "C" else dk
        idx = {}
        for canon, r in pairs[parent]:
            idx.setdefault(canon[PK[parent]], r)
        for canon, r in pairs[child]:
            par = idx.get(canon[fk])
            if par is None:
                raise RuntimeError(f"orphan {child} {canon[PK[child]]} in nested source {code}")
            if one:
                par[key] = r
            else:
                par.setdefault(key, []).append(r)
    return pairs


def write_flat(S, rendered, rng, log, outdir):
    code = S["code"]
    files = FILES_A if code == "A" else FILES_B
    counts = {}
    for table in TABLES:
        rows = rendered[table]
        keys = [k for k in rows[0] if k != "__table"]
        path = os.path.join(outdir, files[table])
        lines = []
        for r in rows:
            vals = []
            for k in keys:
                v = r.get(k)
                if v is None:
                    v = ("N/A" if rng.random() < 0.7 else "") if code == "A" else ("" if rng.random() < 0.6 else "NULL")
                vals.append(str(v))
            lines.append(vals)
        counts[table] = len(lines)
        # malformed rows
        if table in ("Admission", "TriageAssessment", "Diagnosis"):
            for kind in ("truncated", "extra_field"):
                i = rng.randrange(len(lines))
                bad = list(lines[i])
                if kind == "truncated":
                    bad = bad[: len(bad) // 2]
                    note = f"row cut off after {len(bad)} of {len(keys)} fields (export interrupted)"
                else:
                    j = len(bad) - 2
                    sep = "|" if code == "A" else ";"
                    bad[j] = bad[j] + f" {sep} see attached"
                    note = f"stray '{sep}' inside a text value gives {len(keys) + 1} fields"
                lines.insert(rng.randrange(1, len(lines)), ("__RAW__", bad, kind))
                counts[table] += 1
                log.append(dict(source=code, entity=table, record_id=bad[0], field="(row)", defect_type="malformed_record",
                                planted_value=kind, note=note + f"; file {files[table]}"))
        if code == "A":
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("|".join(keys) + "\n")
                for ln in lines:
                    if isinstance(ln, tuple):
                        _, bad, kind = ln
                        fh.write("|".join(bad) + "\n")
                    else:
                        fh.write("|".join(ln) + "\n")
        else:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
                w.writerow(keys)
                for ln in lines:
                    if isinstance(ln, tuple):
                        _, bad, kind = ln
                        # write raw (unquoted) so the stray ';' really creates an extra field
                        fh.write(";".join(bad) + "\n")
                    else:
                        w.writerow(ln)
    return counts


def strip_tables(o, rng, code):
    """Remove bookkeeping keys and apply the JSON missing-value markers."""
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if k == "__table":
                continue
            out[k] = strip_tables(v, rng, code)
        return out
    if isinstance(o, list):
        return [strip_tables(x, rng, code) for x in o]
    if o is None:
        r = rng.random()
        return None if r < 0.75 else ("unknown" if r < 0.9 else "")
    return o


def dict_to_el(tag, d, rng):
    table = d.get("__table")
    el = ET.Element(tag)
    pkkey = fname("C", PK[table]) if table else None
    for k, v in d.items():
        if k == "__table":
            continue
        if k == pkkey:
            el.set(k, "" if v is None else str(v))
            continue
        if isinstance(v, list):
            cont = ET.SubElement(el, k)
            for c in v:
                cont.append(dict_to_el(ITEM_TAG_C[k], c, rng))
        elif isinstance(v, dict) and "__table" in v:
            el.append(dict_to_el(k, v, rng))
        elif isinstance(v, dict):
            sub = ET.SubElement(el, k)
            for kk, vv in v.items():
                leaf(sub, kk, vv, rng)
        else:
            leaf(el, k, v, rng)
    return el


def leaf(parent, k, v, rng):
    if v is None:
        if rng.random() < 0.6:
            return            # missing value = element omitted
        v = "-"              # missing value = dash
    ET.SubElement(parent, k).text = str(v)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_all(write=True):
    rng0 = random.Random(SEED)
    people = plan_people(rng0)
    clean, log, counts, xrows = {}, [], {}, []
    if write:
        if os.path.exists(OUT):
            shutil.rmtree(OUT)
        os.makedirs(OUT)
    for S in SOURCES:
        code = S["code"]
        rng = random.Random(SEED + ord(code))
        T = build_source(S, rng, people[code])
        clean[code] = copy.deepcopy(T)
        for p in people[code]:
            if "_x" in p:
                xrows.append(dict(match_group=p["_x"][0], match_type=p["_x"][1], source=code,
                                  continent=S["continent"], local_patient_id=p["_pid"],
                                  name=f"{p['first']} {p['last']}", date_of_birth=p["dob"].isoformat(),
                                  insurance_number=p["hin"]))
        slog = []
        apply_logical_defects(S, T, rng, slog)
        pairs = {t: [(r, render(S, t, r, rng, slog)) for r in T[t]] for t in TABLES}
        # exact duplicates (same record exported twice)
        for table, rate in [("Patient", 0.01), ("Admission", 0.01), ("TriageAssessment", 0.012),
                            ("Diagnosis", 0.012), ("ClinicalNote", 0.008), ("UnitStay", 0.008),
                            ("GeneralWardRecord", 0.008), ("Healthcare_Professional", 0.03), ("ICD9_Code", 0.02)]:
            lst = pairs[table]
            k = max(1, round(len(lst) * rate))
            for i in sorted(rng.sample(range(len(lst)), k), reverse=True):
                canon, r = lst[i]
                dup = {kk: copy.deepcopy(vv) for kk, vv in r.items()}
                lst.insert(rng.randrange(i + 1, len(lst) + 1), (canon, dup))
                slog.append(dict(source=code, entity=table, record_id=canon[PK[table]], field="(record)",
                                 defect_type="duplicate_exact", planted_value="",
                                 note="identical record appears twice" + (" (nested children listed once)" if S["fmt"] in ("XML", "JSON") else "")))
        counts[code] = {t: len(pairs[t]) for t in TABLES}
        outdir = os.path.join(OUT, S["folder"])
        if write:
            os.makedirs(outdir)
        if S["fmt"] in ("TXT", "CSV"):
            rendered = {t: [r for _, r in pairs[t]] for t in TABLES}
            if write:
                counts[code] = write_flat(S, rendered, rng, slog, outdir)
        else:
            nest(S, pairs)
            top = {t: [r for _, r in pairs[t]] for t in ("Healthcare_Professional", "Unit", "ICD9_Code", "Patient")}
            malformed = 0
            if code == "C":
                root = ET.Element("hospitalRecords", {"system": "C", "continent": S["continent"],
                                                      "hospital": S["hospital"], "timezone": "Asia/Tokyo",
                                                      "exported": AS_OF.strftime("%Y/%m/%d %H:%M:%S"),
                                                      "notice": "Entirely fictional data for educational use only"})
                for tag, t in [("staffRegistry", "Healthcare_Professional"), ("wardRegistry", "Unit"),
                               ("icd9Dictionary", "ICD9_Code"), ("patients", "Patient")]:
                    cont = ET.SubElement(root, tag)
                    for r in top[t]:
                        cont.append(dict_to_el(ITEM_TAG_C[tag], r, rng))
                pats = root.find("patients")
                # malformed records
                bad1 = ET.Element("patient", {"pid": ""})
                ET.SubElement(bad1, "insuranceNo").text = "JP00000000"
                bad2 = ET.Element("patient", {"pid": "??"})
                ET.SubElement(ET.SubElement(bad2, "name"), "family").text = "#ERROR"
                bad3 = ET.Element("patient")
                ET.SubElement(bad3, "birthDate").text = "1985/07/14"
                for i, b in enumerate((bad1, bad2, bad3)):
                    pats.insert(rng.randrange(len(pats)), b)
                    slog.append(dict(source=code, entity="Patient", record_id=b.get("pid", "(none)"), field="(element)",
                                     defect_type="malformed_record", planted_value=["empty pid", "non-numeric pid", "no pid attribute"][i],
                                     note="unusable patient element with no valid identifier"))
                some = [a for a in root.iter("admission")]
                ba = rng.choice(some)
                old = ba.get("aid")
                ba.set("aid", "N/A")
                slog.append(dict(source=code, entity="Admission", record_id=old, field="aid", defect_type="malformed_record",
                                 planted_value="N/A", note="admission identifier unreadable"))
                malformed = 3
                ET.indent(root, space="  ")
                if write:
                    ET.ElementTree(root).write(os.path.join(outdir, "sakura_bay_export.xml"), encoding="utf-8",
                                               xml_declaration=True)
            else:
                doc = {"exportInfo": {"system": "D", "continent": S["continent"], "hospital": S["hospital"],
                                      "timezone": "Africa/Johannesburg", "utcOffset": "+02:00",
                                      "exportedAt": AS_OF.strftime("%Y-%m-%dT%H:%M:%S+02:00"),
                                      "notice": "Entirely fictional data for educational use only"},
                       "staff": top["Healthcare_Professional"], "units": top["Unit"],
                       "icd9Dictionary": top["ICD9_Code"], "patients": top["Patient"]}
                doc = strip_tables(doc, rng, code)
                junk = ["### CORRUPTED EXPORT ROW ###", {}, {"patientRef": None, "name": None, "encounters": "see legacy system"}]
                for i, j in enumerate(junk):
                    doc["patients"].insert(rng.randrange(len(doc["patients"])), j)
                    slog.append(dict(source=code, entity="Patient", record_id="(none)", field="(entry)",
                                     defect_type="malformed_record", planted_value=["string instead of object", "empty object", "null identifier, wrong types"][i],
                                     note="unusable entry in patients array"))
                p = rng.choice([p for p in doc["patients"] if isinstance(p, dict) and p.get("encounters")
                                and isinstance(p["encounters"], list)])
                p["encounters"].append("ENCOUNTER_RECORD_TRUNCATED")
                slog.append(dict(source=code, entity="Admission", record_id="(none)", field="(entry)",
                                 defect_type="malformed_record", planted_value="string instead of object",
                                 note=f"inside encounters of patientRef {p['patientRef']}"))
                malformed = 3
                if write:
                    with open(os.path.join(outdir, "highveld_export.json"), "w", encoding="utf-8") as fh:
                        json.dump(doc, fh, ensure_ascii=False, indent=2)
            counts[code]["Patient"] += malformed
            counts[code]["Admission"] += 1
        log.extend(slog)
    return clean, log, counts, xrows


def write_reports(log, counts, xrows):
    with open(os.path.join(OUT, "defects_log.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["source", "entity", "record_id", "field", "defect_type", "planted_value", "note"])
        w.writeheader()
        for r in log:
            w.writerow(r)
    summ = {}
    for r in log:
        summ.setdefault((r["source"], r["defect_type"]), 0)
        summ[(r["source"], r["defect_type"])] += 1
    types = sorted({t for _, t in summ})
    with open(os.path.join(OUT, "defects_summary.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["defect_type"] + [s["code"] for s in SOURCES] + ["total"])
        for t in types:
            row = [summ.get((s["code"], t), 0) for s in SOURCES]
            w.writerow([t] + row + [sum(row)])
    with open(os.path.join(OUT, "record_counts.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["entity"] + [f"{s['code']} ({s['continent']}, {s['fmt']})" for s in SOURCES])
        for t in TABLES:
            w.writerow([t] + [counts[s["code"]][t] for s in SOURCES])
        w.writerow(["TOTAL"] + [sum(counts[s["code"]].values()) for s in SOURCES])
    with open(os.path.join(OUT, "cross_source_answer_key.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(xrows[0].keys()))
        w.writeheader()
        for r in sorted(xrows, key=lambda r: (r["match_group"], r["source"])):
            w.writerow(r)


if __name__ == "__main__":
    clean, log, counts, xrows = build_all(write=True)
    write_reports(log, counts, xrows)
    for s in SOURCES:
        print(s["code"], s["continent"], s["fmt"], "total records:", sum(counts[s["code"]].values()))
    print("planted problems:", len(log))
