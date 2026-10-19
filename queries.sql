-- Q1 Retrieves the names and admission dates of patients admitted for emergencies who received a high-priority triage classification.
SELECT p.full_name, a.admission_datetime 
FROM Patient p
JOIN Admission a ON a.patient_id= p.patient_id
JOIN TriageAssessment ta ON ta.admission_id= a.admission_id
WHERE ta.priority_level = 'High' AND a.admission_type= 'Emergency';

-- Q2 display patients identifier, name and total number of admissions who have been admitted more than 3 times.
SELECT p.patient_id, p.full_name, COUNT(a.admission_id) AS total_admissions
FROM Patient p
JOIN Admission a ON a.patient_id= p.patient_id
GROUP BY patient_id
HAVING COUNT(admission_id) > 3;

-- Q3 display the names, admission dates and discharge dates of patients who were discharged without undergoing any surgical procedure during the admission.
SELECt p.full_name, a.admission_datetime, a.discharge_datetime
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
--Q7 ESM
--Q8 ESM
--Q9 ESM
--Q10 ESM
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

--Q11 ESM
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

--Q12 ESM
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

--Q13 ESM
/*
I reverse engineered it to exclude the patients to have been in the ICU or CCU units and then add the not exist key operator to them. 
the path is admission->unitstay->unit to get the admission id and the unit type.
Then use the same method but have had a radiology examination. we get the admissions that have at least 1 radiology examination and 
then we exclude the admissions that have been in the ICU or CCU units.
*/
SELECT a.admission_id
FROM Admission a
WHERE EXISTS (SELECT 1 
			FROM RadiologyExamination r 
			WHERE r.admission_id = a.admission_id) 
AND 
( NOT EXISTS (SELECT 1
			FROM UnitStay us
			JOIN Unit u ON us.unit_id = u.unit_id
        	WHERE us.admission_id= a.admission_id AND u.unit_type IN ('CCU', 'ICU')
      ));

--Q14 ESM
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
AND julianday(a.discharge_datetime) - julianday(a.admission_datetime) =(SELECT MAX(julianday(a.discharge_datetime) - julianday(a.admission_datetime))
	FROM Admission
	WHERE discharge_datetime IS NOT NULL);

--Q15 ESM


--Q16 ESM

--Q17 ESM

--Q18 ESM

--Q19 ESM

--Q20 ESM
