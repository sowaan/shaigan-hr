# Copyright (c) 2024, Sowaan and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, add_days
from frappe.model.document import Document
from frappe.utils.background_jobs import enqueue
from shaigan_hr.shaigan_hr.overrides.quarter_leave_application import get_leave_details



def get_leave_type(employee, attendance_date) :

	leave_details_list = get_leave_details(employee, attendance_date)
	leave_details = leave_details_list["leave_allocation"]

	leave_type = "Leave Without Pay"
	if leave_details:
		if "Casual Leave" in leave_details and leave_details["Casual Leave"]["remaining_leaves"] >= 1:
			leave_type = "Casual Leave"
		elif "Sick Leave" in leave_details and leave_details["Sick Leave"]["remaining_leaves"] >= 1:
			leave_type = "Sick Leave"
		else:
			leave_type = "Leave Without Pay"
	
	return leave_type



def create_system_generated_quarter_leaves(att_doc, leave_type, sch_doc):

	
	la_doc = frappe.get_doc({
		"doctype": "Leave Application",
		"employee": att_doc.employee,
		"leave_type": leave_type,
		"from_date": att_doc.attendance_date,
		"to_date": att_doc.attendance_date,
		"custom_system_generated": 1,
		"custom_monthly_leave_scheduler": sch_doc.name,
		"custom_quarter_day": 1,
		"total_leave_days": 0.25,
		"status": "Approved",
		"docstatus": 0,
	})

	la_doc.insert()
	la_doc.submit()
	if sch_doc.workflow_exist == 1 :
		frappe.db.set_value("Leave Application" , la_doc.name , "workflow_state" , sch_doc.workflow_state)



def create_system_generated_full_leaves(att_doc, leave_type, sch_doc):

	leave_exists = frappe.db.sql("""
		SELECT name
		FROM `tabLeave Application`
		WHERE
			employee = %(employee)s
			AND (
				(from_date <= %(attendance_date)s AND to_date >= %(attendance_date)s)
			)
			AND docstatus != 2
		""",
		{ "employee": att_doc.employee, "attendance_date": att_doc.attendance_date }
	)

	if not leave_exists :
			
		la_doc = frappe.get_doc({
			"doctype": "Leave Application",
			"employee": att_doc.employee,
			"leave_type": leave_type,
			"from_date": att_doc.attendance_date,
			"to_date": att_doc.attendance_date,
			"custom_system_generated": 1,
			"custom_monthly_leave_scheduler": sch_doc.name,
			"total_leave_days": 1,
			"status": "Approved",
			"docstatus": 0,
		})
		
		check_adjacent_leaves(la_doc)
		if str(la_doc.from_date) != str(la_doc.to_date) :
			create_single_leaves(la_doc, sch_doc)

		else :	
			la_doc.insert()
			la_doc.submit()
			if sch_doc.workflow_exist == 1 :
				frappe.db.set_value("Leave Application" , la_doc.name , "workflow_state" , sch_doc.workflow_state)


def create_system_generated_half_leaves(att_doc, leave_type, sch_doc):


	leave_exists = frappe.db.sql("""
		SELECT name
		FROM `tabLeave Application`
		WHERE
			employee = %(employee)s
			AND (
				(from_date <= %(attendance_date)s AND to_date >= %(attendance_date)s)
			)
			AND docstatus != 2
		""",
		{ "employee": att_doc.employee, "attendance_date": att_doc.attendance_date }
	)

	if not leave_exists :

		
		la_doc = frappe.get_doc({
			"doctype": "Leave Application",
			"employee": att_doc.employee,
			"leave_type": leave_type,
			"from_date": att_doc.attendance_date,
			"to_date": att_doc.attendance_date,
			"custom_system_generated": 1,
			"custom_monthly_leave_scheduler": sch_doc.name,
			"half_day": 1,
			"total_leave_days": 0.5,
			"status": "Approved",
			"docstatus": 0,
		})
		
		la_doc.insert()
		la_doc.submit()
		if sch_doc.workflow_exist == 1 :
			frappe.db.set_value("Leave Application" , la_doc.name , "workflow_state" , sch_doc.workflow_state)
		




def check_and_create_quarter_leaves(doc):
	emp_list = frappe.get_list("Employee", filters={'status': 'Active'})

	if emp_list:
		for emp in emp_list:
			att_list = frappe.get_list("Attendance",
									   filters={
										   'employee': emp.name,
										   'attendance_date': ['Between', [doc.from_date, doc.to_date]],
										   'status' : 'Present' ,
										   'custom_quarter' : ['in', ['ONE','TWO']] ,
										   'docstatus': 1,
										   'custom_holiday' : ['!=' , 1] ,
									   },
									   order_by='attendance_date')


			# frappe.msgprint(str(emp_list))
			# if emp.name == 'SPPL-4514' :

				# frappe.msgprint(str(att_list))	

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

							leave_type = "Leave Without Pay"
							if leave_details:
								if "Casual Leave" in leave_details and leave_details["Casual Leave"]["remaining_leaves"] >= 0.25:
									leave_type = "Casual Leave"
								elif "Sick Leave" in leave_details and leave_details["Sick Leave"]["remaining_leaves"] >= 0.25:
									leave_type = "Sick Leave"
								else:
									leave_type = "Leave Without Pay"

							create_system_generated_quarter_leaves(att_doc, leave_type, doc)



