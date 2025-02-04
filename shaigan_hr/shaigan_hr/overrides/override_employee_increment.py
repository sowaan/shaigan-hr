import frappe
from datetime import datetime
from sowaan_hr.sowaan_hr.doctype.employee_increment.employee_increment import EmployeeIncrement
from frappe.utils import now, add_days, flt


class OverrideEmployeeIncrement(EmployeeIncrement):
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

	def on_submit(self):
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
				"employee": self.employee,
				"docstatus": 1
			})

		if salary_slip:
			arr_process_setting = frappe.get_doc("Arrears Process Setting")

			start_date = frappe.db.get_value("Salary Slip", salary_slip, "start_date")
			end_date = frappe.db.get_value("Salary Slip", salary_slip, "end_date")
			posting_date = frappe.db.get_value("Salary Slip", salary_slip, "posting_date")

			last_salary_slip = self.get_salary_slip(self.employee, start_date, end_date)


			end_date_ = add_days(self.increment_date, -1)
			curr_basic = 0
			for x in last_salary_slip.earnings:
				for c_salary in arr_process_setting.earnings:
					if x.salary_component == c_salary.salary_component:
						curr_basic = curr_basic + x.amount

			monthly_salary, old_days, new_days = calculate_salary_by_dates(self.current_salary, self.revised_salary, str(start_date), str(end_date), str(self.increment_date))

			print(monthly_salary, old_days, new_days, "monthly_salary, old_days, new_days \n\n\n")
			print(curr_basic, self.current_salary, self.revised_salary, str(start_date), str(end_date), str(self.increment_date), "params \n\n\n")

			
			salary_slip = self.get_salary_slip(self.employee, start_date, end_date_, new_days)
			per_day = flt(self.current_salary) / 30
			salary_slip.custom_payment_day =  flt(salary_slip.custom_payment_day) - flt(new_days)
			salary_slip.absent_days = flt(salary_slip.absent_days) + flt(new_days)
			salary_slip.custom_base = flt(per_day) * flt(salary_slip.custom_payment_day)
			salary_slip.custom_absent_deduction = flt(per_day) * flt(salary_slip.absent_days)
			salary_slip.custom_monthly_salary = self.current_salary
			# salary_slip.payment_days =  salary_slip.payment_days - new_days
			salary_slip.calculate_net_pay()
			print("start Date", start_date, "end date", end_date_, "salary_slip.earnings \n\n\n\n", salary_slip.custom_payment_day, salary_slip.payment_days, salary_slip.custom_base, " first slary base\n\n")


			salary_slip1 = self.get_salary_slip(self.employee, self.increment_date, end_date, old_days)
			per_day = flt(self.revised_salary) / 30
			salary_slip1.custom_payment_day =  flt(salary_slip1.custom_payment_day) - flt(old_days)
			salary_slip1.absent_days = flt(salary_slip1.absent_days) + flt(old_days)
			salary_slip1.custom_base = flt(per_day) * flt(salary_slip1.custom_payment_day)
			salary_slip1.custom_absent_deduction = flt(per_day) * flt(salary_slip1.absent_days)
			salary_slip1.custom_monthly_salary = self.revised_salary
			# salary_slip1.payment_days =  salary_slip1.payment_days - old_days
			salary_slip1.calculate_net_pay()   
			print("start Date", self.increment_date, "end date", end_date, "salary_slip.earnings \n\n\n\n", salary_slip1.custom_payment_day, salary_slip1.payment_days, salary_slip1.custom_base, " Second slary base\n\n")

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
					"docstatus": 1
				})  
			

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
								c_salary.amount = arrears_basic

								break
			print(total_earning, "Total Earning \n\n\n\n")
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

			emp_arrears.total_earning = total_earning
			emp_arrears.total_deduction = total_deduction
			emp_arrears.insert(ignore_permissions=True)
			
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
			arears_amount = total_basic - curr_basic
			
			arrears = frappe.get_doc({
				"doctype": "Arrears Process",
				"salary_component": self.arrears_salary_component,
				"employee": self.employee,
				"from_date": from_date,
				"to_date": end_date["end_date"],
				"company": self.company,
				"docstatus": 1,
				"employee_increment": self.name
			})

			arrears.append("arrear_process_detail", {
				"employee": self.employee,
				"amount": arears_amount,
				"to": end_date["end_date"]
			})
			print(arears_amount, total_basic, curr_basic, sal_2_basic, sal_1_basic, "arears_amount \n\n\n\n")
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