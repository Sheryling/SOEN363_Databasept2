# SOEN 363 Phase 2: Synthetic Source Data (generation notes)

> **All data in this folder is entirely fictional.** It was created only for educational and learning purposes. It doesn't describe real patients or include any real personal information. Hospitals, names, addresses, phone numbers and insurance numbers are all invented.

## AI disclosure facts (for your report)

- **Tool:** Claude (Anthropic), model Claude Opus 5.5, used through claude.ai.
- **Scope:** only the synthetic source datasets were generated (handout §2). The generator script (`generate_sources.py`) is part of the generated data, so include it in your disclosure.
- **Prompt:** see the prompt you sent in the chat (it includes the required "entirely fictional … educational and learning purposes … no real patients" statement).
- **Reproducible:** `python3 generate_sources.py` rebuilds the same files every time (fixed seed `3632026`).
- **Still your job:** review the data (see the checklist at the end) and write all loading, cleaning, integration, SQL and report work yourselves.

## The four sources

| | A | B | C | D |
|---|---|---|---|---|
| Continent | North America | Europe | Asia | Africa |
| Hospital (fictional) | Lakeshore General Hospital | St. Aurelia University Hospital | Sakura Bay Medical Center | Highveld Regional Hospital |
| Format | TXT, 17 files | CSV, 17 files | XML, 1 nested file | JSON, 1 nested file |
| Layout | pipe-delimited, header row, one file per entity | `;`-delimited, header row, `"` quoting, UTF-8 | patients → admissions → children | patients → encounters → children |
| Date/time format | `MM/DD/YYYY hh:mm AM` | `DD/MM/YYYY HH:MM` | `YYYY/MM/DD HH:MM:SS` | ISO 8601 with offset `+02:00` |
| Time zone | America/Toronto local (no offset stored; observes DST) | Europe/Paris local (no offset stored; observes DST) | Asia/Tokyo local, UTC+9 (no offset stored) | Africa/Johannesburg, UTC+2 (offset stored) |
| Missing values | `N/A` or empty | empty or `NULL` | element omitted or `-` | `null`, `"unknown"` or `""` |
| Patient name | `Last, First` | `First Last` | `<name><family/><given/></name>` | `"name": {"first", "last"}` |
| Blood pressure | `120/80` | `120/80 mmHg` | `<systolic>`/`<diastolic>` | `{"systolic", "diastolic", "unit"}` |
| Temperature | °F (`TempF`) | °C with a decimal comma (`37,4`) | °C | °C |
| SpO2 | percent (int) | `"97%"` | percent (int) | fraction (`0.97`) |
| ICD-9 code | no decimal point (`0389`, `41071`) | dotted (`038.9`) | dotted | dotted |
| ID formats | integers | integers | integers; unit codes `W01`–`W12` | integers; staff refs `ST-0001` |
| Insurance no. | `##########-AB` | `EU-###-###-####` | `JP########` | `MA#########` (medical aid) |

In C and D, the parent's ID is implied by nesting, so child records omit it. Three redundant links are kept so you can check consistency: `Diagnosis.patient_id`, `DiagnosticOrder.patient_id` and `RadiologyExamination.admission_id`.

**Cleaning targets.** The values your Phase 1 queries expect are the canonical labels each source's label maps to:

