import frappe
from datetime import datetime
from frappe.utils import now, add_days
from sowaan_hr.sowaan_hr.doctype.arrears_process.arrears_process import ArrearsProcess

class OverrideArrearsProcess(ArrearsProcess):
	# frappe.msgprint('override')
	def get_employee_arrears(self, employee, from_date, to_date, salary_component):
		"""Check if Employee Arrears exists."""
		return frappe.db.exists("Employee Arrears", {
			"employee": employee,
			"from_date": from_date,
			"to_date": to_date,
			"earning_component": salary_component,
			"docstatus": 1
		})

	def get_salary_slip(self, employee, start_date, end_date, absent_days=None):
		salary_slip = frappe.get_doc({
			"doctype": 'Salary Slip',
			"employee": employee,
			"posting_date": end_date,
			"start_date": start_date,
			"end_date": end_date,
			"docstatus": 0
		})
		if absent_days:
			salary_slip.absent_days = absent_days
		salary_slip.validate()
		return salary_slip
	
	def validate_arrears_process(self):
		filters = []
		employees_list = []
		if self.employee:
			filters = [
				["from_date", ">", self.from_date],
				["from_date", "<=", self.to_date],
				["employee", "=", self.employee],
				["docstatus", "=", 1]
			]
			if self.company:
				filters.append(["company", "=", self.company])
			if self.department:
				filters.append(["department", "=", self.department])

			employees_list = frappe.get_all("Salary Structure Assignment", filters=filters, fields=['employee'], distinct=True)
		else:
			filters = [
				["increment_date", ">=", self.from_date],
				["increment_date", "<=", self.to_date],
				["docstatus", "=", 1]
			]

			if self.company:
				filters.append(["company", "=", self.company])
			if self.department:
				filters.append(["department", "=", self.department])
				
			employees_list = frappe.get_all("Employee Increment", filters=filters, fields=['employee'], distinct=True)

		if not self.for_new_employees:
			if employees_list:
				filter_employee = []
				for emp in employees_list:
					emp_arrears_exit = self.get_employee_arrears(emp.employee, self.from_date, self.to_date, self.salary_component)
					if not emp_arrears_exit:
						filter_employee.append(emp)
				employees_done = []
				for emp in filter_employee:
					if frappe.db.get_value("Employee", emp.employee, "status") == "Active" and emp.employee in employees_done:
						continue

					employees_done.append(emp.employee)
					
					salary_structure_assignment_list = frappe.get_all(
						"Salary Structure Assignment",
						filters=[
							["employee", "=", emp.employee],
							["from_date", ">", self.from_date],
							["from_date", "<=", self.to_date],
							["docstatus", "=", 1]
						],
						fields=['name', 'from_date', 'base'],
						order_by="from_date desc"
					)
					# frappe.msgprint('salary_structure_assignment_list: ' + str(salary_structure_assignment_list))
					if not salary_structure_assignment_list:
						continue

					salary_structure_assignment = salary_structure_assignment_list[0]
				
					default_salary = self.get_salary_slip(emp.employee, self.from_date, self.to_date)
					s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
						"employee": emp.employee,
						"from_date": ["<", salary_structure_assignment.from_date],
						"docstatus": 1
					}, order_by="from_date desc")

					# per_day = s_s_assignment.base / first_salary.custom_payment_day
					# default_salary.custom_payment_day =  first_salary.custom_payment_day - absent_days
					default_salary.custom_base = s_s_assignment.base
					# default_salary.custom_absent_deduction = per_day * absent_days
					default_salary.custom_monthly_salary = s_s_assignment.base
					# default_salary.payment_days =  first_salary.payment_days - absent_days
					default_salary.calculate_net_pay()
					# frappe.msgprint('default_salary: ' + str(default_salary.net_pay))

					
					absent_days = frappe.utils.date_diff(self.to_date, add_days(salary_structure_assignment.from_date, -1))
					# frappe.msgprint('absent_days: ' + str(absent_days))
					# frappe.msgprint(str(add_days(salary_structure_assignment.from_date, -1)))
					first_salary = self.get_salary_slip(emp.employee, self.from_date, add_days(salary_structure_assignment.from_date, -1), absent_days)
					
					# s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
					# 	"employee": emp.employee,
					# 	"from_date": ["<=", self.from_date],
					# 	"docstatus": 1
					# })
					# frappe.msgprint('s_s_assignment: ' + str(s_s_assignment))
					per_day = s_s_assignment.base / first_salary.custom_payment_day
					first_salary.custom_payment_day =  first_salary.custom_payment_day - absent_days
					first_salary.custom_base = per_day * first_salary.custom_payment_day
					first_salary.custom_absent_deduction = per_day * absent_days
					first_salary.custom_monthly_salary = s_s_assignment.base
					first_salary.payment_days =  first_salary.payment_days - absent_days
					first_salary.calculate_net_pay()
					# frappe.msgprint('first_salary: ' + str(first_salary.net_pay))
					
					sal_1_basic = 0
					for x in first_salary.earnings:
						for d in self.a_p_earnings:
							if x.salary_component == d.salary_component:
								sal_1_basic = sal_1_basic + x.amount
					
					
					second_salary = self.get_salary_slip(emp.employee, salary_structure_assignment.from_date, self.to_date)
					absent_days = frappe.utils.date_diff(salary_structure_assignment.from_date, self.from_date)

					# frappe.msgprint('absent_days: ' + str(absent_days))
					# s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
					# 	"employee": emp.employee,
					# 	"from_date": ["<=", salary_structure_assignment.from_date],
					# 	"docstatus": 1
					# })
					# frappe.msgprint('salary_structure_assignment: ' + str(salary_structure_assignment))
					per_day = salary_structure_assignment.base / second_salary.custom_payment_day
					second_salary.custom_payment_day =  second_salary.custom_payment_day - (absent_days)
					second_salary.custom_base = per_day * second_salary.custom_payment_day
					second_salary.custom_absent_deduction = per_day * (absent_days)
					second_salary.custom_monthly_salary = salary_structure_assignment.base
					second_salary.payment_days =  second_salary.payment_days - (absent_days)
					second_salary.calculate_net_pay() 
					# frappe.msgprint('second_salary: ' + str(second_salary.net_pay))
					
					
					sal_2_basic = 0
					for x in second_salary.earnings:
						for d in self.a_p_earnings:
							if x.salary_component == d.salary_component:
								sal_2_basic = sal_2_basic + x.amount
					
					curr_basic = 0
					for x in default_salary.earnings:
						for d in self.a_p_earnings:
							if x.salary_component == d.salary_component:
								curr_basic = curr_basic + x.amount
						
					total_basic = sal_2_basic + sal_1_basic   
					arrears_basic = abs(total_basic - curr_basic)
					# if arrears_basic < 0:
					# 	arrears_basic = arrears_basic * -1
					# frappe.msgprint('total_basic: ' + str(total_basic))
					# frappe.msgprint('curr_basic: ' + str(curr_basic))
					# frappe.msgprint('arrears_basic: ' + str(arrears_basic))
					# frappe.msgprint('sal_1_basic: ' + str(sal_1_basic))
					# frappe.msgprint('sal_2_basic: ' + str(sal_2_basic))
										
					for row in self.arrear_process_detail:
						if row.employee == emp.employee:
							# If the condition is true, update the row
							row.to = self.to_date
							row.base_salary = salary_structure_assignment.base
							row.amount = arrears_basic
							break  # Exit the loop when a match is found
					else:
						# This block runs only if the loop completes without a 'break'
						new_row = self.append("arrear_process_detail", {})
						new_row.employee = emp.employee
						new_row.to = self.to_date
						new_row.base_salary = salary_structure_assignment.base
						new_row.amount = arrears_basic


		if self.for_new_employees:
			previouse_month_from_date = frappe.utils.add_months(self.from_date, -1)
			previous_month_end_date = frappe.utils.add_months(self.to_date, -1)
			# frappe.msgprint(str(previouse_month_from_date))
			# frappe.msgprint(str(previous_month_end_date))
			filters = [
				["date_of_joining", "Between", [previouse_month_from_date, previous_month_end_date]],
				["status", "=", "Active"]
			]
			if self.employee:
				filters.append(["name", "=", self.employee])
			new_employee = frappe.get_all("Employee", filters=filters)

			filter_employee = []
			for emp in new_employee:
				emp_arrears_exit = self.get_employee_arrears(emp.name, self.from_date, self.to_date, self.salary_component)
				if not emp_arrears_exit:
					filter_employee.append(emp)

			for emp in filter_employee:
				if (not frappe.db.exists("Salary Slip", {
					"employee": emp.name,
					"start_date": previouse_month_from_date,
					"end_date": previous_month_end_date,
				})) and frappe.db.exists("Salary Structure Assignment", {
					"employee": emp.name,
					"from_date": ["Between", [previouse_month_from_date, previous_month_end_date]],
					"company": self.company,
					"docstatus": 1
				}):
					default_salary = self.get_salary_slip(emp.name, previouse_month_from_date, previous_month_end_date)
					# frappe.msgprint(str(default_salary.start_date))
					# frappe.msgprint(str(default_salary.end_date))
					# frappe.msgprint(str(default_salary.custom_payment_day))
					# frappe.msgprint(str(default_salary.custom_base))
					total_basic = 0
					for x in self.a_p_earnings:
						for d in default_salary.earnings:
							if x.salary_component == d.salary_component:
								total_basic = total_basic + d.amount
							
					arrears_basic = total_basic
					# frappe.msgprint(str(arrears_basic))
					if emp.name in [row.employee for row in self.arrear_process_detail]:
						for row in self.arrear_process_detail:
							if row.employee == emp.name:
								row.to = self.to_date
								row.amount = arrears_basic
								break
					else:
						self.append("arrear_process_detail", {
							"employee": emp.name,
							"to": self.to_date,
							"amount": arrears_basic
						})
		
						


	def on_submit(self):
		if not self.for_new_employees:
			if self.arrear_process_detail:
				for emp in self.arrear_process_detail:
					salary_structure_assignment_list = frappe.get_all(
						"Salary Structure Assignment",
						filters=[
							["employee", "=", emp.employee],
							["from_date", ">", self.from_date],
							["from_date", "<=", self.to_date],
							["docstatus", "=", 1]
						],
						fields=['name', 'from_date', 'base'],
						order_by="from_date desc"
					)
					if not salary_structure_assignment_list:
						continue

					salary_structure_assignment = salary_structure_assignment_list[0]
				
					default_salary = self.get_salary_slip(emp.employee, self.from_date, self.to_date)
					s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
						"employee": emp.employee,
						"from_date": ["<", salary_structure_assignment.from_date],
						"docstatus": 1
					}, order_by="from_date desc")

					# per_day = s_s_assignment.base / first_salary.custom_payment_day
					# default_salary.custom_payment_day =  first_salary.custom_payment_day - absent_days
					default_salary.custom_base = s_s_assignment.base
					# default_salary.custom_absent_deduction = per_day * absent_days
					default_salary.custom_monthly_salary = s_s_assignment.base
					# default_salary.payment_days =  first_salary.payment_days - absent_days
					default_salary.calculate_net_pay()
					# frappe.msgprint('default_salary: ' + str(default_salary.net_pay))

					absent_days = frappe.utils.date_diff(self.to_date, add_days(salary_structure_assignment.from_date, -1))
					# frappe.msgprint('absent_days: ' + str(absent_days))
					# frappe.msgprint(str(add_days(salary_structure_assignment.from_date, -1)))
					first_salary = self.get_salary_slip(emp.employee, self.from_date, add_days(salary_structure_assignment.from_date, -1), absent_days)
					
					# s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
					# 	"employee": emp.employee,
					# 	"from_date": ["<=", self.from_date],
					# 	"docstatus": 1
					# })
					# frappe.msgprint('s_s_assignment: ' + str(s_s_assignment))
					per_day = s_s_assignment.base / first_salary.custom_payment_day
					first_salary.custom_payment_day =  first_salary.custom_payment_day - absent_days
					first_salary.custom_base = per_day * first_salary.custom_payment_day
					first_salary.custom_absent_deduction = per_day * absent_days
					first_salary.custom_monthly_salary = s_s_assignment.base
					first_salary.payment_days =  first_salary.payment_days - absent_days
					first_salary.calculate_net_pay()
					# frappe.msgprint('first_salary: ' + str(first_salary.net_pay))
					
					
					second_salary = self.get_salary_slip(emp.employee, salary_structure_assignment.from_date, self.to_date)
					absent_days = frappe.utils.date_diff(salary_structure_assignment.from_date, self.from_date)
					
					# frappe.msgprint('absent_days: ' + str(absent_days))
					# s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
					# 	"employee": emp.employee,
					# 	"from_date": ["<=", salary_structure_assignment.from_date],
					# 	"docstatus": 1
					# })
					# frappe.msgprint('salary_structure_assignment: ' + str(salary_structure_assignment))
					per_day = salary_structure_assignment.base / second_salary.custom_payment_day
					second_salary.custom_payment_day =  second_salary.custom_payment_day - (absent_days)
					second_salary.custom_base = per_day * second_salary.custom_payment_day
					second_salary.custom_absent_deduction = per_day * (absent_days)
					second_salary.custom_monthly_salary = salary_structure_assignment.base
					second_salary.payment_days =  second_salary.payment_days - (absent_days)
					second_salary.calculate_net_pay() 
						
						
					emp_arrears = frappe.get_doc({
						"doctype": "Employee Arrears",
						"employee": emp.employee,
						"from_date": self.from_date,
						"to_date": self.to_date,
						"earning_component": self.salary_component,
						"arrears_process": self.name
					})  
					earn_existing = []
					deduct_existing = []
					for x in self.a_p_earnings:
						if not x.salary_component in earn_existing:
							earn_existing.append(x.salary_component)
							emp_arrears.append("e_a_earnings", {
								"salary_component": x.salary_component,
								"amount": 0
							})

					for x in self.a_p_deductions:
						if not x.salary_component in deduct_existing:
							deduct_existing.append(x.salary_component)
							emp_arrears.append("e_a_deductions", {
								"salary_component": x.salary_component,
								"amount": 0
							})

					em_arr_total_earning = 0
					for f_salary in first_salary.earnings:
						for s_salary in second_salary.earnings:
							for d_salary in default_salary.earnings:
								for c_salary in emp_arrears.e_a_earnings:
									if f_salary.salary_component == s_salary.salary_component == d_salary.salary_component == c_salary.salary_component:
										arrears_basic = (s_salary.amount + f_salary.amount) - d_salary.amount
										c_salary.amount = abs(arrears_basic)
										em_arr_total_earning =  em_arr_total_earning + c_salary.amount
										break
					
					emp_arrears.total_earning = em_arr_total_earning

					em_arr_total_deduction = 0
					for c_salary in emp_arrears.e_a_deductions:
						arrears_basic = 0
						for f_salary in first_salary.deductions:
							if f_salary.salary_component == c_salary.salary_component:
								arrears_basic += f_salary.amount
								break

						for s_salary in second_salary.deductions:
							if s_salary.salary_component == c_salary.salary_component:
								arrears_basic += s_salary.amount
								break

						for d_salary in default_salary.deductions:
							if d_salary.salary_component == c_salary.salary_component:
								arrears_basic -= d_salary.amount
								break
						c_salary.amount = abs(arrears_basic)
						em_arr_total_deduction = em_arr_total_deduction + c_salary.amount

					emp_arrears.total_deduction = em_arr_total_deduction
					emp_arrears_exit = self.get_employee_arrears(emp.employee, self.from_date, self.to_date, self.salary_component)
					if not emp_arrears_exit:
						emp_arrears.docstatus = 1
						emp_arrears.insert(ignore_permissions=True)


		if self.for_new_employees:
			previouse_month_from_date = frappe.utils.add_months(self.from_date, -1)
			previous_month_end_date = frappe.utils.add_months(self.to_date, -1)

			for emp in self.arrear_process_detail:
				if (not frappe.db.exists("Salary Slip", {
					"employee": emp.employee,
					"start_date": previouse_month_from_date,
					"end_date": previous_month_end_date,
				})) and frappe.db.exists("Salary Structure Assignment", {
					"employee": emp.employee,
					"from_date": ["Between", [previouse_month_from_date, previous_month_end_date]],
					"company": self.company,
					"docstatus": 1
				}):
					default_salary = self.get_salary_slip(emp.employee, previouse_month_from_date, previous_month_end_date)
							
					emp_arrears = frappe.get_doc({
						"doctype": "Employee Arrears",
						"employee": emp.employee,
						"from_date": self.from_date,
						"to_date": self.to_date,
						"earning_component": self.salary_component,
						"arrears_process": self.name,
						"docstatus": 1,
					})  
					earn_existing = []
					deduct_existing = []
					for x in self.a_p_earnings:
						if not x.salary_component in earn_existing:
							earn_existing.append(x.salary_component)
							emp_arrears.append("e_a_earnings", {
								"salary_component": x.salary_component,
								"amount": 0
							})

					for x in self.a_p_deductions:
						if not x.salary_component in deduct_existing:
							deduct_existing.append(x.salary_component)
							emp_arrears.append("e_a_deductions", {
								"salary_component": x.salary_component,
								"amount": 0
							})

					em_arr_total_earning = 0
					for c_salary in emp_arrears.e_a_earnings:
						for d_salary in default_salary.earnings:
							if d_salary.salary_component == c_salary.salary_component:
								c_salary.amount = d_salary.amount
								em_arr_total_earning =  em_arr_total_earning + c_salary.amount
								break
					
					emp_arrears.total_earning = em_arr_total_earning

					em_arr_total_deduction = 0
					for c_salary in emp_arrears.e_a_deductions:
						for d_salary in default_salary.deductions:
							if d_salary.salary_component == c_salary.salary_component:
								arrears_basic = d_salary.amount
								c_salary.amount = abs(arrears_basic)
								em_arr_total_deduction = em_arr_total_deduction + c_salary.amount
								break

					emp_arrears.total_deduction = em_arr_total_deduction
					emp_arrears_exit = self.get_employee_arrears(emp.employee, self.from_date, self.to_date, self.salary_component)
					if not emp_arrears_exit:
						emp_arrears.insert(ignore_permissions=True)
