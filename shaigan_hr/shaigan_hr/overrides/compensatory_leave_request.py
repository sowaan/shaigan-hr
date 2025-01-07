from hrms.hr.doctype.compensatory_leave_request.compensatory_leave_request import CompensatoryLeaveRequest
import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, format_date, get_url_to_list, getdate






class OverrideCompensatoryLeaveRequest(CompensatoryLeaveRequest):
    def validate_attendance(doc):
        # pass
        dates = []
        
        if doc.leave_type == "Compensatory Leave":
           
            employee_doc = frappe.get_doc("Employee", doc.employee)
            if employee_doc.custom_overtime_status == "No":
                current_date = doc.work_from_date
                end_date = doc.work_end_date
                
                while current_date <= end_date:
                    dates.append(current_date)
                    current_date = frappe.utils.add_days(current_date, 1)
        
                for date in dates:
                    attendance_doc = frappe.get_doc("Attendance", {"attendance_date": date, "employee": doc.employee})
                    
                    if attendance_doc:
                        if 3 < attendance_doc.working_hours <= 4:
                            doc.half_day = 1
                            doc.half_day_date = doc.work_end_date
                        elif attendance_doc.working_hours > 4:
                            doc.status = "Present"
                        
                        else:
                            frappe.throw("You cannot apply for Compensatory Leave.")
                    else:
                        frappe.throw("Attendance record not found for date: {}".format(date))
            else:
                frappe.throw("Compensatory Leave cannot be applied as Overtime is set to Yes.")