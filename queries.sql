-- Q1 
/*
    We need to display the name and admission dates of patients who were admitted for 
    emergencies and received a high-priority triage classification. To do this, we join 
    the Patient, Admission and TriageAssessment tables since getting the patient name 
    comes from the Patient table and the admissions datetime comes from the admission 
    table. We join the TriageAssessment table to the Admission table because we can filter
    the results based on the priority levle of the triage and as an Emergency type of 
    admission. 
*/
SELECT p.full_name, a.admission_datetime 
FROM Patient p
JOIN Admission a ON a.patient_id= p.patient_id
JOIN TriageAssessment ta ON ta.admission_id= a.admission_id
WHERE ta.priority_level = 'High' AND a.admission_type= 'Emergency';

-- Q2 
/*
    We need to display the patients identifier and name, which commes from the Patient 
    table,and the total number of admissions who have been admitted more than 3 times,
    which comes from the Admission table. To do this we join the Patient and Admission tables
*/
SELECT p.patient_id, p.full_name, COUNT(a.admission_id) AS total_admissions
FROM Patient p
JOIN Admission a ON a.patient_id= p.patient_id
GROUP BY p.patient_id
HAVING COUNT(a.admission_id) > 3;

-- Q3 
/*
    We need to display the names, which comes from the Patient table, and the admission 
    dates and discharges dates, which comes from the Admission table, of patients who were
    discharged without undergoing any surgical procedure during the admission. To do this
    we join the Patient and Admission tables and then left join the SurgicalProcedure 
    table to the Admission table so that we can filter out any admissions that had a 
    surgical procedure. We also filter for only those admissions that have a discharge
    status of 'Discharged'.
*/
SELECT p.full_name, a.admission_datetime, a.discharge_datetime
FROM Patient p
JOIN Admission a ON a.patient_id= p.patient_id
LEFT JOIN SurgicalProcedure sp ON sp.admission_id= a.admission_id
WHERE sp.procedure_id IS NULL AND a.admission_status= 'Discharged';


--Q4 ESM
/*
  	Question is asking for both surgical procedure and radiology in the same admission, to get the 
	by joining the admission table to the patient table we are then able to link the surgery and radiology
	to the admission id and there is no need for a where function because the joining of the tables is the 
	constraint.
*/
select distinct(full_name) from Patient
join Admission on Admission.patient_id = Patient.patient_id
join RadiologyExamination on Admission.admission_id = RadiologyExamination.admission_id
join SurgicalProcedure on Admission.admission_id = SurgicalProcedure.admission_id;

-- Q5 ESM
/*
	Most of the info we need to display comes from the unitstay table so we join the Admission, 
	Patient and Unit tables since we also need the full name the admission id and the ICU or CCU 
	type, then we restrict based on ICU or CCU and we subtract the exit time by  the entry time
	and see if its larger than 7 days 
*/
select Patient.full_name, Unit.unit_type, UnitStay.entry_datetime, UnitStay.exit_datetime, (julianday(UnitStay.exit_datetime) - julianday(UnitStay.entry_datetime)) as length_in_ccu_or_icu
from UnitStay
join Admission on Admission.admission_id = UnitStay.admission_id
join Patient on Admission.patient_id = Patient.patient_id
join Unit on UnitStay.unit_id = Unit.unit_id
where (Unit.unit_type = 'CCU' or Unit.unit_type = 'ICU') 
	and (julianday(UnitStay.exit_datetime) - julianday(UnitStay.entry_datetime)) > 7;
--Q6 ESM
/*
	we need to display the patient names from the patient table and count 
	how many admissions each patient had, using left or right join depending on the 
	table would keep the patient ids with 0 admissions. Each patient name 
	needs to be displayed with their individual count using the group by function
*/
select Patient.full_name, count(Admission.patient_id) from Patient
left join Admission on Admission.patient_id = Patient.patient_id
group by Patient.patient_id; 

--Q7
/*
    During one same admission, get the names of patients who entered through
    the Emergency Department and got transferred to either the ICU or CCU
 */
SELECT DISTINCT Patient.full_name
FROM Patient
INNER JOIN Admission
ON Patient.patient_id = Admission.patient_id
INNER JOIN UnitStay
ON Admission.admission_id = UnitStay.admission_id
INNER JOIN Unit
ON UnitStay.unit_id = Unit.unit_id
WHERE Admission.admission_source = 'Emergency Department' AND (Unit.unit_type = 'ICU' OR Unit.unit_type = 'CCU');

--Q8
/*
    Out of all admissions that included at least one stay at either the ICU
    or CCU, get the most assigned primary diagnosis and show its ICD-9 code,
    official description(aka: title), and number of times it was assigned
 */
