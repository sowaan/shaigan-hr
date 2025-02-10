import frappe
from datetime import datetime
from frappe.utils import now, add_days, date_diff, flt
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
				["increment_date", ">", self.from_date],
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
					
					salary_structure_assignment_list = frappe.get_all("Salary Structure Assignment",
							filters=[
								["employee","=", emp.employee],
								["from_date",">", self.from_date],
								["from_date","<=", self.to_date]
							],
							fields=['name'],
					)
					if not salary_structure_assignment_list:
						continue

					salary_structure_assignment = frappe.get_doc(
						"Salary Structure Assignment", 
						salary_structure_assignment_list[0].name
					)
				
					default_salary = self.get_salary_slip(emp.employee, self.from_date, self.to_date)

					monthly_salary, old_days, new_days = calculate_salary_by_dates(default_salary.custom_base, salary_structure_assignment.base, str(self.from_date), str(self.to_date), str(salary_structure_assignment.from_date))

					# print(monthly_salary, old_days, new_days, "monthly_salary, old_days, new_days \n\n\n")
					# absent_days = frappe.utils.date_diff(self.to_date, add_days(salary_structure_assignment.from_date, -1)) 
					first_salary = self.get_salary_slip(emp.employee, self.from_date, add_days(salary_structure_assignment.from_date, -1), new_days)
					s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
						"employee": emp.employee,
						"from_date": ["<=", self.from_date],
						"docstatus": 1
					})
					per_day = flt(s_s_assignment.base) / 30
					first_salary.custom_payment_day =  flt(first_salary.custom_payment_day) - new_days
					first_salary.absent_days = flt(first_salary.absent_days) + flt(new_days)
					first_salary.custom_base = per_day * flt(first_salary.custom_payment_day)
					first_salary.custom_absent_deduction = flt(per_day) * flt(first_salary.absent_days)
					first_salary.custom_monthly_salary = s_s_assignment.base
					first_salary.calculate_net_pay()
					
					sal_1_basic = 0
					for x in first_salary.earnings:
						for d in self.a_p_earnings:
							if x.salary_component == d.salary_component:
								sal_1_basic = sal_1_basic + x.amount
					
					
					second_salary = self.get_salary_slip(emp.employee, salary_structure_assignment.from_date, self.to_date)
					# absent_days = frappe.utils.date_diff(salary_structure_assignment.from_date, self.from_date) 
					print(salary_structure_assignment.from_date, self.to_date,old_days, "Salary Slip \n\n\n\n\n\n\n")
					s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
						"employee": emp.employee,
						"from_date": ["<=", salary_structure_assignment.from_date],
						"docstatus": 1
					})
					per_day = s_s_assignment.base / 30
					second_salary.custom_payment_day =  flt(second_salary.custom_payment_day) - flt(old_days)
					second_salary.absent_days = flt(second_salary.absent_days) + flt(old_days)
					second_salary.custom_base = per_day * flt(second_salary.custom_payment_day)
					second_salary.custom_absent_deduction = flt(per_day) * flt(second_salary.absent_days)
					second_salary.custom_monthly_salary = s_s_assignment.base
					second_salary.calculate_net_pay() 
					
					
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


		if self.for_new_employees:
			previouse_month_from_date = frappe.utils.add_months(self.from_date, -1)
			previous_month_end_date = frappe.utils.add_months(self.to_date, -1)
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
					print(default_salary, previouse_month_from_date, previous_month_end_date, "Salary slip \n\n\n\n\n")
					total_basic = 0
					for x in self.a_p_earnings:
						for d in default_salary.earnings:
							if x.salary_component == d.salary_component:
								total_basic = total_basic + d.amount
							
					arrears_basic = total_basic
					if emp.name in [row.employee for row in self.arrear_process_detail]:
						for row in self.arrear_process_detail:
							if row.employee == emp.name:
								# If the condition is true, update the row
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
				
					default_salary = self.get_salary_slip(emp.employee, self.from_date, self.to_date)
					monthly_salary, old_days, new_days = calculate_salary_by_dates(default_salary.custom_base, salary_structure_assignment.base, str(self.from_date), str(self.to_date), str(salary_structure_assignment.from_date))
					# absent_days = frappe.utils.date_diff(self.to_date, add_days(salary_structure_assignment.from_date, -1))
					first_salary = self.get_salary_slip(emp.employee, self.from_date, add_days(salary_structure_assignment.from_date, -1), new_days)
					s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
						"employee": emp.employee,
						"from_date": ["<=", self.from_date],
						"docstatus": 1
					})
					per_day = flt(s_s_assignment.base) / 30
					first_salary.custom_payment_day =  flt(first_salary.custom_payment_day) - new_days
					first_salary.absent_days = flt(first_salary.absent_days) + flt(new_days)
					first_salary.custom_base = per_day * flt(first_salary.custom_payment_day)
					first_salary.custom_absent_deduction = flt(per_day) * flt(first_salary.absent_days)
					first_salary.custom_monthly_salary = s_s_assignment.base
					first_salary.calculate_net_pay()
					
					
					second_salary = self.get_salary_slip(emp.employee, salary_structure_assignment.from_date, self.to_date)
					# absent_days = frappe.utils.date_diff(salary_structure_assignment.from_date, self.from_date) 
					s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
						"employee": emp.employee,
						"from_date": ["<=", salary_structure_assignment.from_date],
						"docstatus": 1
					})
					per_day = s_s_assignment.base / 30
					second_salary.custom_payment_day =  flt(second_salary.custom_payment_day) - flt(old_days)
					second_salary.absent_days = flt(second_salary.absent_days) + flt(old_days)
					second_salary.custom_base = per_day * flt(second_salary.custom_payment_day)
					second_salary.custom_absent_deduction = flt(per_day) * flt(second_salary.absent_days)
					second_salary.custom_monthly_salary = s_s_assignment.base
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
								c_salary.amount = arrears_basic
								em_arr_total_deduction = em_arr_total_deduction + c_salary.amount
								break

					emp_arrears.total_deduction = em_arr_total_deduction
					emp_arrears_exit = self.get_employee_arrears(emp.employee, self.from_date, self.to_date, self.salary_component)
					if not emp_arrears_exit:
						emp_arrears.insert(ignore_permissions=True)


