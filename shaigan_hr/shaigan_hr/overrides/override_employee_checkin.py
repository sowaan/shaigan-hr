# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_datetime
from frappe.utils import cint, get_datetime, datetime, time_diff_in_seconds , add_days
from datetime import datetime
from hrms.hr.doctype.shift_assignment.shift_assignment import (
    get_actual_start_end_datetime_of_shift,
)
from hrms.hr.utils import validate_active_employee

from shaigan_hr.shaigan_hr.api.api import (calculate_ot_hours , count_penalties)

from hrms.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin

class OverrideEmployeeCheckin(EmployeeCheckin):
    def validate(self):
        validate_active_employee(self.employee)
        self.validate_duplicate_log()
        self.fetch_shift()

    def validate_duplicate_log(self):
        doc = frappe.db.exists(
            "Employee Checkin",
            {
                "employee": self.employee,
                "time": self.time,
                "name": ("!=", self.name),
                "log_type": self.log_type,
            },
        )
        if doc:
            doc_link = frappe.get_desk_link("Employee Checkin", doc)
            frappe.throw(
                _("This employee already has a log with the same timestamp.{0}").format("<Br>" + doc_link)
            )

    def fetch_shift(self):
        shift_actual_timings = get_actual_start_end_datetime_of_shift(
            self.employee, get_datetime(self.time), True
        )
        if shift_actual_timings:
            if (
                shift_actual_timings.shift_type.determine_check_in_and_check_out
                == "Strictly based on Log Type in Employee Checkin"
                and not self.log_type
                and not self.skip_auto_attendance
            ):
                frappe.throw(
                    _("Log Type is required for check-ins falling in the shift: {0}.").format(
                        shift_actual_timings.shift_type.name
                    )
                )
            if not self.attendance:
                self.shift = shift_actual_timings.shift_type.name
                self.shift_actual_start = shift_actual_timings.actual_start
                self.shift_actual_end = shift_actual_timings.actual_end
                self.shift_start = shift_actual_timings.start_datetime
                self.shift_end = shift_actual_timings.end_datetime
        else:
            self.shift = None


@frappe.whitelist()
def add_log_based_on_employee_field(
    employee_field_value,
    timestamp,
    device_id=None,
    log_type=None,
    skip_auto_attendance=0,
    employee_fieldname="attendance_device_id",
):
    """Finds the relevant Employee using the employee field value and creates a Employee Checkin.

    :param employee_field_value: The value to look for in employee field.
    :param timestamp: The timestamp of the Log. Currently expected in the following format as string: '2019-05-08 10:48:08.000000'
    :param device_id: (optional)Location / Device ID. A short string is expected.
    :param log_type: (optional)Direction of the Punch if available (IN/OUT).
    :param skip_auto_attendance: (optional)Skip auto attendance field will be set for this log(0/1).
    :param employee_fieldname: (Default: attendance_device_id)Name of the field in Employee DocType based on which employee lookup will happen.
    """

    if not employee_field_value or not timestamp:
        frappe.throw(_("'employee_field_value' and 'timestamp' are required."))

    employee = frappe.db.get_values(
        "Employee",
        {employee_fieldname: employee_field_value},
        ["name", "employee_name", employee_fieldname],
        as_dict=True,
    )
    if employee:
        employee = employee[0]
    else:
        frappe.throw(
            _("No Employee found for the given employee field value. '{}': {}").format(
                employee_fieldname, employee_field_value
            )
        )

    doc = frappe.new_doc("Employee Checkin")
    doc.employee = employee.name
    doc.employee_name = employee.employee_name
    doc.time = timestamp
    doc.device_id = device_id
    doc.log_type = log_type
    if cint(skip_auto_attendance) == 1:
        doc.skip_auto_attendance = "1"
    doc.insert()

    return doc