def check_and_create_full_and_half_leaves(doc):
	emp_list = frappe.get_list("Employee", filters={'status': 'Active'})
	# frappe.msgprint(str(emp_list))

	if emp_list:

		for emp in emp_list:
			att_list = frappe.get_list("Attendance",
									   filters={
										   'employee': emp.name,
										   'attendance_date': ['Between', [doc.from_date, doc.to_date]],
										   'status' : 'Absent' ,
										   'docstatus': 1,
										   'custom_holiday' : ['!=' , 1] ,
									   },
									   order_by='attendance_date')
				   
			if att_list:
				for att in att_list:
					att_doc = frappe.get_doc("Attendance", att.name)	

					leave_details_list = get_leave_details(att_doc.employee, att_doc.attendance_date)
					leave_details = leave_details_list["leave_allocation"]

					leave_type = "Leave Without Pay"
					if leave_details:
						if "Casual Leave" in leave_details and leave_details["Casual Leave"]["remaining_leaves"] >= 1:
							leave_type = "Casual Leave"
						elif "Sick Leave" in leave_details and leave_details["Sick Leave"]["remaining_leaves"] >= 1:
							leave_type = "Sick Leave"
						else:
							leave_type = "Leave Without Pay"

					create_system_generated_full_leaves(att_doc, leave_type, doc)


			half_att_list = frappe.get_list("Attendance",
									   filters={
										   'employee': emp.name,
										   'attendance_date': ['Between', [doc.from_date, doc.to_date]],
										   'status' : 'Half Day' ,
										   'docstatus': 1,
										   'custom_holiday' : ['!=' , 1] ,
									   },
									   order_by='attendance_date')


					# elif att_doc.status == 'Half Day':
			if half_att_list :
				for att in half_att_list:
					att_doc = frappe.get_doc("Attendance", att.name)
					if not att_doc.leave_application:

						leave_details_list = get_leave_details(att_doc.employee, att_doc.attendance_date)
						leave_details = leave_details_list["leave_allocation"]

						leave_type = "Leave Without Pay"
						if leave_details:
							if "Casual Leave" in leave_details and leave_details["Casual Leave"]["remaining_leaves"] >= 0.5:
								leave_type = "Casual Leave"
							elif "Sick Leave" in leave_details and leave_details["Sick Leave"]["remaining_leaves"] >= 0.5:
								leave_type = "Sick Leave"
							else:
								leave_type = "Leave Without Pay"

						create_system_generated_half_leaves(att_doc, leave_type, doc)

	check_and_create_quarter_leaves(doc)				


def create_single_leaves(doc, sch_doc) :

    start_date = doc.from_date
    end_date = doc.to_date
    
    current_date = start_date
    while str(current_date) <= str(end_date) :
        leave_type = get_leave_type(doc.employee, current_date)
        new_doc = frappe.get_doc({
            "doctype": "Leave Application",
            "employee": doc.employee,
            "leave_type": leave_type,
            "from_date": current_date,
            "to_date": current_date,
            "custom_system_generated": 1,
            "custom_monthly_leave_scheduler": doc.custom_monthly_leave_scheduler,
            "total_leave_days": 1,
            "status": "Approved",
            "docstatus": 0,
        })
        new_doc.insert()
        new_doc.submit()

        if sch_doc.workflow_exist == 1:
            frappe.db.set_value("Leave Application", new_doc.name, "workflow_state", sch_doc.workflow_state)

        current_date = add_days(current_date, 1)