def calculate_salary_by_dates(old_salary, new_salary, start_date_str, end_date_str, increment_date_str):
    # Convert strings to date objects
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    increment_date = datetime.strptime(increment_date_str, "%Y-%m-%d")

    # Total number of days in the payroll period
    total_days = (end_date - start_date).days + 1

    # Ensure the total days do not exceed 30
    if total_days < 30:
        total_days = 30  # If total days is less than 30, adjust to 30
    
    # Days in old salary
    new_salary_days = ((end_date - increment_date).days + 1) if end_date > increment_date else 1
    if new_salary_days > 30:
        new_salary_days = 30  # If new salary days exceed 30, adjust to 30
    old_salary_days = (increment_date - start_date).days if increment_date > start_date else 0
    print(f"New Salary Days: {new_salary_days}")
    print(f"Old Salary Days: {old_salary_days}")
    if old_salary_days > 0 and new_salary_days == 30:
        new_salary_days = new_salary_days - old_salary_days
    # Adjust for the last day increment and ensure total days are 30
    if increment_date == end_date and old_salary_days > 29:
        old_salary_days = 29  # 29 days for old salary
        new_salary_days = 1   # 1 day for new salary
    else:
        print(f"Total Days: {total_days}")
        # new_salary_days = total_days - old_salary_days
        old_salary_days = total_days - new_salary_days

    # If total_days is more than 30, adjust 1 day to the new salary
    if total_days > 30:
        print(f"Total Days old under: {old_salary_days} {(increment_date - start_date).days}")
        if new_salary_days > old_salary_days and (increment_date - start_date).days + new_salary_days > 30:
            old_salary_days = old_salary_days
            new_salary_days = 30 - old_salary_days
        old_salary_days = 30 - new_salary_days
        # new_salary_days = 30 - old_salary_days
    elif total_days < 30:
        print("Total days should be 30 or more")
        new_salary_days += 1

    # Daily wages
    daily_old = old_salary / 30  # assuming 30 days in a month
    daily_new = new_salary / 30

    # Salary calculation
    old_salary_part = daily_old * old_salary_days
    new_salary_part = daily_new * new_salary_days

    total_salary = old_salary_part + new_salary_part
    return round(total_salary, 2), old_salary_days, new_salary_days
