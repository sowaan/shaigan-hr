# Copyright (c) 2024, Sowaan and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from shaigan_hr.shaigan_hr.overrides.quarter_leave_application import get_leave_details






def create_system_generated_quarter_leaves(att_doc, leave_type, sch_doc):
	la_doc = frappe.get_doc({
				"doctype": "Leave Application",
				"employee": att_doc.employee ,
				"leave_type" : leave_type ,
				"from_date": att_doc.attendance_date ,
				"to_date": att_doc.attendance_date ,
				"custom_system_generated" : 1 ,
                "custom_monthly_leave_scheduler" : sch_doc.name ,
				"custom_quarter_day": 1 ,
				"total_leave_days" : 0.25 ,
				"status": "Approved",
				"docstatus": 0 ,
			 })
	la_doc.insert()
	la_doc.submit()
				


def check_and_create_quarter_leaves(doc):
    emp_list = frappe.get_list("Employee", filters={'status': 'Active'})

    if emp_list:
        for emp in emp_list:
            att_list = frappe.get_list("Attendance", 
                                        filters={
                                            'employee': emp.name,
                                            'attendance_date': ['Between', [doc.from_date, doc.to_date]],
                                            'custom_attendance_status': ['in', ['3 Quarters', 'Half Day']],
                                            'docstatus': 1,
                                        },
                                        order_by='attendance_date')

            if att_list:
                for att in att_list:
                    att_doc = frappe.get_doc("Attendance", att.name)
                    t_req = 0
                    req = 0
                    table_length = len(att_doc.custom_quarter_leaves)

                    if table_length > 2:
                        table_length = 2

                    if att_doc.custom_attendance_status == 'Half Day':
                        t_req = 2
                    elif att_doc.custom_attendance_status == '3 Quarters':
                        t_req = 1	

                    if att_doc.custom_attendance_status in ['Half Day', '3 Quarters']:
                        req = t_req - table_length

                        while req > 0:
                            req -= 1
                            leave_details_list = get_leave_details(att_doc.employee, att_doc.attendance_date)
                            leave_details = leave_details_list["leave_allocation"]

                            if leave_details:
                                leave_type = None
                                if "Casual Leave" in leave_details and leave_details["Casual Leave"]["remaining_leaves"] >= 0.25:
                                    leave_type = "Casual Leave"
                                elif "Sick Leave" in leave_details and leave_details["Sick Leave"]["remaining_leaves"] >= 0.25:
                                    leave_type = "Sick Leave"
                                else:
                                    leave_type = "Leave Without Pay"

                                create_system_generated_quarter_leaves(att_doc, leave_type, doc)


                                








class MonthlyLeaveScheduler(Document):

    def before_save(self):
        if self.from_date > self.to_date:
            frappe.throw("'To Date' must be greater than 'From Date'.")
        # enqueue(check_and_create_quarter_leaves, doc=self, queue="default") 

    def before_submit(self):
        # frappe.throw("yo")
        # check_and_create_quarter_leaves(self)
        enqueue(check_and_create_quarter_leaves, doc=self, queue="default")

    def before_cancel(self):
        la_list = frappe.get_list("Leave Application",
                    filters={
                        'custom_monthly_leave_scheduler': self.name,
                        'docstatus': 1,
                    })
        if la_list:
            for la in la_list:
                la_doc = frappe.get_doc("Leave Application", la.name)
                la_doc.cancel()