SELECT ICD9_Code.icd9_code, ICD9_Code.official_title, COUNT(DISTINCT Diagnosis.diagnosis_id)
FROM ICD9_Code
INNER JOIN Diagnosis
ON ICD9_Code.icd9_code = Diagnosis.icd9_code
INNER JOIN UnitStay
ON Diagnosis.admission_id = UnitStay.admission_id
INNER JOIN Unit
ON UnitStay.unit_id = Unit.unit_id
WHERE Diagnosis.diagnosis_type = 'Primary' AND (Unit.unit_type = 'ICU' OR Unit.unit_type = 'CCU')
GROUP BY ICD9_Code.icd9_code, ICD9_Code.official_title
ORDER BY COUNT(DISTINCT Diagnosis.diagnosis_id) DESC
LIMIT 1;

--Q9
/*
    For each critical care unit type (MICU, SICU, ICU, CCU), compute
    the average length of stay and display the unit type with its average
 */
SELECT Unit.unit_type, AVG(julianday(UnitStay.exit_datetime) - julianday(UnitStay.entry_datetime))
FROM Unit
INNER JOIN UnitStay
ON Unit.unit_id = UnitStay.unit_id
WHERE Unit.unit_type = 'MICU' OR Unit.unit_type = 'SICU' OR Unit.unit_type = 'ICU' OR Unit.unit_type = 'CCU'
GROUP BY Unit.unit_type;

--Q10 
/*
We are joining Patient and Admission with patient id to get the full name of the patient, 
then we join the Admission, SurgicalProcedure table and UnitStay table  with admission_id
to get the procedure date and time and the entry date and time, respectively.
Finally we join the unit table and unit stay table with unit
_id to get the unit type for the conditional statement. The where clause filters the results 
for unit_type (ICU or CCU) and 
had a surgical procedure before their entry into the unit.
*/
SELECT p.full_name, s.procedure_datetime, u.unit_type, us.entry_datetime
FROM Patient p
JOIN Admission a ON p.patient_id = a.patient_id
JOIN SurgicalProcedure s ON a.admission_id = s.admission_id
JOIN UnitStay us ON a.admission_id = us.admission_id
JOIN Unit u ON u.unit_id = us.unit_id
WHERE u.unit_type IN ('ICU', 'CCU') AND s.procedure_datetime < us.entry_datetime;

--Q11 
/*
I looked at the path through which we can link a patient name and the radiology exam count accross admissions. 
We have the patient id as common rows in the admission and patient tables, whereas we have the admission_id 
between the admission and radiology examination tables. so the path is patient -> admission -> radiology examination. 
We can use a left join to get all the patients and their corresponding admissions and radiology exams. 
Then we can group by patient name and admission id to 
get the count(r.exam_id) of radiology exams for each patient across all admissions without counting NULL values. 
*/
SELECT p.full_name, 
COUNT(r.exam_id) as num_radiology_exams
FROM Patient p
LEFT JOIN Admission a ON p.patient_id = a.patient_id
LEFT JOIN RadiologyExamination r ON a.admission_id = r.admission_id
GROUP BY p.patient_id, p.full_name
ORDER BY num_radiology_exams DESC;

--Q12 
/*
Here we go through the patient->admission->clinical note path to get the patient name and the clinical note.
We then filter the clinical notes to only include those of type 'Discharge Summary' and 
we lower the note text to make the search case-insensitive and then use the LIKE operator
to filter for recovery.
We add the Distinct keyword to not have duplicates.
*/
SELECT DISTINCT p.full_name
FROM Patient p
JOIN Admission a ON p.patient_id = a.patient_id
JOIN ClinicalNote c ON a.admission_id = c.admission_id
WHERE c.note_type = 'Discharge Summary' AND LOWER(c.note_text) LIKE '%recovery%';

--Q13 
/*
I reverse engineered it to exclude the patients to have been in the ICU or CCU units and then add the not exist key operator to them. 
the path is admission->unitstay->unit to get the admission id and the unit type.
Then use the same method but have had a radiology examination. we get the admissions that have at least 1 radiology examination and 
then we exclude the admissions that have been in the ICU or CCU units.
*/
SELECT a.admission_id
FROM Admission a
WHERE EXISTS (
    SELECT 1 
    FROM RadiologyExamination r 
    WHERE r.admission_id = a.admission_id
) 
AND NOT EXISTS (
    SELECT 1
    FROM UnitStay us
    JOIN Unit u ON us.unit_id = u.unit_id
    WHERE us.admission_id = a.admission_id AND u.unit_type IN ('CCU', 'ICU')
);

--Q14 
/*
The discharge and admission times are in the admission table 
so we just need to substract them to find the length of the stay and 
then we just need to match the patient's name and admission id through 
the patient id, and lastly we verify the longest by checking that 
they have indeed been discharged and we compare the length of stay 
with a subquery containing the max length of stay to showcase all equally longest stays.
*/
SELECT p.full_name, a.admission_id, julianday(a.discharge_datetime) - julianday(a.admission_datetime) as length_of_stay
FROM Patient p
JOIN Admission a ON p.patient_id = a.patient_id
WHERE a.discharge_datetime IS NOT NULL
AND julianday(a.discharge_datetime) - julianday(a.admission_datetime) = (
    SELECT MAX(julianday(a2.discharge_datetime) - julianday(a2.admission_datetime))
    FROM Admission a2
    WHERE a2.discharge_datetime IS NOT NULL
);