| Field (Phase 1 value) | A | B | C | D |
|---|---|---|---|---|
| admission_type: Emergency / Elective / Urgent | EMERGENCY / ELECTIVE / URGENT | Emergency / Planned / Urgent | EMG / ELE / URG | emergency / elective / urgent |
| admission_source: Emergency Department / Physician Referral / Transfer from Another Hospital / Clinic | ER / REFERRAL / TRANSFER IN / CLINIC | A&E / GP Referral / Inter-hospital Transfer / Outpatient Clinic | ED / REF / TRF / OPD | casualty / referral / transfer / clinic |
| admission_status: Discharged / Admitted / Deceased / Transferred | DISCHARGED / INPATIENT / EXPIRED / TRANSFERRED OUT | Discharged / In Hospital / Died / Transferred Out | DC / ACT / DEC / TRF | discharged / admitted / deceased / transferred |
| priority_level: High / Medium / Low | HIGH / MEDIUM / LOW | P1 / P2 / P3 | 1 / 2 / 3 | red / yellow / green |
| unit_type: Emergency / ICU / CCU / MICU / SICU / General Ward / Step-Down | ED / ICU / CCU / MICU / SICU / MED/SURG / STEPDOWN | A&E / Intensive Care / Coronary Care / Medical ICU / Surgical ICU / Ward / HDU | ER / ICU / CCU / MICU / SICU / GW / SDU | casualty / icu / ccu / micu / sicu / general_ward / high_care |
| diagnosis_type: Primary / Secondary | PRIMARY / SECONDARY | Principal / Additional | P / S | primary / secondary |
| note_type: Admission Note / Progress Note / Discharge Summary / Consultation Note | ADMIT NOTE / PROGRESS / DC SUMMARY / CONSULT | Admission / Daily Review / Discharge Letter / Consult | ADM / PRG / DCS / CON | admission_note / progress_note / discharge_summary / consult_note |
| condition_at_discharge: Improved / Stable / Unchanged / Deceased | IMPROVED / … / EXPIRED | … / Died | IMP / STB / UNC / DEC | improved / … / deceased |
| life_status: Alive / Deceased | ALIVE / DECEASED | Living / Deceased | A / D | `isDeceased` true/false |
| gender: Male / Female / Other | M / F / X | Male / Female / Other | M / F / O | male / female / other |
| staff_type: Physician / Surgeon / Nurse / Radiologist / Radiology Technician / Lab Technician | MD / SURGEON / RN / RADIOLOGIST / RAD TECH / LAB TECH | Doctor / Surgeon / Nurse / Radiologist / Radiographer / Biomedical Scientist | DR / SG / NS / RD / RT / LT | doctor / surgeon / nurse / radiologist / radiographer / lab_technologist |

## Record counts (as written to the files)

Your own Task 1 profiling code must produce these counts. Use this table only to cross-check.

| Entity | A | B | C | D |
|---|---|---|---|---|
| Healthcare_Professional | 72 | 72 | 72 | 72 |
| Unit | 12 | 12 | 12 | 12 |
| ICD9_Code | 62 | 62 | 62 | 62 |
| Patient | 254 | 259 | 251 | 267 |
| Admission | 469 | 476 | 455 | 492 |
| TriageAssessment | 363 | 365 | 358 | 376 |
| Diagnosis | 1,000 | 1,018 | 974 | 1,057 |
| ClinicalNote | 1,951 | 1,977 | 1,842 | 2,024 |
| SurgicalProcedure | 127 | 110 | 120 | 128 |
| DischargeRecord | 453 | 459 | 434 | 463 |
| DiagnosticOrder | 806 | 802 | 818 | 854 |
| DiagnosticExamination | 433 | 432 | 445 | 451 |
| RadiologyExamination | 332 | 332 | 327 | 358 |
| RadiologyReport | 332 | 332 | 327 | 358 |
| UnitStay | 981 | 996 | 923 | 971 |
| CriticalCareRecord | 449 | 471 | 383 | 388 |
| GeneralWardRecord | 890 | 899 | 853 | 951 |
| **Total** | **8,986** | **9,074** | **8,656** | **9,284** |

That's 36,000 raw records in total (the handout requires 20,000–40,000). The counts include planted duplicates and malformed records.

## Planted data-quality problems

Every planted problem is listed one per row in `defects_log.csv` (source, entity, record ID, field, type, planted value, note). That file is the **answer key**: use it to check that your cleaning catches everything. Don't load it into the database.

