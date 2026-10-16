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