def check_adjacent_leaves(doc) :

        
    day_before = frappe.utils.add_days(doc.from_date,-1)
    day_after = frappe.utils.add_days(doc.to_date,1)
    dayDifference = frappe.utils.date_diff(doc.to_date , doc.from_date) + 1
    
    
    d_b = 0
    d_a = 0
    
    
    emp_doc = frappe.get_doc("Employee", doc.employee)
    att_list = frappe.get_list("Attendance", 
                    filters = {
                        "employee": doc.employee,
                        'shift': ["!=", ""],
                    },
                    fields = ['name', 'shift'],
                    order_by = "attendance_date DESC",
                )
                
    
    
    
    
    if att_list : 
        shift_doc = frappe.get_doc("Shift Type", att_list[0].shift)
    else :
        shift_doc = frappe.get_doc("Shift Type", emp_doc.default_shift)
                
          
          
          
          
          
          
    ################ Give priority to holiday in the Employee doctype #################
    
    
    holiday_in_emp = frappe.db.get_value('Employee', doc.employee, 'holiday_list')
    if holiday_in_emp:
        holiday_doc = frappe.get_doc("Holiday List", holiday_in_emp)
    else:
        holiday_doc = frappe.get_doc("Holiday List", shift_doc.holiday_list)

    doc.custom_holiday = holiday_doc.name
    
    
    
    
    
    
    
    public_holiday_dates = []
    weekly_off_holiday_dates = []
    
    for row in holiday_doc.holidays :
        if row.weekly_off != 1 :
            public_holiday_dates.append(str(row.holiday_date))
        else :
            weekly_off_holiday_dates.append(str(row.holiday_date))
            
    # frappe.msgprint(str(doc.workflow_state))
    
    check_b_d = frappe.db.exists({"doctype" : "Leave Application", "employee" : doc.employee , "to_date" : day_before , "half_day" : ["!=" , 1] , "custom_quarter_day" : ["!=" , 1] , "docstatus" : ["!=" , 2] , "workflow_state" : ["NOT IN" , ['Rejected by First Approver','Rejected by Second Approver','Rejected by HR Head']] } )
    check_a_d = frappe.db.exists({"doctype" : "Leave Application", "employee" : doc.employee , "from_date" : day_after , "half_day" : ["!=" , 1] , "custom_quarter_day" : ["!=" , 1] , "docstatus" : ["!=" , 2] , "workflow_state" : ["NOT IN" , ['Rejected by First Approver','Rejected by Second Approver','Rejected by HR Head']] } )
    
    
    if not check_b_d :
        # frappe.msgprint(str(public_holiday_dates))
        while str(day_before) in public_holiday_dates:
            d_b = d_b + 1
            day_before = frappe.utils.add_days(day_before, -1)
            
    
    
    if not check_a_d :    
        while str(day_after) in public_holiday_dates:
            d_a = d_a + 1
            day_after = frappe.utils.add_days(day_after, 1)
    
    
        
    doc.from_date = frappe.utils.add_days(day_before,1)
    doc.to_date = frappe.utils.add_days(day_after,-1)
    doc.total_leave_days = dayDifference + d_b + d_a
    
    
    
    
    
    
    
    ###########################   FOR PUBLIC HOLIDAYS   ##########################
    
    
    sig1 = 1
    sig2 = 1
    day_before = frappe.utils.add_days(doc.from_date,-1)
    day_after = frappe.utils.add_days(doc.to_date,1)
        
    if d_b == 0 :
        
        while sig1 == 1 :
            if str(day_before) in weekly_off_holiday_dates :
                day_before = frappe.utils.add_days(day_before, -1)
            
            else :
                sig1 = 0
                check_b_d = frappe.db.exists({"doctype" : "Leave Application", "employee" : doc.employee , "to_date" : day_before , "half_day" : ["!=" , 1] , "custom_quarter_day" : ["!=" , 1] , "docstatus" : ["!=" , 2] , "workflow_state" : ["NOT IN" , ['Rejected by First Approver','Rejected by Second Approver','Rejected by HR Head']] } )
                if check_b_d :
                    doc.from_date = frappe.utils.add_days(day_before, 1)
                    
    
    if d_a == 0 :            
                
        while sig2 == 1 :
        
            if str(day_after) in weekly_off_holiday_dates :
                day_after = frappe.utils.add_days(day_after, 1)
            
            else :
                sig2 = 0
                check_a_d = frappe.db.exists({"doctype" : "Leave Application", "employee" : doc.employee , "from_date" : day_after , "half_day" : ["!=" , 1] , "custom_quarter_day" : ["!=" , 1] , "docstatus" : ["!=" , 2] , "workflow_state" : ["NOT IN" , ['Rejected by First Approver','Rejected by Second Approver','Rejected by HR Head']] } )
                if check_a_d :
                    doc.to_date = frappe.utils.add_days(day_after, -1)
            
    
    
    doc.total_leave_days = frappe.utils.date_diff(doc.to_date , doc.from_date) + 1
    
    
    holiday_att_list = frappe.db.get_list("Attendance",
                        
                            filters = {
                                'employee' : doc.employee ,
                                'docstatus' : 1 ,
                                'custom_holiday' : 1 ,
                                'attendance_date' : ['between', [doc.from_date , doc.to_date] ] ,
                                'status' : ['!=', 'On Leave'] ,
                                
                            }
                            
                        )
    
    if holiday_att_list :
        for row in holiday_att_list :
            holiday_att_doc = frappe.get_doc('Attendance', row.name)
            holiday_att_doc.cancel()
                
				
		
				
				
					
					
					
					
					
					
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                
        
    
    
    
    
    
    
    
    
    
    
    











class MonthlyLeaveScheduler(Document):

	def before_save(self):
		if self.from_date > self.to_date:
			frappe.throw("'To Date' must be greater than 'From Date'.")

	def before_submit(self):
		doc_name = self
		enqueue(check_and_create_full_and_half_leaves , doc = self, queue = "long")
		
		




