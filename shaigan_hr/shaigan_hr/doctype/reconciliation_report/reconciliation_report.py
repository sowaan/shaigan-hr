# Copyright (c) 2024, Sowaan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ReconciliationReport(Document):
	def before_save(doc):

		# doc = self
		start_date = doc.start_date
		end_date = doc.end_date
		total_month_days = 30
		

		prev_start_date = frappe.utils.add_to_date(start_date, months= -1)
		prev_end_date = frappe.utils.add_to_date(end_date, months= -1)
		
		# employee_filter=""
		# employee1_filter=""
		# if doc.employee:
		# 	employee_filter = "AND e.name = %(employee_id)s"
		# 	employee1_filter = "AND ss.employee = %(employee_id)s"

		filters = []
		filters_salaryslip = []
		params = {
			"start_date": start_date, 
			"end_date": end_date,
			"prev_start_date": prev_start_date,
			"prev_end_date": prev_end_date
		}
		employee_id = doc.employee
		company = doc.company
		branch = doc.branch
		department = doc.department



		# Add filters dynamically
		if company:
			filters.append("e.company = %(company)s")
			params["company"] = company
			filters_salaryslip.append("ss.company = %(company)s")

		if branch:
			filters.append("e.branch = %(branch)s")
			params["branch"] = branch
			filters_salaryslip.append("ss.branch = %(branch)s")

		if department:
			filters.append("e.department = %(department)s")
			params["department"] = department
			filters_salaryslip.append("ss.department = %(department)s")

		if employee_id:
			filters.append("e.name = %(employee_id)s")
			params["employee_id"] = employee_id
			filters_salaryslip.append("ss.employee = %(employee_id)s")

		# Combine filters into SQL WHERE clause
		filter_condition = " AND ".join(filters)
		filter_condition_salaryslip = " AND ".join(filters_salaryslip)
		if filter_condition_salaryslip:
			filter_condition_salaryslip = " AND " + filter_condition_salaryslip

		if filter_condition:
			filter_condition = " AND " + filter_condition




		#joiners#########################################
		joiners_employees = frappe.db.sql(f"""
			SELECT 
				e.name AS employee_id,
				e.employee_name,
				e.date_of_joining,
				e.relieving_date,
				e.designation,
				ss.gross_pay,
				SUM(CASE WHEN se.salary_component = 'Pre Month Arrear' THEN se.amount ELSE 0 END) AS pre_month_arrear,
				SUM(CASE WHEN se.salary_component = 'Imprest Reimbursement' THEN se.amount ELSE 0 END) AS imprest_reimbursement,
				SUM(CASE WHEN se.salary_component = 'Arrears' THEN se.amount ELSE 0 END) AS arrears,
				SUM(CASE WHEN se.salary_component = 'Increment Arrears' THEN se.amount ELSE 0 END) AS increment_arrears,
				SUM(CASE WHEN se.salary_component = 'Arrears (Automated)' THEN se.amount ELSE 0 END) AS automated_arrears
			FROM 
				`tabEmployee` e
			INNER JOIN `tabSalary Slip` ss ON ss.employee = e.name
			LEFT JOIN `tabSalary Detail` se ON se.parent = ss.name AND se.parentfield = 'earnings'
			WHERE 
				(
					e.date_of_joining BETWEEN %(start_date)s AND %(end_date)s 
					OR (
						e.date_of_joining BETWEEN %(prev_start_date)s AND %(prev_end_date)s
						AND NOT EXISTS (  
							SELECT 1 FROM `tabSalary Slip` ss_prev
							WHERE ss_prev.employee = e.name
							AND ss_prev.start_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s
						)
					)
				)
				AND ss.start_date BETWEEN %(start_date)s AND %(end_date)s  -- Only current month's salary slips
				{filter_condition}
			GROUP BY e.name, ss.name
		""",params, as_dict=True)

		# Clear previous data
		doc.table_qase = []

		# Process each employee's salary details
		for employee in joiners_employees:
			gross_pay = employee["gross_pay"] if employee["gross_pay"] else 0
			pre_month_arrear = employee["pre_month_arrear"] if employee["pre_month_arrear"] else 0
			imprest_reimbursement = employee["imprest_reimbursement"] if employee["imprest_reimbursement"] else 0
			arrears = employee["arrears"] if employee["arrears"] else 0
			increment_arrears = employee["increment_arrears"] if employee["increment_arrears"] else 0
			automated_arrears = employee["automated_arrears"] if employee["automated_arrears"] else 0

			# Calculate the adjusted base salary
			adjusted_base_salary = (
				gross_pay 
				- pre_month_arrear 
				- imprest_reimbursement 
				- arrears 
				- increment_arrears 
				- automated_arrears
			)

			# Calculate paid salary based on joining days
			days_diff = frappe.utils.date_diff(end_date, employee["date_of_joining"]) + 1
			if days_diff > 30:
				days_diff = 30

			# Append data to the table
			doc.append("table_qase", {
				"employee_id": employee["employee_id"],
				"employee_name": employee["employee_name"],
				"designation": employee["designation"],
				"base_salary": round(adjusted_base_salary),
				"paid_days": days_diff,
				"paid_salary": round(adjusted_base_salary)
			})


		


		# For Leavers Table#################################################
		doc.leavers = []

		# Query to get leavers' details and arrears components (if any)
		leavers_employees = frappe.db.sql(f"""
			SELECT
				e.name AS employee_id,
				e.employee_name,
				e.date_of_joining,
				e.relieving_date,
				e.designation,
				ss_prev.gross_pay,
				SUM(CASE WHEN se.salary_component = 'Imprest Reimbursement' THEN se.amount ELSE 0 END) AS imprest_reimbursement,
				SUM(CASE WHEN se.salary_component LIKE '%%Arrear%%' THEN se.amount ELSE 0 END) AS arrears_amount  -- Sum of all arrears components
			FROM
				`tabEmployee` e
			INNER JOIN `tabSalary Slip` ss_prev ON ss_prev.employee = e.name 
				AND ss_prev.start_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s  -- Previous month salary slip
			LEFT JOIN `tabSalary Detail` se ON se.parent = ss_prev.name AND se.parentfield = 'earnings'
			WHERE
				e.relieving_date BETWEEN %(start_date)s AND %(end_date)s
				{filter_condition}
			GROUP BY e.name, ss_prev.name
		""",params
		#   {
		# 	"start_date": start_date,
		# 	"end_date": end_date,
		# 	"prev_start_date": prev_start_date,
		# 	"prev_end_date": prev_end_date,
		# 	"employee_id": employee_id
		# }
		, as_dict=True)

		# Process each leaver's salary details
		for employee in leavers_employees:
			gross_pay = employee["gross_pay"] if employee["gross_pay"] else 0
			imprest_reimbursement = employee["imprest_reimbursement"] if employee["imprest_reimbursement"] else 0
			arrears_amount = employee["arrears_amount"] if employee["arrears_amount"] else 0

			# Adjust the gross pay by subtracting "Imprest Reimbursement" and all "Arrears" components
			adjusted_gross_pay = gross_pay - imprest_reimbursement - arrears_amount

			# Append to the leavers table
			doc.append("leavers", {
				"employee_id": employee["employee_id"],
				"employee_name": employee["employee_name"],
				"designation": employee["designation"],
				"base_salary": round(adjusted_gross_pay)
			})







		#For Arrears########################################################
		doc.arrears = []
		salary_slips_with_arrears = frappe.db.sql(f"""
			SELECT 
				e.name AS employee_id,
				e.employee_name AS employee_name,
				e.designation,
				se.salary_component,
				se.amount
			FROM 
				`tabSalary Slip` ss
			INNER JOIN `tabEmployee` e ON e.name = ss.employee
			INNER JOIN `tabSalary Detail` se 
				ON se.parent = ss.name AND se.parentfield = 'earnings'
			WHERE 
				ss.start_date BETWEEN %(start_date)s AND %(end_date)s
				AND se.salary_component LIKE '%%Arrear%%' 
				{filter_condition}
			ORDER BY ss.start_date
		""",params
		#   {
		# 	"start_date": start_date,
		# 	"end_date": end_date,
		# 	"employee_id":employee_id
		# }
		, as_dict=True)

		# Process each employee's salary slip with arrears
		for employee in salary_slips_with_arrears:
			arrears_amount = employee["amount"] if employee["amount"] else 0  # Get arrears amount

			# Append to the arrears list in the document
			doc.append("arrears", {
				"employee_id": employee["employee_id"],
				"employee_name": employee["employee_name"],
				"designation": employee["designation"],
				"arrears_type": employee["salary_component"],  # Name of the arrears component
				"amount": round(arrears_amount)  # Amount of the arrears
			})




		# For Increment / Incetives Table############################################
		doc.table_robb = []
		doc.table_robb = []
		combined_query = f"""
			SELECT 
				e.name AS employee_id, 
				e.employee_name, 
				e.designation,
				SUM(ead.amount) AS increment_amount,
				CASE 
					WHEN ei.increment_date IS NOT NULL THEN DATEDIFF(%(end_date)s, ei.increment_date)+1
					ELSE 30 
				END AS days
			FROM
				`tabEmployee` e
			JOIN
				`tabEmployee Arrears` ea ON ea.employee = e.name
			JOIN
				`tabEmployee Earning Detail` ead ON ead.parent = ea.name
			LEFT JOIN
				`tabEmployee Increment` ei ON ei.employee = e.name
				AND ei.arrears_salary_component NOT LIKE 'Pre Increment Arrears'  -- Exclude Pre Increment Arrears
				AND ei.increment_date BETWEEN %(start_date)s AND %(end_date)s
			WHERE
				ea.from_date = %(start_date)s
				AND ea.to_date = %(end_date)s
				AND ea.earning_component LIKE '%%Increment%%'
				AND ea.earning_component NOT LIKE 'Pre Increment Arrears'
				AND ea.docstatus = 1
				{filter_condition}
			GROUP BY e.name

			
			# UNION ALL
			
			# SELECT 
			# 	e.name AS employee_id, 
			# 	e.employee_name, 
			# 	e.designation,
			# 	ei.increment_amount AS increment_amount,
			# 	30 AS days
			# FROM
			# 	`tabEmployee` e
			# JOIN
			# 	`tabEmployee Increment` ei ON ei.employee = e.name
			# WHERE
			# 	ei.increment_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s
			# 	AND ei.arrears_salary_component = 'Pre Increment Arrears'
			# 	AND ei.docstatus = 1
				
		"""

		# Execute the query
		combined_results = frappe.db.sql(combined_query,params
		# 						    {
		# 	"start_date": start_date,
		# 	"end_date": end_date,
		# 	"prev_start_date": prev_start_date,
		# 	"prev_end_date": prev_end_date,
		# 	"employee_id": employee_id
		# }
		, as_dict=True)

		# Append each result to table_robb
		for employee in combined_results:
			doc.append("table_robb", {
				"employee_id": employee["employee_id"],
				"employee_name": employee["employee_name"],
				"designation": employee["designation"],
				"increment_amount": round(employee["increment_amount"]),
				"increment_days" : employee["days"]
			})
		


		#For Allowances###############################################
		doc.allowances = []
		doc.allowances_cancelled = []
		total_allowances_current = frappe.db.sql(f"""
			SELECT 
				ss.employee AS employee_id,
				ss.employee_name,
				ss.designation,
				sd.salary_component AS component_name,
				sd.amount AS total_allowances,
				"current" as tag
			FROM 
				`tabSalary Slip` ss
			LEFT JOIN 
				`tabSalary Detail` sd ON ss.name = sd.parent
			WHERE 
				ss.start_date BETWEEN %(start_date)s AND %(end_date)s  
				AND sd.salary_component IN (
					SELECT sc.name 
					FROM `tabSalary Component` sc 
					WHERE sc.custom_is_allowance = 1 AND sc.disabled = 0
					{filter_condition_salaryslip}
				)
			
		""",params 
		# {"start_date": start_date, "end_date": end_date}
		, as_dict=True)

		current_employees= []
		
		
		current_employees = [
			row["employee_id"] for row in frappe.db.sql(f"""
				SELECT 
					ss.employee AS employee_id
				FROM 
					`tabSalary Slip` ss
				WHERE 
					ss.start_date BETWEEN %(start_date)s AND %(end_date)s  
					{filter_condition_salaryslip}
			""",params
			#   {"start_date": start_date, "end_date": end_date}
			, as_dict=True)
		]
		# if not current_employees:
		# 	current_employees = ("",)
		params["current_employees"] = current_employees
					
		
		

		total_allowances_previous = frappe.db.sql(f"""
			SELECT 
				ss.employee AS employee_id,
				ss.employee_name,
				ss.designation,
				sd.salary_component AS component_name,
				sd.amount AS total_allowances,
				"false" as tag
			FROM 
				`tabSalary Slip` ss
			JOIN 
				`tabSalary Detail` sd ON ss.name = sd.parent
			WHERE 
				ss.start_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s 
				AND sd.salary_component IN (
					SELECT sc.name 
					FROM `tabSalary Component` sc 
					WHERE sc.custom_is_allowance = 1 AND sc.disabled = 0
				)
				AND ss.employee IN %(current_employees)s
				{filter_condition_salaryslip}
			GROUP BY 
				ss.employee, sd.salary_component
		""", params 
		# {"prev_start_date": prev_start_date, "prev_end_date": prev_end_date , "current_employees": current_employees } 
		, as_dict=True)
		# frappe.msgprint(str(len(previous_employees)))

		for row in total_allowances_current:
			sig = 0
			for row1 in total_allowances_previous:
				if row1["tag"] == "false" and row["employee_id"] == row1["employee_id"] and row["component_name"] == row1["component_name"]:
					diff = row["total_allowances"] - row1["total_allowances"]
					if diff > 0:
						doc.append("allowances", {
							"employee_id": row["employee_id"],
							"salary_component_type": row["component_name"],
							"difference": round(row["total_allowances"] - row1["total_allowances"]),
							"employee_name": row["employee_name"],
							"designation": row["designation"]
						})
					elif diff<0:
						doc.append("allowances_cancelled", {
						"employee_id": row["employee_id"],
						"salary_component_type": row["component_name"],
						"difference": round(row1["total_allowances"] - row["total_allowances"]),
						"employee_name": row["employee_name"],
						"designation": row["designation"]
					})
					row1["tag"] = "true"
					sig = 1
					break

			if sig!= 1:
				doc.append("allowances", {
					"employee_id": row["employee_id"],
					"salary_component_type": row["component_name"],
					"difference": round(row["total_allowances"]),
					"employee_name": row["employee_name"],
					"designation": row["designation"]
				})
			
		for row1 in total_allowances_previous:				
			if row1["tag"] == "false":
				doc.append("allowances_cancelled", {
					"employee_id": row1["employee_id"],
					"salary_component_type": row1["component_name"],
					"difference": round(row1["total_allowances"]),
					"employee_name": row1["employee_name"],
					"designation": row1["designation"]
				})


		#less paid ######################

		current_month_salaries = frappe.db.sql(f"""
			SELECT 
				ss.employee AS employee_id,
				ss.employee_name,
				ss.designation,
				SUM(CASE WHEN sd.salary_component IN ('House Rent Allowance', 'Basic', 'Medical', 'Utilities  Allowance') THEN sd.amount ELSE 0 END) AS total_amount
			
			FROM 
				`tabSalary Slip` ss
			LEFT JOIN 
				`tabSalary Detail` sd ON ss.name = sd.parent
			WHERE 
				ss.start_date BETWEEN %(start_date)s AND %(end_date)s
				{filter_condition_salaryslip}
				# AND sd.salary_component IN ('House Allowance', 'Basic', 'Medical', 'Utility Allowance')
				
			GROUP BY 
				ss.employee
		""",params 
		# {"start_date": start_date, "end_date": end_date, "employee_id":employee_id} 
		, as_dict=True)


		previous_month_salaries = frappe.db.sql(f"""
			SELECT 
				ss.employee AS employee_id,
				ss.employee_name,
				ss.designation,
				SUM(CASE WHEN sd.salary_component IN ('House Rent Allowance', 'Basic', 'Medical', 'Utilities  Allowance', 'Increment') THEN sd.amount ELSE 0 END) AS total_amount
			FROM 
				`tabSalary Slip` ss
			LEFT JOIN 
				`tabSalary Detail` sd ON ss.name = sd.parent
			WHERE 
				ss.end_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s
				AND ss.docstatus IN (0, 1)
				{filter_condition_salaryslip}
			GROUP BY 
				ss.employee
		""",
		params
		# {"prev_start_date": prev_start_date, "prev_end_date": prev_end_date,"employee_id":employee_id}
		, as_dict=True)
		
		current_map = {row['employee_id']: row for row in current_month_salaries}
		previous_map = {row['employee_id']: row for row in previous_month_salaries}
		doc.less_paid_last_month = []
		# Loop through previous month's data, calculate the difference and append to `less_paid_last_month` table
		for employee_id, prev_data in previous_map.items():
			diff = 0
			diff1 = 0
			current_data = current_map.get(employee_id)
			if current_data:
				diff = current_data['total_amount'] - prev_data['total_amount']
				diff1 = abs(diff)
				# if diff != 0 :
				# 	if diff1 < 0 :
				# 		diff1 = diff1 * (-1)
				# 	# If the difference is very small, set it to 0
				# 	if  diff1 > 0 and diff1 < 1:
				# 		diff = 0
				# Append non-zero differences to the table
				if round(diff1) != 0:
					doc.append("less_paid_last_month", {
						"employee": employee_id,
						"employee_name": current_data['employee_name'],
						"designation": current_data['designation'],
						"amount": round(diff1)
					})











		#For Excess Paid########################################################
		doc.excess_paid_month = []
		excess_paid_data = frappe.db.sql(f"""
			SELECT 
				ss.employee AS employee_id,
				ss.employee_name AS employee_name,
				ss.designation,
				se.salary_component,
				se.amount
			FROM 
				`tabSalary Slip` ss
			INNER JOIN `tabSalary Detail` se 
				ON se.parent = ss.name AND se.parentfield = 'earnings'
			WHERE 
				ss.start_date BETWEEN %(prev_start_date)s AND %(prev_end_date)s
				AND se.salary_component LIKE '%%Arrear%%' 
				{filter_condition_salaryslip}
			ORDER BY ss.start_date
		""", params 
		# {
		# 	"prev_start_date": prev_start_date,
		# 	"prev_end_date": prev_end_date,
		# 	"employee_id":employee_id
		# }
		, as_dict=True)

		# Process each employee's salary slip with arrears
		for employee in excess_paid_data:
			arrears_amount = employee["amount"] if employee["amount"] else 0  # Get arrears amount

			# Append to the arrears list in the document
			doc.append("excess_paid_month", {
				"employee_id": employee["employee_id"],
				"employee_name": employee["employee_name"],
				"designation": employee["designation"],
				"arrears_type": employee["salary_component"],  # Name of the arrears component
				"amount": round(arrears_amount)  # Amount of the arrears
			})

		





		#total Salary
		total_gross_current_month = frappe.db.sql(f"""
			SELECT 
				SUM(ss.gross_pay) AS basic_salary
			FROM 
				`tabSalary Slip` ss
			WHERE 
				ss.docstatus IN (0,1)
				AND ss.start_date = %(start_date)s AND ss.end_date = %(end_date)s
				{filter_condition_salaryslip}
			
		""",params 
		# {"start_date": start_date, "end_date": end_date, "employee_id" : employee_id}
		, as_dict=True)


		total_gross_last_month = frappe.db.sql(f"""
			SELECT 
				SUM(ss.gross_pay) AS basic_salary
			FROM 
				`tabSalary Slip` ss
			WHERE
				ss.docstatus IN (0,1)
				AND ss.start_date = %(prev_start_date)s AND ss.end_date = %(prev_end_date)s
				{filter_condition_salaryslip}
		""",params 
		# {"prev_start_date": prev_start_date, "prev_end_date": prev_end_date, "employee_id" : employee_id}
		, as_dict=True)



		total_imbers_current_month = frappe.db.sql(f"""
			SELECT 
				SUM(CASE WHEN se.salary_component = 'Imprest Reimbursement' THEN se.amount ELSE 0 END) AS imprest_reimbursement
		
			FROM 
				`tabSalary Slip` ss
			LEFT JOIN
				`tabSalary Detail` se ON se.parent = ss.name
			WHERE 
				ss.docstatus IN (0,1)
				AND ss.start_date = %(start_date)s 
				AND ss.end_date = %(end_date)s
				{filter_condition_salaryslip}
			
		""", params 
		# {"start_date": start_date, "end_date": end_date, "employee_id" : employee_id}
		, as_dict=True)

		total_imbers_last_month = frappe.db.sql(f"""
			SELECT 
				SUM(CASE WHEN se.salary_component = 'Imprest Reimbursement' THEN se.amount ELSE 0 END) AS imprest_reimbursement
				
			FROM 
				`tabSalary Slip` ss
			LEFT JOIN
				`tabSalary Detail` se ON se.parent = ss.name
			WHERE 
				ss.docstatus IN (0,1)
				AND ss.start_date = %(prev_start_date)s 
				AND ss.end_date = %(prev_end_date)s
				{filter_condition_salaryslip}
		""", params 
		# {"prev_start_date": prev_start_date, "prev_end_date": prev_end_date, "employee_id" : employee_id}
		, as_dict=True)


		# Extract the basic_salary values (assuming a single result will be returned)
		salary_paid_current_month = (total_gross_current_month[0]['basic_salary'] or 0) - (total_imbers_current_month[0]['imprest_reimbursement'] or 0) if total_gross_current_month else 0

		# salary_paid_current_month = total_gross_current_month[0]['basic_salary'] - total_imbers_current_month[0]['imprest_reimbursement']  if total_gross_current_month else 0
		salary_paid_last_month = total_gross_last_month[0]['basic_salary'] - total_imbers_last_month[0]['imprest_reimbursement'] if total_gross_last_month else 0
		# frappe.msgprint(str(total_paid_current_month[0]['imprest_reimbursement']) + str(total_paid_current_month[0]['basic_salary']))
		# frappe.msgprint(str(total_paid_last_month[0]['imprest_reimbursement']) + str(total_paid_last_month[0]['basic_salary']))
		# frappe.msgprint(str(total_imbers_current_month[0]['imprest_reimbursement']))
		# frappe.msgprint(str(total_imbers_last_month[0]['imprest_reimbursement']))

		# Assign the values to the respective fields in the document
		doc.salary_paid_current_month = salary_paid_current_month
		doc.salary_paid_last_month = salary_paid_last_month

		# Calculate the total difference (sum of current and previous month's salary)
		doc.total_difference = abs(salary_paid_current_month - salary_paid_last_month)


		total1 = 0
		total2 = 0

		# Summing total1
		for i in doc.table_qase:
			total1 += i.paid_salary or 0
		for i in doc.arrears:
			total1 += i.amount or 0
		for i in doc.table_robb:
			total1 += i.increment_amount or 0
		for i in doc.allowances:
			total1 += i.difference or 0
		for i in doc.less_paid_last_month:
			total1 += i.amount or 0
		doc.total1 = total1

		# Summing total2
		for i in doc.leavers:
			total2 += i.base_salary or 0
		for i in doc.excess_paid_month:
			total2 += i.amount or 0
		for i in doc.allowances_cancelled:
			total2 += i.difference or 0
		doc.total2 = total2

		# Calculate the difference
		doc.difference = doc.total1 - doc.total2
		