| Problem type | A | B | C | D | What it looks like |
|---|---|---|---|---|---|
| duplicate_exact | 57 | 58 | 54 | 60 | Same record exported twice (in C/D, nested children are listed only once) |
| duplicate_entity | 6 | 6 | 6 | 6 | Same patient registered twice: same insurance no. + DOB, name in different case/spacing; sometimes one admission is filed under the copy |
| missing_required | 33 | 33 | 32 | 33 | NOT NULL value missing (DOB, insurance no., admission type/time, triage vitals, ICD-9 code, unit entry time, …) |
| text_format | 244 | 268 | 268 | 276 | Extra spaces or wrong capitalization in categories and names |
| invalid_date | 19 | 28 | 51 | 19 | Impossible dates (Feb 30, month 13+, `0000/00/00`) |
| ambiguous_date | 31 | 4 | 0 | 24 | Day/month swapped where the day is ≤ 12, two-digit years, D timestamps with no offset |
| date_format_inconsistency | 18 | 44 | 20 | 49 | A valid date in the wrong format (ISO in A/B, text month in B, compact in C, epoch ms or UTC `Z` in D) |
| invalid_numeric | 7 | 6 | 7 | 5 | Heart rate −12/412/"eighty", pain 15, SpO2 140, … |
| unit_inconsistency | 2 | 3 | 2 | 4 | °C in a °F field, °F in a °C field, Kelvin, SpO2 percent in a fraction field |
| broken_reference | 24 | 24 | 14 | 14 | Unknown patient/admission/order (A, B only), unknown ICD-9 code, unit or staff member |
| patient_admission_mismatch | 8 | 8 | 8 | 8 | `Diagnosis`/`DiagnosticOrder` patient differs from its admission's patient |
| chronology | 19 | 19 | 19 | 19 | Discharge before admission, unit exit before entry, surgery after discharge, report before exam, diagnosis before admission, lab exam before its order, death before admission, birth after admission |
| status_inconsistency | 5 | 5 | 5 | 5 | Discharged with no discharge time, still admitted but has a discharge time, deceased admission but patient "alive", discharge condition "Improved" for a death |
| missing_primary_diagnosis | 2 | 2 | 2 | 2 | Completed admission with no primary diagnosis |
| icd9_format | 11 | 0 | 0 | 11 | A: dotted code in an undotted source; D: leading zero lost (`38.9` for `038.9`) |
| malformed_record | 6 | 6 | 4 | 4 | A/B: truncated rows and rows with an extra delimiter; C: patient elements with an empty, non-numeric or missing `pid`; D: non-object entries |

That's 2,037 planted problems in about 36,000 records, so the large majority of records stay usable. Some optional fields (phone, address, bed number, outcome, …) are naturally empty and aren't counted as defects.

**Repeated local IDs across sources.** Every source numbers its own records from 1, so patient 1, admission 1, staff 1 and so on exist in all four sources and are different entities. This is deliberate, and it's what your identifier-mapping work has to solve.

**Cross-source people** (`cross_source_answer_key.csv`):
- **certain_match** (24 groups): same person in two sources, with the same international insurance no. (`INTL-…`), name and DOB. Their admissions don't overlap in time.
- **uncertain_match** (4 groups): same name and DOB but different insurance numbers. Keep these as uncertain and don't merge them automatically.
- **different_person_same_name** (12 groups): same name, but a different DOB and insurance no. Don't merge these.

## What was checked before delivery

- Each source has 5,000–10,000 records; all files open (TXT/CSV with a standard reader, apart from the planted malformed rows; XML and JSON parse).
- Before the problems were planted, the clean data loaded into your Phase 1 schema with **0 foreign-key violations and 0 chronology or status errors**, and **all 20 Phase 1 queries returned rows** in every source. After you clean the data, your results should be close to that.

## Review checklist for your team

1. **ICD-9 dictionary.** Check each of the 62 codes and titles against the official CMS ICD-9-CM (version 32) code list. The handout requires you to verify AI-generated dictionary entries.
2. Spot-check 10–20 records per source for realism (vital signs vs. triage level, unit flow, dates).
3. Confirm that nothing looks like a real person (names are random first/last combinations; phone numbers use fictional ranges).
4. Make your profiling counts match the record-count table above, and make sure your cleaning catches the problems in `defects_log.csv`.
5. Keep the source files unchanged; the handout requires the originals to be preserved.
