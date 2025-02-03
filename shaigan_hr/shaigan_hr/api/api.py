import frappe
from frappe.utils import get_datetime
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, datetime, time_diff_in_seconds, add_days
from datetime import datetime as py_datetime

import frappe
# from frappe.utils import get_datetime, timedelta


from hrms.hr.doctype.employee_checkin.employee_checkin import (

    skip_attendance_in_checkins

)


def calculate_ot_hours(logs, employee, attendance_date, shift_type):
    """Calculate penalties and mark if the employee is late.

    :param logs: List of 'Employee Checkin' logs.
    :param shift_type: The shift type which includes shift start and end times.
    :param check_in_out_type: One of the check-in/check-out types (not used in this version).
    :param working_hours_calc_type: One of the working hours calculation types (not used in this version).
    """
    
    # total_working_seconds = 0
    # working_hours = 0
    # ot_hours = 0
    # last_in_time = None
    # logs.sort(key=lambda log: log.time)
    # for log in logs:
    #     if log.log_type == 'IN':
    #         last_in_time = log.time
    #     elif log.log_type == 'OUT' and last_in_time:
    #         time_diff = time_diff_in_seconds(log.time, last_in_time)
    #         total_working_seconds += time_diff
    #         last_in_time = None

    # total_working_hours = total_working_seconds / 3600
    # frappe.msgprint(f"Total Working Hours: {total_working_hours}")

    # attendance_date = str(attendance_date)
    total_working_seconds = 0
    outside_shift_seconds = 0
    working_hours = 0
    last_in_time = None

    shift_type_doc = frappe.get_doc('Shift Type', shift_type)

    shift_start = get_datetime(f"{attendance_date} {shift_type_doc.start_time}")


    if isinstance(shift_type_doc.start_time, str):
        start_time = py_datetime.strptime(shift_type_doc.start_time, "%H:%M:%S").time()
    else:
        start_time = shift_type_doc.start_time

    if isinstance(shift_type_doc.end_time, str):
        end_time = py_datetime.strptime(shift_type_doc.end_time, "%H:%M:%S").time()
    else:
        end_time = shift_type_doc.end_time

    if start_time < end_time :
        shift_end = get_datetime(f"{attendance_date} {shift_type_doc.end_time}")
    else :
        shift_end = get_datetime(f"{add_days(attendance_date, 1)} {shift_type_doc.end_time}")


    logs.sort(key=lambda log: log.time)

    for log in logs:
        if log.log_type == 'IN':
            last_in_time = log.time
        elif log.log_type == 'OUT' and last_in_time:
            time_diff = time_diff_in_seconds(log.time, last_in_time)
            total_working_seconds += time_diff

            if last_in_time < shift_start:
                outside_shift_seconds += time_diff_in_seconds(min(log.time, shift_start), last_in_time)

            if log.time > shift_end:
                outside_shift_seconds += time_diff_in_seconds(log.time, max(shift_end, last_in_time))


            last_in_time = None

    total_working_hours = total_working_seconds / 3600
    outside_shift_hours = outside_shift_seconds / 3600
    working_hours = total_working_hours - outside_shift_hours

    return outside_shift_hours






def count_penalties(logs, employee, attendance_date, shift_type, working_hours) :
    
    shift_type_doc = frappe.get_doc('Shift Type', shift_type)
    threshold_for_absent = shift_type_doc.required_hours - shift_type_doc.working_hours_threshold_for_half_day
    shift_start = get_datetime(f"{attendance_date} {shift_type_doc.start_time}")
    shift_end = get_datetime(f"{attendance_date} {shift_type_doc.end_time}")
    grace_time = 0

    if shift_type_doc.enable_late_entry_marking == 1 :
        if shift_type_doc.late_entry_grace_period :
            grace_time = shift_type_doc.late_entry_grace_period

    filtered_logs = [log for log in logs if shift_start <= log.time <= shift_end]
    
    filtered_logs.sort(key=lambda log: log.time)

    penalties = 0
    last_out_time = None
    late = False  
    early = False
    
    if filtered_logs :


        in_time = filtered_logs[0].time
        out_time = filtered_logs[-1].time


    # if filtered_logs:
        first_log = filtered_logs[0]

        if first_log.log_type == 'IN':
            absent_threshold_in_minutes = threshold_for_absent * 60
            
            if first_log.time > shift_start + timedelta(minutes=grace_time) and first_log.time <= shift_start + timedelta(minutes=absent_threshold_in_minutes):
                late = True
        elif first_log.log_type == 'OUT':
            late = False


    # if filtered_logs:
        last_log = filtered_logs[-1]


        if shift_start < first_log.time and first_log.time <= shift_start + timedelta(minutes=grace_time) :

            late_minutes = (first_log.time - shift_start).total_seconds() / 60

            
            if last_log.log_type == 'OUT':
                absent_threshold_in_minutes = threshold_for_absent * 60
                absent_threshold_in_minutes = absent_threshold_in_minutes - late_minutes

                if last_log.time <= shift_end - timedelta(seconds=1) and last_log.time > shift_end - timedelta(minutes=absent_threshold_in_minutes) :
                    early = True
            elif last_log.log_type == 'IN':
                early = False



        else :    
            if last_log.log_type == 'OUT':
                absent_threshold_in_minutes = threshold_for_absent * 60
                if last_log.time <= shift_end - timedelta(seconds=1) and last_log.time > shift_end - timedelta(minutes=absent_threshold_in_minutes) :
                    early = True
            elif last_log.log_type == 'IN':
                early = False


  
    
    # if filtered_logs :
        for log in filtered_logs:
            if log.log_type == 'OUT':
                last_out_time = log.time
            elif log.log_type == 'IN':
                if last_out_time:
                    
                    if last_out_time < log.time:
                
                        duration = log.time - last_out_time
                        if duration.total_seconds() / 3600 < threshold_for_absent:
                            penalties += 1
                    last_out_time = None
      

        if late == True :
            penalties = penalties + 1
        if early == True :
            penalties = penalties + 1

        if penalties > 4 :
            penalties = 4


    else :
        if shift_type_doc.required_hours > working_hours :
            penalties = 0



    return penalties 



def time_diff_in_hours(start, end):
	return round(float((end - start).total_seconds()) / 3600, 2)



def find_index_in_dict(dict_list, key, value):
	return next((index for (index, d) in enumerate(dict_list) if d[key] == value), None)


@frappe.whitelist()
def check_work_flow_exist(doctype) :

    worf_flow_doc = frappe.db.get_list("Workflow",
                        filters = {
                            'document_type' : doctype ,
                            'is_active' : 1 ,
                        })
    
    if worf_flow_doc :
        return worf_flow_doc[0].name
    
    return None



@frappe.whitelist()
def get_workflow_states(docname) :

    states = []
    workflow_doc = frappe.get_doc('Workflow' , docname)

    for row in workflow_doc.states :
        if row.doc_status != '2' :
            states.append(row.state)
    
    return states






