def mark_attendance_and_link_log(
    logs,
    attendance_status,
    attendance_date,
    working_hours=None,
    late_entry=False,
    early_exit=False,
    in_time=None,
    out_time=None,
    shift=None,
):
    """Creates an attendance and links the attendance to the Employee Checkin.
    Note: If attendance is already present for the given date, the logs are marked as skipped and no exception is thrown.

    :param logs: The List of 'Employee Checkin'.
    :param attendance_status: Attendance status to be marked. One of: (Present, Absent, Half Day, Skip). Note: 'On Leave' is not supported by this function.
    :param attendance_date: Date of the attendance to be created.
    :param working_hours: (optional)Number of working hours for the given date.
    """
    log_names = [x.name for x in logs]
    employee = logs[0].employee
    penalties = count_penalties(logs, employee, attendance_date, shift, working_hours)
    ot_hrs = calculate_ot_hours(logs, employee, attendance_date, shift)
    
    # shift_type_doc = frappe.get_doc("Shift Type",shift)

    att_status = ''
    q = ''
    
    if penalties == 0 :
        att_status = 'Present'        
  
    elif penalties == 1 :
        att_status = '3 Quarters'
        q = 'ONE'

    elif penalties == 2 :
        att_status = 'Half Day'
        q = 'TWO'

    elif penalties == 3 :
        att_status = 'Quarter'
        q = 'THREE'

    elif penalties == 4 :
        att_status = 'Absent'
        q = 'FOUR'     


    if attendance_status == "Skip":
        skip_attendance_in_checkins(log_names)
        return None

    elif attendance_status in ("Present", "Absent", "Half Day"):

        if att_status == 'Absent' or att_status == 'Quarter' :
            attendance_status = 'Absent'


        if attendance_status == 'Absent' and att_status != 'Quarter' :
            att_status = 'Absent'

        try:
            frappe.db.savepoint("attendance_creation")
            attendance = frappe.new_doc("Attendance")
            if penalties > 0 :
                if attendance_status == 'Half Day' :
                    attendance_status = 'Absent'
                attendance.update(
                    {
                        "doctype": "Attendance",
                        "employee": employee,
                        "attendance_date": attendance_date,
                        "status": attendance_status,
                        "custom_attendance_status": att_status,
                        "custom_quarter": q, 
                        "working_hours": working_hours,
                        "custom_overtime_hours": ot_hrs,
                        "shift": shift,
                        "late_entry": late_entry,
                        "early_exit": early_exit,
                        "in_time": in_time,
                        "out_time": out_time,
                    }
                ).submit()

            else :    
                attendance.update(
                    {
                        "doctype": "Attendance",
                        "employee": employee,
                        "attendance_date": attendance_date,
                        "status": attendance_status,
                        "custom_attendance_status": att_status,
                        "working_hours": working_hours,
                        "custom_overtime_hours": ot_hrs,
                        "shift": shift,
                        "late_entry": late_entry,
                        "early_exit": early_exit,
                        "in_time": in_time,
                        "out_time": out_time,
                    }
                ).submit()

            if attendance_status == "Absent":
                attendance.add_comment(
                    text=_("Employee was marked Absent for not meeting the working hours threshold.")
                )

            update_attendance_in_checkins(log_names, attendance.name)
            return attendance

        except frappe.ValidationError as e:
            handle_attendance_exception(log_names, e)

    else:
        frappe.throw(_("{} is an invalid Attendance Status.").format(attendance_status))


def calculate_working_hours(logs, employee, attendance_date, shift_type, check_in_out_type, working_hours_calc_type):
    total_working_seconds = 0
    outside_shift_seconds = 0
    last_in_time = None

    shift_start = get_datetime(f"{attendance_date} {shift_type.start_time}")

    
    start_time = datetime.strptime(shift_type.start_time, "%H:%M:%S").time()
    end_time = datetime.strptime(shift_type.end_time, "%H:%M:%S").time()


    if start_time < end_time :
        shift_end = get_datetime(f"{attendance_date} {shift_type.end_time}")

    else :
        shift_end = get_datetime(f"{add_days(attendance_date, 1)} {shift_type.end_time}")



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

    return working_hours, logs[0].time, logs[-1].time


def time_diff_in_hours(start, end):
    return round(float((end - start).total_seconds()) / 3600, 2)


def find_index_in_dict(dict_list, key, value):
    return next((index for (index, d) in enumerate(dict_list) if d[key] == value), None)


def handle_attendance_exception(log_names: list, error_message: str):
    frappe.db.rollback(save_point="attendance_creation")
    frappe.clear_messages()
    skip_attendance_in_checkins(log_names)
    add_comment_in_checkins(log_names, error_message)


def add_comment_in_checkins(log_names: list, error_message: str):
    text = "{0}<br>{1}".format(frappe.bold(_("Reason for skipping auto attendance:")), error_message)

    for name in log_names:
        frappe.get_doc(
            {
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": "Employee Checkin",
                "reference_name": name,
                "content": text,
            }
        ).insert(ignore_permissions=True)


def skip_attendance_in_checkins(log_names: list):
    EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
    (
        frappe.qb.update(EmployeeCheckin)
        .set("skip_auto_attendance", 1)
        .where(EmployeeCheckin.name.isin(log_names))
    ).run()


def update_attendance_in_checkins(log_names: list, attendance_id: str):
    EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
    (
        frappe.qb.update(EmployeeCheckin)
        .set("attendance", attendance_id)
        .where(EmployeeCheckin.name.isin(log_names))
    ).run()
