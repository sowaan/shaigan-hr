# Copyright (c) 2024, Sowaan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TrainingNeedAssessmentForm(Document):
	def after_insert(self):
		email = frappe.db.get_value("User", {"name": self.owner}, "email")
		if email:
			employee = frappe.db.get_value("Employee", {"user_id": email}, "name")
			employee_doc = frappe.get_doc("Employee",employee)
			self.employee_id = employee_doc.custom_shaigan_id
			self.employee_name = employee_doc.employee_name
			self.designation = employee_doc.designation
			self.department = employee_doc.department
			for q in employee_doc.education:
				if q.qualification:
					self.qualification = q.qualification
					break
			self.date_of_joining = employee_doc.date_of_joining
			self.gender = employee_doc.gender
			