-- Q15
/*
Start from Patient and LEFT JOIN Admission and UnitStay so every patient is
listed (patients with no unit stays get 0). Per admission, transfers = stays - 1,
so per patient, transfers = total stays - number of admissions that have stays.
GROUP BY patient, COUNT(unit_stay_id) counts all stays, COUNT(DISTINCT us.admission_id) 
counts admissions with stays (COUNT skips NULLs, giving 0 - 0 = 0).
*/

SELECT a.patient_id, 
	COUNT(us.unit_stay_id) - COUNT(DISTINCT us.admission_id) AS transfers
FROM Admission a
INNER JOIN UnitStay us ON us.admission_id = a.admission_id
GROUP BY a.patient_id;

-- Q16
/*
Join Admission to UnitStay and Unit (unit type), keep only critical care
units (ICU, CCU, MICU, SICU), group by admission so types are compared within the
same admission, HAVING keeps admissions with more than one distinct unit type,
DISTINCT lists each qualifying patient once.
*/

SELECT DISTINCT a.patient_id
FROM Admission a
INNER JOIN UnitStay us ON us.admission_id = a.admission_id
INNER JOIN Unit u on u.unit_id = us.unit_id
WHERE u.unit_type IN ('ICU', 'CCU', 'MICU', 'SICU')
GROUP BY a.admission_id, a.patient_id
HAVING COUNT(DISTINCT u.unit_type) > 1;

-- Q17
/*
Join Admission to Patient (name) and to Diagnosis ON admission_id, so each
diagnosis stays with its own admission, group by admission, HAVING keeps admissions
with more than one distinct ICD-9 code, COUNT(DISTINCT) ignores repeated diagnoses
of the same code.
*/

SELECT p.full_name, a.admission_id, COUNT(Distinct d.icd9_code) AS num_idc9_codes
FROM Admission a
INNER JOIN Patient p ON p.patient_id = a.patient_id
INNER JOIN Diagnosis d ON d.admission_id = a.admission_id
GROUP BY p.full_name, a.admission_id
HAVING COUNT(DISTINCT d.icd9_code) > 1;

-- Q18
/*
Join ClinicalNote to Admission and Patient (notes link to patients through
their admission). A correlated subquery finds, for the current row's patient, the
latest note_datetime across all of that patient's admissions, the WHERE keeps only
the note whose datetime equals that maximum.
*/

SELECT p.full_name, cn.note_type, cn.note_datetime, cn.note_text
FROM ClinicalNote cn 
INNER JOIN Admission a ON a.admission_id = cn.admission_id
INNER JOIN Patient p ON p.patient_id = a.patient_id
WHERE cn.note_datetime = (
	SELECT MAX(cn2.note_datetime)
	FROM ClinicalNote cn2
	INNER JOIN Admission a2 ON a2.admission_id = cn2.admission_id
	WHERE a2.patient_id = a.patient_id
);

-- Q19
/*
Start from Admission and join Patient (name, date of death). LEFT JOIN
DischargeRecord so admissions without a discharge record are kept (they can still
match on admission_status). LEFT JOIN Diagnosis on the same admission, with the
'Primary' filter in ON so admissions without a primary diagnosis are not dropped,
LEFT JOIN ICD9_Code for the diagnosis title. WHERE keeps admissions whose status OR
discharge condition is 'Deceased'.
*/

SELECT p.full_name, a.admission_datetime, p.date_of_death, d.icd9_code, i.official_title
FROM Admission a 
INNER JOIN Patient p ON p.patient_id = a.patient_id
LEFT JOIN DischargeRecord dr ON dr.admission_id = a.admission_id
LEFT JOIN Diagnosis d ON d.admission_id = a.admission_id AND d.diagnosis_type = 'Primary'
LEFT JOIN ICD9_Code i ON i.icd9_code = d.icd9_code
WHERE (a.admission_status = 'Deceased' OR dr.condition_at_discharge = 'Deceased');

-- Q20
/*
From Admission, join Patient (name), and join both SurgicalProcedure and
RadiologyExamination on the same admission_id (same admission). This pairs every
procedure with every exam of that admission, WHERE keeps only pairs whose DATE()
parts match.
*/

SELECT p.full_name, a.admission_id, sp.procedure_type, re.exam_type, DATE(sp.procedure_datetime) AS common_date
FROM Admission a
INNER JOIN Patient p ON p.patient_id = a.patient_id
INNER JOIN SurgicalProcedure sp ON sp.admission_id = a.admission_id
INNER JOIN RadiologyExamination re ON re.admission_id = a.admission_id
WHERE DATE(sp.procedure_datetime) = DATE(re.exam_datetime);
