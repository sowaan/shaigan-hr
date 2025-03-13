import frappe
from frappe import _
from frappe.utils import  flt,get_link_to_form,getdate,date_diff,add_days,add_months,get_first_day,get_last_day
from hrms.payroll.doctype.additional_salary.additional_salary import AdditionalSalary




class OverrideAdditionalSalary(AdditionalSalary):
        
        def before_save(self):
            
        

            if self.custom_is_prorated:  
                self.amount = self.calculate_prorated_salary()

            if self.amount < 0:
                frappe.throw(_("Amount should not be less than zero"))
        

        def calculate_prorated_salary(self):
             
             
                        
            payroll_date = getdate(self.payroll_date)
            cutoff_date = payroll_date.replace(day=25)
            remaining_days = date_diff(cutoff_date, payroll_date) + 1

            # Calculate prorated amount using amount/30 * remaining_days
            per_day_salary = flt(self.amount) / 30
            prorated_amount = flt(per_day_salary * remaining_days)

            return prorated_amount