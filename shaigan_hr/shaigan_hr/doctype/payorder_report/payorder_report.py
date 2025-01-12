# Copyright (c) 2025, Sowaan and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
import frappe

class PayorderReport(Document):
	def before_save(self):
		start_date = self.start_date
		end_date = self.end_date

		filters = []
		params = {
			"start_date": start_date, 
			"end_date": end_date
		}

		employee_id = self.employee
		branch = self.branch
		department = self.department
		company = self.company

		# Add filters dynamically
		if branch:
			filters.append("e.branch = %(branch)s")
			params["branch"] = branch

		if department:
			filters.append("e.department = %(department)s")
			params["department"] = department

		if employee_id:
			filters.append("e.name = %(employee_id)s")
			params["employee_id"] = employee_id
		
		if company:
			filters.append("e.company = %(company)s")
			params["company"] = company





		# Combine filters into SQL WHERE clause
		filter_condition = " AND ".join(filters)

		query = frappe.db.sql(f"""
			SELECT
				e.custom_shaigan_id as "Employee ID",
				ss.employee_name as "Employee Name",
				e.custom_city as "Station",
				e.custom_cnic_no as "CNIC",
				ss.net_pay as "Amount"
				
			FROM
				`tabSalary Slip` as ss
			LEFT JOIN
				`tabEmployee` AS e on ss.employee = e.name 
			
				
			
			WHERE
				start_date >= %(start_date)s
				AND end_date <= %(end_date)s
				AND ss.docstatus = 1
				{filter_condition}
				AND e.bank_name = "Payorder"
				
		""", params, as_dict=True)


		self.table_lpbb = []
		for row in query:
			self.append("table_lpbb", {
				"employee_id": row["Employee ID"],
				"name1": row["Employee Name"],
				"station": row["Station"],
				"cnic": row["CNIC"],
				"amount": row["Amount"]
			})