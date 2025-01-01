# Copyright (c) 2024, Sowaan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ReconciliationReport(Document):
	def before_save(self):

		doc = self
		start_date = doc.start_date
		end_date = doc.end_date
		total_month_days = 30
		employee_id = doc.employee
		
		employee_filter=""
		employee1_filter=""
		if doc.employee:
			employee_filter = "AND e.name = %(employee_id)s"
			employee1_filter = "AND ss.employee = %(employee_id)s"


		#for Joiners Table
		joiners_employees = frappe.db.sql(f"""
				SELECT 
					e.name,
					e.employee_name,e.date_of_joining,e.relieving_date,e.designation,ssa.base AS base_salary
				FROM 
					`tabEmployee` e
				LEFT JOIN (
					SELECT 
						employee, base, MAX(from_date) AS latest_from_date
					FROM 
						`tabSalary Structure Assignment`
					GROUP BY 
						employee
				) ssa
				ON e.name = ssa.employee
				WHERE 
					e.date_of_joining BETWEEN %(start_date)s AND %(end_date)s
					AND (
						e.relieving_date IS NULL OR 
						NOT (e.relieving_date BETWEEN %(start_date)s AND %(end_date)s)
					)
					AND EXISTS (
						SELECT 1 
						FROM `tabSalary Slip` ss 
						WHERE ss.employee = e.name
					)
					{employee_filter}
			""", {"start_date": start_date, "end_date": end_date ,  "employee_id": employee_id}, as_dict=True )
		
		doc.table_qase = []
		for employee in joiners_employees:
			
			base_salary = employee["base_salary"] if employee["base_salary"] else 0
			days_diff = frappe.utils.date_diff(end_date, employee["date_of_joining"]) + 1
			paid_salary = ( (base_salary / total_month_days) * days_diff)
			doc.append("table_qase", {
				"employee_id": employee["name"],"employee_name": employee["employee_name"],"designation": employee["designation"],"base_salary": base_salary,"paid_days": days_diff,"paid_salary" : paid_salary
				
			})

		# For Leavers Table
		doc.leavers=[]
		leavers_employees = frappe.db.sql(f"""
				SELECT 
					e.name,e.employee_name,e.date_of_joining,e.relieving_date,e.designation,ssa.base AS base_salary
				FROM 
					`tabEmployee` e
				LEFT JOIN (
					SELECT 
						employee, base, MAX(from_date) AS latest_from_date
					FROM 
						`tabSalary Structure Assignment`
					GROUP BY 
						employee
				) ssa
				ON e.name = ssa.employee
				WHERE 
					e.relieving_date BETWEEN %(start_date)s AND %(end_date)s
					AND EXISTS (
						SELECT 1 
						FROM `tabSalary Slip` ss 
						WHERE ss.employee = e.name
					)
					{employee_filter}
			""", {"start_date": start_date, "end_date": end_date, "employee_id": employee_id} , as_dict=True)


		for employee in leavers_employees:
			
			base_salary = employee["base_salary"] if employee["base_salary"] else 0
			days_diff = frappe.utils.date_diff(end_date, employee["date_of_joining"]) + 1
			paid_salary = ( (base_salary / total_month_days) * days_diff)
			doc.append("leavers", {
				"employee_id": employee["name"],"employee_name": employee["employee_name"],"designation": employee["designation"],"base_salary": base_salary
				
			})


		#For Arrears
		prev_start_date = frappe.utils.add_to_date(start_date, months= -1)
		prev_end_date = frappe.utils.add_to_date(end_date, months= -1)
		
		doc.arrears=[]
		arrears_employees = frappe.db.sql(f"""
				SELECT 
					e.name,e.employee_name,e.date_of_joining,e.relieving_date,e.designation,e.custom_basic_salary
				FROM 
					`tabEmployee` e
				WHERE 
					e.date_of_joining BETWEEN %(prev_start_date)s AND %(prev_end_date)s
					AND (
						e.relieving_date IS NULL OR 
						NOT (e.relieving_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s)
					)
					AND NOT EXISTS (
						SELECT 1 
						FROM `tabSalary Slip` ss 
						WHERE ss.employee = e.name
					)
					{employee_filter}
			""", {"prev_start_date": prev_start_date, "prev_end_date": prev_end_date, "employee_id": employee_id}, as_dict=True)

		increment_arrears_employees = frappe.db.sql(f"""
					SELECT 
						e.name, 
						e.employee_name, 
						e.designation, 
						e.custom_basic_salary,
						ad.payroll_date
					FROM 
						`tabEmployee` e
					JOIN 
						`tabAdditional Salary` ad ON ad.employee = e.name
					WHERE 
						ad.payroll_date BETWEEN %(start_date)s AND %(end_date)s
						AND ad.salary_component = "Increment Arrears"
						AND ad.docstatus = 1
						{employee_filter}
				""", {"start_date": start_date, "end_date": end_date, "employee_id": employee_id}, as_dict=True)
						

		for employee in arrears_employees:
			
			base_salary = employee["custom_basic_salary"] if employee["custom_basic_salary"] else 0
			days_diff = frappe.utils.date_diff(prev_end_date, employee["date_of_joining"]) + 1
			paid_salary = ( (base_salary / total_month_days) * days_diff)
			doc.append("arrears", {
				"employee_id": employee["name"],"employee_name": employee["employee_name"],"designation": employee["designation"],"base_salary": base_salary,"paid_days" : days_diff,"paid_salary" : paid_salary
				
			})

		for employee in increment_arrears_employees:
			
			base_salary = employee["custom_basic_salary"] if employee["custom_basic_salary"] else 0
			days_diff = frappe.utils.date_diff(end_date, employee["payroll_date"]) + 1
			paid_salary = ( (base_salary / total_month_days) * days_diff)
			doc.append("arrears", {
				"employee_id": employee["name"],"employee_name": employee["employee_name"],"designation": employee["designation"],"base_salary": base_salary,"paid_days" : days_diff,"paid_salary" : paid_salary
				
			})



		# For Increment / Incetives Table
		doc.table_robb = []
		increment_incentives_employees = frappe.db.sql(f"""
					SELECT 
						e.name, 
						e.employee_name, 
						e.designation,
						pd.custom_salary_change_amount
					FROM 
						`tabEmployee` e
					JOIN 
						`tabEmployee Promotion` pd ON pd.employee = e.name
					WHERE 
						pd.promotion_date BETWEEN %(start_date)s AND %(end_date)s
						AND pd.docstatus = 1
						{employee_filter}
				""", {"start_date": start_date, "end_date": end_date, "employee_id": employee_id}, as_dict=True)
						

		for employee in increment_incentives_employees:
			doc.append("table_robb", {
				"employee_id": employee["name"],"employee_name": employee["employee_name"],"designation": employee["designation"],"increment_amount": employee["custom_salary_change_amount"]				
			})

		


		#For Allowances
		doc.allowances = []
		total_allowances_current = frappe.db.sql("""
				SELECT 
					sd.salary_component AS component_name,
					SUM(sd.amount) AS total_allowances
				FROM 
					`tabSalary Slip` ss
				JOIN 
					`tabSalary Detail` sd ON ss.name = sd.parent
				WHERE 
					ss.posting_date BETWEEN %(start_date)s AND %(end_date)s
					AND sd.salary_component IN (
						SELECT sc.name 
						FROM `tabSalary Component` sc 
						WHERE sc.custom_is_allowance = 1 AND sc.disabled = 0
					)
					AND ss.docstatus = 1
				GROUP BY 
					sd.salary_component
			""", {"start_date": start_date, "end_date": end_date}, as_dict=True)
		
		total_allowances_previous = frappe.db.sql("""
				SELECT 
					sd.salary_component AS component_name,
					SUM(sd.amount) AS total_allowances
				FROM 
					`tabSalary Slip` ss
				JOIN 
					`tabSalary Detail` sd ON ss.name = sd.parent
				WHERE 
					ss.posting_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s
					AND sd.salary_component IN (
						SELECT sc.name 
						FROM `tabSalary Component` sc 
						WHERE sc.custom_is_allowance = 1 AND sc.disabled = 0
					)
					AND ss.docstatus = 1
				GROUP BY 
					sd.salary_component
			""", {"prev_start_date": prev_start_date, "prev_end_date": prev_end_date}, as_dict=True)
		
		current_allowances_dict = {allowance["component_name"]: allowance["total_allowances"] for allowance in total_allowances_current}
		previous_allowances_dict = {allowance["component_name"]: allowance["total_allowances"] for allowance in total_allowances_previous}

		all_component_names = set(current_allowances_dict.keys()).union(set(previous_allowances_dict.keys()))

		for component_name in all_component_names:
			# Get the current and previous allowances (default to 0 if not present)
			current = current_allowances_dict.get(component_name, 0)
			previous = previous_allowances_dict.get(component_name, 0)
			
			# Calculate the difference
			difference = current - previous
			if difference > 0:
				doc.append("allowances", {
					"salary_component_type": component_name,"difference": difference
					
				})



		#For Allowances Cancelled
		doc.allowances_cancelled = []
		total_allowances_current_cancelled = frappe.db.sql("""
				SELECT 
					sd.salary_component AS component_name,
					SUM(sd.amount) AS total_allowances
				FROM 
					`tabSalary Slip` ss
				JOIN 
					`tabSalary Detail` sd ON ss.name = sd.parent
				WHERE 
					ss.posting_date BETWEEN %(start_date)s AND %(end_date)s
					AND sd.salary_component IN (
						SELECT sc.name 
						FROM `tabSalary Component` sc 
						WHERE sc.custom_is_allowance = 1 AND sc.disabled = 0
					)
					AND ss.docstatus = 1
				GROUP BY 
					sd.salary_component
			""", {"start_date": start_date, "end_date": end_date}, as_dict=True)
		
		total_allowances_previous_cancelled = frappe.db.sql("""
				SELECT 
					sd.salary_component AS component_name,
					SUM(sd.amount) AS total_allowances
				FROM 
					`tabSalary Slip` ss
				JOIN 
					`tabSalary Detail` sd ON ss.name = sd.parent
				WHERE 
					ss.posting_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s
					AND sd.salary_component IN (
						SELECT sc.name 
						FROM `tabSalary Component` sc 
						WHERE sc.custom_is_allowance = 1 AND sc.disabled = 0
					)
					AND ss.docstatus = 1
				GROUP BY 
					sd.salary_component
			""", {"prev_start_date": prev_start_date, "prev_end_date": prev_end_date}, as_dict=True)
		
		current_allowances_dict = {allowance["component_name"]: allowance["total_allowances"] for allowance in total_allowances_current_cancelled}
		previous_allowances_dict = {allowance["component_name"]: allowance["total_allowances"] for allowance in total_allowances_previous_cancelled}

		all_component_names = set(current_allowances_dict.keys()).union(set(previous_allowances_dict.keys()))

		for component_name in all_component_names:
			current = current_allowances_dict.get(component_name, 0)
			previous = previous_allowances_dict.get(component_name, 0)
			difference = current - previous
			if difference < 0:
				difference = difference * -1
				doc.append("allowances_cancelled", {
					"salary_component_type": component_name,"difference": difference
					
				})




		#For Less Paid
		doc.less_paid_last_month = []
		less_paid_data = frappe.db.sql(f"""
			SELECT 
				ss.employee AS employee_id,ss.employee_name AS employee_name,ss.absent_days AS absent_days,ssa.base AS basic_salary,ss.designation AS designation
			FROM 
				`tabSalary Slip` ss
			LEFT JOIN (
				SELECT 
					employee, 
					base, 
					MAX(from_date) AS latest_from_date
				FROM 
					`tabSalary Structure Assignment`
				WHERE 
					docstatus = 1
				GROUP BY 
					employee
			) ssa ON ss.employee = ssa.employee

			WHERE 
				ss.docstatus = 1
				AND ss.posting_date BETWEEN %(start_date)s AND %(end_date)s
				{employee1_filter}
		""", {"start_date": start_date, "end_date": end_date,"employee_id": employee_id}, as_dict=True)



		for employee in less_paid_data:

			base_salary = employee["basic_salary"] if employee["basic_salary"] else 0
			absent_days = employee["absent_days"]
			paid_days = 30 - absent_days
			paid_salary = ( (base_salary / total_month_days) * absent_days)
			if paid_salary < base_salary:

				doc.append("less_paid_last_month", {
					"employee_id": employee["employee_id"],"employee_name": employee["employee_name"],"designation": employee["designation"],"base_salary": base_salary,"paid_days" : paid_days,"paid_salary" : paid_salary
					
				})


		#For Excess Paid
		doc.excess_paid_month = []
		excess_paid_data = frappe.db.sql(f"""
			SELECT 
				ss.employee AS employee_id,ss.employee_name AS employee_name,ss.absent_days AS absent_days,ssa.base AS basic_salary,ss.designation AS designation
			FROM 
				`tabSalary Slip` ss
			LEFT JOIN (
				SELECT 
					employee, 
					base, 
					MAX(from_date) AS latest_from_date
				FROM 
					`tabSalary Structure Assignment`
				WHERE 
					docstatus = 1
				GROUP BY 
					employee
			) ssa ON ss.employee = ssa.employee

			WHERE 
				ss.docstatus = 1
				AND ss.posting_date BETWEEN %(start_date)s AND %(end_date)s
				{employee1_filter}
		""", {"start_date": start_date, "end_date": end_date, "employee_id" : employee_id}, as_dict=True)



		for employee in excess_paid_data:

			base_salary = employee["basic_salary"] if employee["basic_salary"] else 0
			absent_days = employee["absent_days"]
			paid_days = 30 - absent_days
			paid_salary = ( (base_salary / total_month_days) * absent_days)
			if paid_salary > base_salary:

				doc.append("excess_paid_month", {
					"employee_id": employee["employee_id"],"employee_name": employee["employee_name"],"designation": employee["designation"],"base_salary": base_salary,"paid_days" : paid_days,"paid_salary" : paid_salary
					
				})

		#total Salary
		total_paid_current_month = frappe.db.sql(f"""
			SELECT 
				SUM(ss.gross_pay) AS basic_salary
			FROM 
				`tabSalary Slip` ss
			WHERE 
				ss.docstatus = 1
				AND ss.start_date BETWEEN %(start_date)s AND %(end_date)s
				{employee1_filter}
		""", {"start_date": start_date, "end_date": end_date, "employee_id" : employee_id}, as_dict=True)

		total_paid_last_month = frappe.db.sql(f"""
			SELECT 
				SUM(ss.gross_pay) AS basic_salary
			FROM 
				`tabSalary Slip` ss
			WHERE 
				ss.docstatus = 1
				AND ss.start_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s
				{employee1_filter}
		""", {"prev_start_date": prev_start_date, "prev_end_date": prev_end_date, "employee_id" : employee_id}, as_dict=True)


		if total_paid_current_month:
			total_current_basic_salary = total_paid_current_month[0].get('basic_salary', 0)
			doc.salary_paid_current_month = total_current_basic_salary if total_current_basic_salary is not None else 0
		else:
			doc.salary_paid_current_month = 0

		if total_paid_last_month:
			total_last_basic_salary = total_paid_last_month[0].get('basic_salary', 0)
			doc.salary_paid_last_month = total_last_basic_salary if total_last_basic_salary is not None else 0
		else:
			doc.salary_paid_last_month = 0

		# Ensure both are floats
		doc.salary_paid_current_month = float(doc.salary_paid_current_month)
		doc.salary_paid_last_month = float(doc.salary_paid_last_month)

		# Calculate total difference
		doc.total_difference = doc.salary_paid_current_month - doc.salary_paid_last_month

		# Ensure total_difference is positive
		if doc.total_difference < 0:
			doc.total_difference = doc.total_difference * -1