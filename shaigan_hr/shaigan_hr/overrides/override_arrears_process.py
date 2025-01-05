import frappe
from frappe.utils import now, add_days
from sowaan_hr.sowaan_hr.doctype.arrears_process.arrears_process import ArrearsProcess

class OverrideArrearsProcess(ArrearsProcess):
	def validate_arrears_process(self):
		filters = []
		employees_list = []
		if self.employee:
			filters = [
				["from_date", ">", self.from_date],
				["from_date", "<=", self.to_date],
				["docstatus", "=", 1]
			]
			filters.append(["employee", "=", self.employee])
			if self.company:
				filters.append(["company", "=", self.company])

			if self.department:
				filters.append(["department", "=", self.department])

			employees_list = frappe.get_all(
				"Salary Structure Assignment",
				filters=filters,
				fields=['employee'],
				distinct=True
			)

		else:
			filters = [
				["increment_date", ">", self.from_date],
				["increment_date", "<=", self.to_date],
				["docstatus", "=", 1]
			]

			if self.company:
				filters.append(["company", "=", self.company])

			if self.department:
				filters.append(["department", "=", self.department])
				


			employees_list = frappe.get_all(
				"Employee Increment",
				filters=filters,
				fields=['employee'],
				distinct=True
			)

		print(employees_list, "employees_list \n\n\n\n")

		if employees_list:
			employees_done = []
			for emp in employees_list:
				employee_status = frappe.db.get_value("Employee", emp.employee, "status")
				if employee_status == "Active" and emp.employee in employees_done:
					continue

				employees_done.append(emp.employee)
				
				salary_structure_assignment_list = frappe.get_all("Salary Structure Assignment",
						filters=[
							["employee","=", emp.employee],
							["from_date",">", self.from_date],
							["from_date","<=", self.to_date]
						],
						fields = ['name'],
				)
				if not salary_structure_assignment_list:
					continue

				salary_structure_assignment = frappe.get_doc(
					"Salary Structure Assignment", 
					salary_structure_assignment_list[0].name
				)
			
				default_salary = frappe.get_doc({
					"doctype": 'Salary Slip',
					"employee": emp.employee,
					"posting_date": self.to_date,
					"payroll_frequency": "",
					"start_date": self.from_date,
					"end_date": self.to_date,
					"docstatus": 0
				})
				default_salary.validate()

				absent_days = frappe.utils.date_diff(self.to_date, add_days(salary_structure_assignment.from_date, -1)) 
				# print(absent_days, self.to_date, salary_structure_assignment.from_date, "absent_days \n\n\n\n")
				first_salary = frappe.get_doc({
					"doctype": 'Salary Slip',
					"employee": emp.employee,
					"posting_date": add_days(salary_structure_assignment.from_date, -1),
					"payroll_frequency": "",
					"start_date": self.from_date,
					"end_date": add_days(salary_structure_assignment.from_date, -1),
					"absent_days": absent_days,
					"docstatus": 0
				})
				first_salary.validate()
				
				s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
					"employee": emp.employee,
					"from_date": ["<=", self.from_date],
					"docstatus": 1
				})
				# print(employee_status, allow_manual_att, emp.employee, self.from_date, "Check filters \n\n\n\n")
				per_day = s_s_assignment.base / first_salary.custom_payment_day
				first_salary.custom_payment_day =  first_salary.custom_payment_day - absent_days
				first_salary.custom_base = per_day * first_salary.custom_payment_day
				first_salary.custom_absent_deduction = per_day * absent_days
				first_salary.custom_monthly_salary = s_s_assignment.base
					# print(per_day, first_salary.custom_payment_day, absent_days, s_s_assignment.base, "First Salary per_day \n\n\n\n")
				first_salary.payment_days =  first_salary.payment_days - absent_days
				first_salary.calculate_net_pay()
				
				sal_1_basic = 0
				for x in first_salary.earnings:
					sal_1_basic = sal_1_basic + x.amount
				
				
				second_salary = frappe.get_doc({
					"doctype": 'Salary Slip',
					"employee": emp.employee,
					"posting_date": self.to_date,
					"payroll_frequency": "",
					"start_date": salary_structure_assignment.from_date,
					"end_date": self.to_date,
					"docstatus": 0
				})
				second_salary.validate() 
				
				absent_days = frappe.utils.date_diff(salary_structure_assignment.from_date, self.from_date) 
				s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
					"employee": emp.employee,
					"from_date": ["<=", salary_structure_assignment.from_date],
					"docstatus": 1
				})
				per_day = s_s_assignment.base / second_salary.custom_payment_day
				second_salary.custom_payment_day =  second_salary.custom_payment_day - absent_days
				second_salary.custom_base = per_day * second_salary.custom_payment_day
				second_salary.custom_absent_deduction = per_day * absent_days
				second_salary.custom_monthly_salary = s_s_assignment.base
				# print(per_day, second_salary.custom_payment_day, absent_days, s_s_assignment.base, "Sec Salary per_day \n\n\n\n")
				second_salary.payment_days =  second_salary.payment_days - absent_days
				second_salary.calculate_net_pay() 
				
				
				sal_2_basic = 0
				for x in second_salary.earnings:
					# if x.salary_component == 'Basic':
					sal_2_basic = sal_2_basic + x.amount
						
				
				curr_basic = 0
				for x in default_salary.earnings:
					# if x.salary_component == 'Basic':
					curr_basic = curr_basic + x.amount
					
					
				total_basic = sal_2_basic + sal_1_basic   
				emp_arrears = frappe.get_doc({
					"doctype": "Employee Arrears",
					"employee": emp.employee,
					"from_date": self.from_date,
					"to_date": self.to_date,
					"earning_component": self.salary_component,
					"docstatus": 1,
					# "arrears_process": self.name
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
									c_salary.amount = arrears_basic
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

					c_salary.amount = arrears_basic
					em_arr_total_deduction = em_arr_total_deduction + c_salary.amount

				emp_arrears.total_deduction = em_arr_total_deduction
				# print(emp_arrears.as_dict(), "emp_arrears \n\n\n\n")
				emp_arrears.insert(ignore_permissions=True)
				arrears_basic = total_basic - curr_basic

				
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

		else:
			if self.employee:
				employee_status = frappe.db.get_value("Employee", self.employee, "status")
				if employee_status != "Active":
					frappe.throw("Employee is not active")
				employee_joining_date = frappe.db.get_value("Employee", self.employee, "date_of_joining")
				previouse_month_from_date = frappe.utils.add_months(self.from_date, -1)
				previous_month_end_date = frappe.utils.add_days(self.to_date, -1)


				default_salary = frappe.get_doc({
						"doctype": 'Salary Slip',
						"employee": self.employee,
						"posting_date": previous_month_end_date,
						"start_date": previouse_month_from_date,
						"end_date": previous_month_end_date,
						"docstatus": 0
					})
				default_salary.validate()
				
				total_basic = 0
				for x in default_salary.earnings:
					# if x.salary_component == 'Basic':
					total_basic = total_basic + x.amount
					  
				emp_arrears = frappe.get_doc({
					"doctype": "Employee Arrears",
					"employee": self.employee,
					"from_date": self.from_date,
					"to_date": self.to_date,
					"earning_component": self.salary_component,
					"docstatus": 1,
					# "arrears_process": self.name
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
							arrears_basic -= d_salary.amount
							c_salary.amount = arrears_basic
							em_arr_total_deduction = em_arr_total_deduction + c_salary.amount
							break

				emp_arrears.total_deduction = em_arr_total_deduction
				# print(emp_arrears.as_dict(), "emp_arrears \n\n\n\n")
				emp_arrears.insert(ignore_permissions=True)
				arrears_basic = total_basic

				
				self.append("arrear_process_detail", {
					"employee": self.employee,
					"to": self.to_date,
					"amount": arrears_basic
				})
					

