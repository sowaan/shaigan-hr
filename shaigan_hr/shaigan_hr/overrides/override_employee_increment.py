import frappe
from datetime import datetime
from sowaan_hr.sowaan_hr.doctype.employee_increment.employee_increment import EmployeeIncrement
from frappe.utils import now, add_days


class OverrideEmployeeIncrement(EmployeeIncrement):
	def before_save(self):
		salary_sturcture = self.get_structure_asignment()
		tax_slab = frappe.get_last_doc("Income Tax Slab", filters={
			"company": self.company,
			"disabled": 0,
			"docstatus": 1,
			"currency": salary_sturcture.currency
		})
		
		salary_sturcture = frappe.get_doc({
			"doctype": "Salary Structure Assignment",
			"employee": self.employee,
			"from_date": self.increment_date,
			"salary_structure": salary_sturcture.salary_structure,
			"company": self.company,
			"payroll_payable_account": salary_sturcture.payroll_payable_account,
			"currency": salary_sturcture.currency,
			"income_tax_slab": tax_slab.name,
			"base": self.revised_salary,
			"docstatus": 1,
			"employee_increment": self.name
		})
		salary_sturcture.insert(ignore_permissions=True)

		arrears_setting = frappe.get_doc("Arrears Process Setting")
		salary_slip = frappe.db.exists("Salary Slip", {
				"start_date": ["<=", self.increment_date],
				"end_date": [">=", self.increment_date],
				"employee": self.employee
			})

		if salary_slip:
			start_date = frappe.db.get_value("Salary Slip", salary_slip, "start_date")
			end_date = frappe.db.get_value("Salary Slip", salary_slip, "end_date")
			posting_date = frappe.db.get_value("Salary Slip", salary_slip, "posting_date")

			last_salary_slip = frappe.get_doc({
				"doctype": 'Salary Slip',
				"employee": self.employee,
				"posting_date": posting_date,
				"payroll_frequency": "",
				"start_date": start_date,
				"end_date": end_date
			})
			last_salary_slip.validate()

			end_date_ = add_days(self.increment_date, -1)
			print(end_date_, "end_date_ \n\n\n\n")

			curr_basic = 0
			for x in last_salary_slip.earnings:
				# if x.salary_component == 'Basic':
				curr_basic = curr_basic + x.amount
			print(curr_basic, "curr_basic \n\n\n\n")
			salary_slip = frappe.get_doc({
				"doctype": "Salary Slip",
				"employee": self.employee,
				"posting_date": now(),
				"payroll_frequency": last_salary_slip.payroll_frequency,
				"salary_structure": salary_sturcture.salary_structure,
				"start_date": start_date,
				"end_date": end_date_,
				"company": self.company
			})
			salary_slip.validate()
			print(salary_slip.custom_base, "base \n\n\n\n")
			absent_days_first = frappe.utils.date_diff(end_date, end_date_)
			absent_days_second = frappe.utils.date_diff(end_date_, start_date)
			date_diff = absent_days_first + absent_days_second
			from_date = str(self.increment_date)
			day_of_from_date = datetime.strptime(from_date, "%Y-%m-%d").day
			frappe.msgprint(str(absent_days_first))
			frappe.msgprint(str(absent_days_second))
			if day_of_from_date in [26, 27, 28, 29, 30, 31]:
				# frappe.throw(f"sa {salary_structure_assignment.from_date}")
				# frappe.msgprint("if")
				# frappe.msgprint(from_date)
				
				if date_diff > 30:
					absent_days_first = absent_days_first - (date_diff - 30)
				elif date_diff < 30:
					absent_days_first = absent_days_first + (30 - date_diff)
			else:
				# frappe.msgprint("else")
				# frappe.msgprint(from_date)
				if date_diff > 30:
					absent_days_second = absent_days_second - (date_diff - 30)
				elif date_diff < 30:
					absent_days_second = absent_days_second + (30 - date_diff)
			frappe.msgprint(str(absent_days_first))
			frappe.msgprint(str(absent_days_second))

			print(absent_days_first, "absent_days \n\n\n\n")
		# 	if  allow_manual_att == "Yes":
			s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
				"employee": self.employee,
				"from_date": ["<=", start_date],
				"docstatus": 1
			}, order_by="from_date desc")
			per_day = s_s_assignment.base / salary_slip.custom_payment_day
			salary_slip.custom_payment_day =  salary_slip.custom_payment_day - absent_days_first
			salary_slip.custom_base = per_day * salary_slip.custom_payment_day
			salary_slip.custom_absent_deduction = per_day * absent_days_first
			salary_slip.custom_monthly_salary = s_s_assignment.base
			# print(per_day, salary_slip.custom_payment_day, absent_days, s_s_assignment.base, "old Salary per_day \n\n\n\n")
			salary_slip.payment_days =  salary_slip.payment_days - absent_days_first
			salary_slip.calculate_net_pay()
			# print("start Date", start_date, "end date", end_date_, "salary_slip.earnings \n\n\n\n", salary_slip.custom_payment_day, salary_slip.payment_days, absent_days, salary_slip.custom_base, "\n\n")


			salary_slip1 = frappe.get_doc({
				"doctype": "Salary Slip",
				"employee": self.employee,
				"posting_date": now(),
				"payroll_frequency": last_salary_slip.payroll_frequency,
				"salary_structure": salary_sturcture.salary_structure,
				"start_date": self.increment_date,
				"end_date": end_date,
				"company": self.company
			})
			salary_slip1.validate()
			print(salary_slip1.custom_base, "base \n\n\n\n")

			# absent_days = frappe.utils.date_diff(end_date_, start_date) 
			# frappe.throw(str(absent_days_second))
			
		# 	if  allow_manual_att == "Yes":
			s_s_assignment = frappe.get_last_doc("Salary Structure Assignment", filters={
				"employee": self.employee,
				"from_date": ["<=", self.increment_date],
				"docstatus": 1
			}, order_by="from_date desc")

			per_day = s_s_assignment.base / salary_slip1.custom_payment_day
			salary_slip1.custom_payment_day =  salary_slip1.custom_payment_day - absent_days_second
			salary_slip1.custom_base = per_day * salary_slip1.custom_payment_day
			salary_slip1.custom_absent_deduction = per_day * absent_days_second
			salary_slip1.custom_monthly_salary = s_s_assignment.base
			# print(per_day, salary_slip1.custom_payment_day, absent_days, s_s_assignment.base, "new Salary per_day \n\n\n\n")
			salary_slip1.payment_days =  salary_slip1.payment_days - absent_days_second
			salary_slip1.calculate_net_pay()   
		# 	# print(salary_slip1.as_dict().earnings, "start Date", self.increment_date, "end date", end_date, "salary_slip.earnings \n\n\n\n", salary_slip1.custom_payment_day,salary_slip1.payment_days, absent_days, salary_slip1.custom_base, "\n\n") 
			from_date = add_days(end_date, 1)
			end_date = frappe.call('hrms.payroll.doctype.payroll_entry.payroll_entry.get_end_date', 
				frequency = last_salary_slip.payroll_frequency, 
				start_date = from_date
			)

			emp_arrears = frappe.get_doc({
					"doctype": "Employee Arrears",
					"employee": self.employee,
					"from_date": from_date,
					"to_date": end_date['end_date'],
					"earning_component": self.arrears_salary_component,
					# "docstatus": 1
				})  
			
			arr_process_setting = frappe.get_doc("Arrears Process Setting")

			for x in arr_process_setting.earnings:
				emp_arrears.append("e_a_earnings", {
					"salary_component": x.salary_component,
					"amount": 0
				})

			for x in arr_process_setting.deductions:
				emp_arrears.append("e_a_deductions", {
					"salary_component": x.salary_component,
					"amount": 0
				})
			
			total_earning = 0
			for f_salary in salary_slip.earnings:
				for s_salary in salary_slip1.earnings:
					for d_salary in last_salary_slip.earnings:
						for c_salary in emp_arrears.e_a_earnings:
							if f_salary.salary_component == s_salary.salary_component == d_salary.salary_component == c_salary.salary_component:
								# print(f_salary.salary_component, f_salary.amount, s_salary.amount, d_salary.amount, "f_salary.amount \n\n\n\n")
								arrears_basic = (s_salary.amount + f_salary.amount) - d_salary.amount
								total_earning = total_earning + arrears_basic
								c_salary.amount = abs(arrears_basic)

								break
			
			total_deduction = 0
			for c_salary in emp_arrears.e_a_deductions:
				arrears_basic = 0
				for f_salary in salary_slip.deductions:
					if f_salary.salary_component == c_salary.salary_component:
						arrears_basic += f_salary.amount
						break

				for s_salary in salary_slip1.deductions:
					if s_salary.salary_component == c_salary.salary_component:
						arrears_basic += s_salary.amount
						break

				for d_salary in last_salary_slip.deductions:
					if d_salary.salary_component == c_salary.salary_component:
						arrears_basic -= d_salary.amount
						break
				
				total_deduction = total_deduction + arrears_basic
				c_salary.amount = arrears_basic

			arears_amount = 0
			sal_1_basic = 0

			for x in salary_slip.earnings:
				for y in arrears_setting.earnings:
					if x.salary_component == y.salary_component:
						sal_1_basic = sal_1_basic + x.amount

			sal_2_basic = 0
			for x in salary_slip1.earnings:
				for y in arrears_setting.earnings:
					if x.salary_component == y.salary_component:
						sal_2_basic = sal_2_basic + x.amount

			total_basic = sal_2_basic + sal_1_basic   
			arears_amount = abs(total_basic - curr_basic)
			print(arears_amount, "arears_amount \n\n\n\n")

			emp_arrears.total_earning = total_earning
			emp_arrears.total_deduction = total_deduction
			emp_arrears.insert(ignore_permissions=True)
			
			
			
			arrears = frappe.get_doc({
				"doctype": "Arrears Process",
				"salary_component": self.arrears_salary_component,
				"employee": self.employee,
				"from_date": from_date,
				"to_date": end_date["end_date"],
				"company": self.company,
				# "docstatus": 1,
				"employee_increment": self.name
			})

			arrears.append("arrear_process_detail", {
				"employee": self.employee,
				"amount": arears_amount,
				"to": end_date["end_date"]
			})

			a_p_earn_existing = []
			a_p_deduct_existing = []

			for x in arr_process_setting.earnings:
				if not x.salary_component in a_p_earn_existing:
					a_p_earn_existing.append(x.salary_component)
					arrears.append("a_p_earnings", {
						"salary_component": x.salary_component,
						"amount": 0
					})

			for x in arr_process_setting.deductions:
				if not x.salary_component in a_p_deduct_existing:
					a_p_deduct_existing.append(x.salary_component)
					arrears.append("a_p_deductions", {
						"salary_component": x.salary_component,
						"amount": 0
					})

			arrears.insert(ignore_permissions=True)
			frappe.db.set_value("Employee Arrears", emp_arrears.name, "arrears_process", arrears.name)

	@frappe.whitelist()
	def get_structure_asignment(self):
		get_last_salary_structure = frappe.get_last_doc("Salary Structure Assignment", filters=[
			["employee", "=", self.employee],
			["from_date", "<=", self.increment_date],
			["docstatus", "=", 1]
		], order_by="from_date desc")
		# print(get_last_salary_structure.base)
		# print(get_last_salary_structure, "get_last_salary_structure \n\n\n\n")

		return get_last_salary_structure

