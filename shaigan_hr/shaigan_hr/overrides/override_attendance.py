

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	cint,
	cstr,
	format_date,
	get_datetime,
	get_link_to_form,
	getdate,
	nowdate,
	add_to_date,
)
from datetime import datetime, timedelta

from hrms.hr.doctype.shift_assignment.shift_assignment import has_overlapping_timings
from hrms.hr.utils import (
	get_holiday_dates_for_employee,
	get_holidays_for_employee,
	validate_active_employee,
)

from hrms.hr.doctype.attendance.attendance import Attendance

from shaigan_hr.shaigan_hr.overrides.quarter_leave_application import get_leave_details


class DuplicateAttendanceError(frappe.ValidationError):
	pass


class OverlappingShiftAttendanceError(frappe.ValidationError):
	pass


class OverrideAttendance(Attendance):
	def validate(self):
		from erpnext.controllers.status_updater import validate_status

		validate_status(self.status, ["Present", "Absent", "On Leave", "Half Day", "Work From Home"])
		validate_active_employee(self.employee)
		self.validate_attendance_date()
		self.validate_duplicate_record()
		self.validate_overlapping_shift_attendance()
		self.validate_employee_status()
		self.check_leave_record()
		# self.check_quarter_leave_record()
		# self.check_quarter_threshold()


    # Sufyan created this Function
	def before_submit(self) :
		if self.status == 'Present' and self.custom_quarter in ['ONE', 'TWO']:
			q_l_list = frappe.get_list("Leave Application",
								filters={
									'employee': self.employee,
									'from_date': self.attendance_date,
									'custom_quarter_day': 1,
									'status': 'Approved',
									'docstatus': 1,
								})
			if q_l_list :
				x = 0
				for q_l in q_l_list:
					x = x + 1
					q_l_doc = frappe.get_doc("Leave Application", q_l.name)
					self.append('custom_quarter_leaves', {
						'leave_application': q_l_doc.name,
						'leave_type': q_l_doc.leave_type,
						'from_time': q_l_doc.custom_from_time,
						'to_time': q_l_doc.custom_to_time,
						'system_generated' : q_l_doc.custom_system_generated ,
					})
					if self.custom_quarter == 'ONE' :
						break
						
					if self.custom_quarter == 'TWO' and x == 2 :
						break



	def validate_attendance_date(self):
		date_of_joining = frappe.db.get_value("Employee", self.employee, "date_of_joining")

		# leaves can be marked for future dates
		if (
			self.status != "On Leave"
			and not self.leave_application
			and getdate(self.attendance_date) > getdate(nowdate())
		):
			frappe.throw(
				_("Attendance can not be marked for future dates: {0}").format(
					frappe.bold(format_date(self.attendance_date)),
				)
			)
		elif date_of_joining and getdate(self.attendance_date) < getdate(date_of_joining):
			frappe.throw(
				_("Attendance date {0} can not be less than employee {1}'s joining date: {2}").format(
					frappe.bold(format_date(self.attendance_date)),
					frappe.bold(self.employee),
					frappe.bold(format_date(date_of_joining)),
				)
			)

	def validate_duplicate_record(self):
		duplicate = self.get_duplicate_attendance_record()

		if duplicate:
			frappe.throw(
				_("Attendance for employee {0} is already marked for the date {1}: {2}").format(
					frappe.bold(self.employee),
					frappe.bold(format_date(self.attendance_date)),
					get_link_to_form("Attendance", duplicate),
				),
				title=_("Duplicate Attendance"),
				exc=DuplicateAttendanceError,
			)

	def get_duplicate_attendance_record(self) -> str | None:
		Attendance = frappe.qb.DocType("Attendance")
		query = (
			frappe.qb.from_(Attendance)
			.select(Attendance.name)
			.where(
				(Attendance.employee == self.employee)
				& (Attendance.docstatus < 2)
				& (Attendance.attendance_date == self.attendance_date)
				& (Attendance.name != self.name)
			)
		)

		if self.shift:
			query = query.where(
				((Attendance.shift.isnull()) | (Attendance.shift == ""))
				| (
					((Attendance.shift.isnotnull()) | (Attendance.shift != ""))
					& (Attendance.shift == self.shift)
				)
			)

		duplicate = query.run(pluck=True)

		return duplicate[0] if duplicate else None

	def validate_overlapping_shift_attendance(self):
		attendance = self.get_overlapping_shift_attendance()

		if attendance:
			frappe.throw(
				_("Attendance for employee {0} is already marked for an overlapping shift {1}: {2}").format(
					frappe.bold(self.employee),
					frappe.bold(attendance.shift),
					get_link_to_form("Attendance", attendance.name),
				),
				title=_("Overlapping Shift Attendance"),
				exc=OverlappingShiftAttendanceError,
			)

	def get_overlapping_shift_attendance(self) -> dict:
		if not self.shift:
			return {}

		Attendance = frappe.qb.DocType("Attendance")
		same_date_attendance = (
			frappe.qb.from_(Attendance)
			.select(Attendance.name, Attendance.shift)
			.where(
				(Attendance.employee == self.employee)
				& (Attendance.docstatus < 2)
				& (Attendance.attendance_date == self.attendance_date)
				& (Attendance.shift != self.shift)
				& (Attendance.name != self.name)
			)
		).run(as_dict=True)

		for d in same_date_attendance:
			if has_overlapping_timings(self.shift, d.shift):
				return d

		return {}

	def validate_employee_status(self):
		if frappe.db.get_value("Employee", self.employee, "status") == "Inactive":
			frappe.throw(_("Cannot mark attendance for an Inactive employee {0}").format(self.employee))

	def check_leave_record(self):
		LeaveApplication = frappe.qb.DocType("Leave Application")
		leave_record = (
			frappe.qb.from_(LeaveApplication)
			.select(
				LeaveApplication.leave_type,
				LeaveApplication.half_day,
				LeaveApplication.half_day_date,
				LeaveApplication.name,
			)
			.where(
				(LeaveApplication.employee == self.employee)
				& (self.attendance_date >= LeaveApplication.from_date)
				& (self.attendance_date <= LeaveApplication.to_date)
				& (LeaveApplication.status == "Approved")
				& (LeaveApplication.docstatus == 1)
				& (LeaveApplication.custom_quarter_day != 1)
			)
		).run(as_dict=True)

		if leave_record:
			for d in leave_record:
				self.leave_type = d.leave_type
				self.leave_application = d.name
				if d.half_day_date == getdate(self.attendance_date):
					self.status = "Half Day"
					frappe.msgprint(
						_("Employee {0} on Half day on {1}").format(
							self.employee, format_date(self.attendance_date)
						)
					)
				else:
					self.status = "On Leave"
					frappe.msgprint(
						_("Employee {0} is on Leave on {1}").format(
							self.employee, format_date(self.attendance_date)
						)
					)

		if self.status in ("On Leave", "Half Day"):
			if not leave_record:
				frappe.msgprint(
					_("No leave record found for employee {0} on {1}").format(
						self.employee, format_date(self.attendance_date)
					),
					alert=1,
				)
		elif self.leave_type:
			self.leave_type = None
			self.leave_application = None



    ## Created By Sufyan For Shaigan Quarter Leave ##
	def check_quarter_leave_record(self) :

		LeaveApplication = frappe.qb.DocType("Leave Application")
		quarter_leave_records = (
                frappe.qb.from_(LeaveApplication)
                .select(
                    LeaveApplication.name,
					LeaveApplication.leave_type,
                    LeaveApplication.custom_from_time,
                    LeaveApplication.custom_to_time,
                )
                .where(
                    (LeaveApplication.employee == self.employee)
                    & (self.attendance_date == LeaveApplication.from_date)
                    & (LeaveApplication.status == "Approved")
                    & (LeaveApplication.docstatus == 1)
                    & (LeaveApplication.custom_quarter_day == 1)
                )
            ).run(as_dict=True)
		
		if quarter_leave_records :
			for row in quarter_leave_records :
				self.append('custom_leave_applications',{
					'leave_application' : row.name ,
					'type' : row.leave_type ,
					'from_time' : row.custom_from_time ,
					'to_time' : row.custom_to_time ,
                })
			self.custom_quarter_day = 1	



   ## Created By Sufyan For Shaigan Quarter Leave ##
	def check_quarter_threshold(self) :
		if self.shift and self.working_hours and self.in_time and self.out_time :
			sh_t_doc = frappe.get_doc("Shift Type",self.shift)
			if sh_t_doc.working_hours_threshold_for_half_day < self.working_hours < sh_t_doc.custom_working_hours_threshold_for_quarter_day :
				self.custom_quarter_day = 1
				
				q_from_time = frappe.utils.get_time(self.in_time)
				q_to_time = frappe.utils.get_time(self.in_time)

				if self.custom_leave_applications :
					for row in self.custom_leave_applications :
						to_time = frappe.utils.get_time(row.to_time)
						if to_time > q_from_time :
							q_from_time = frappe.utils.get_time(row.to_time)	
				else :
					q_from_time = frappe.utils.get_time(self.out_time)	

				 # Convert time to datetime, add 1 second, then convert back to time
				q_from_time = (datetime.combine(datetime.today(), q_from_time) + timedelta(seconds=1)).time()
				q_t = sh_t_doc.required_hours / 4
				q_to_time = (datetime.combine(datetime.today(), q_from_time) + timedelta(hours=q_t)).time()

				leave_details_list = get_leave_details(self.employee , self.attendance_date)
				leave_details = leave_details_list["leave_allocation"]
				if leave_details :
					leave_type = None

					if "Casual Leave" in leave_details and leave_details["Casual Leave"]["remaining_leaves"] >= 0.25 :
						leave_type = "Casual Leave"
					elif "Sick Leave" in leave_details and leave_details["Sick Leave"]["remaining_leaves"] >= 0.25 :
						leave_type = "Sick Leave"
					else:
						leave_type = "Leave Without Pay"


				la_doc = frappe.get_doc({
					"doctype": "Leave Application",
					"employee": self.employee ,
					"leave_type" : leave_type ,
					"from_date": self.attendance_date ,
					"to_date": self.attendance_date ,
					"custom_created_from_attendance" : 1 ,
					"custom_quarter_day": 1 ,
					"custom_from_time" : q_from_time ,
					"custom_to_time" : q_to_time ,
					"total_leave_days" : 0.25 ,
					"status": "Approved",
					"docstatus": 1 ,
				})
				la_doc.insert()
				

				self.append('custom_leave_applications', {
					'leave_application': la_doc.name ,
					'type': la_doc.leave_type ,
					'from_time': la_doc.custom_from_time ,
					'to_time' : la_doc.custom_to_time ,
					'created_according_to_quarter_threshold' : 1 ,
				})


				if leave_type != 'Leave Without Pay' :
					self.working_hours = self.working_hours + (sh_t_doc.required_hours*0.25)



	def validate_employee(self):
		emp = frappe.db.sql(
			"select name from `tabEmployee` where name = %s and status = 'Active'", self.employee
		)
		if not emp:
			frappe.throw(_("Employee {0} is not active or does not exist").format(self.employee))	








	def unlink_attendance_from_checkins(self):
		EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
		linked_logs = (
			frappe.qb.from_(EmployeeCheckin)
			.select(EmployeeCheckin.name)
			.where(EmployeeCheckin.attendance == self.name)
			.for_update()
			.run(as_dict=True)
		)

		if linked_logs:
			(
				frappe.qb.update(EmployeeCheckin)
				.set("attendance", "")
				.where(EmployeeCheckin.attendance == self.name)
			).run()

			frappe.msgprint(
				msg=_("Unlinked Attendance record from Employee Checkins: {}").format(
					", ".join(get_link_to_form("Employee Checkin", log.name) for log in linked_logs)
				),
				title=_("Unlinked logs"),
				indicator="blue",
				is_minimizable=True,
				wide=True,
			)


@frappe.whitelist()
def get_events(start, end, filters=None):
	from frappe.desk.reportview import get_filters_cond

	events = []

	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user})

	if not employee:
		return events

	conditions = get_filters_cond("Attendance", filters, [])
	add_attendance(events, start, end, conditions=conditions)
	add_holidays(events, start, end, employee)
	return events


def add_attendance(events, start, end, conditions=None):
	query = """select name, attendance_date, status, employee_name
		from `tabAttendance` where
		attendance_date between %(from_date)s and %(to_date)s
		and docstatus < 2"""

	if conditions:
		query += conditions

	for d in frappe.db.sql(query, {"from_date": start, "to_date": end}, as_dict=True):
		e = {
			"name": d.name,
			"doctype": "Attendance",
			"start": d.attendance_date,
			"end": d.attendance_date,
			"title": f"{d.employee_name}: {cstr(d.status)}",
			"status": d.status,
			"docstatus": d.docstatus,
		}
		if e not in events:
			events.append(e)


def add_holidays(events, start, end, employee=None):
	holidays = get_holidays_for_employee(employee, start, end)
	if not holidays:
		return

	for holiday in holidays:
		events.append(
			{
				"doctype": "Holiday",
				"start": holiday.holiday_date,
				"end": holiday.holiday_date,
				"title": _("Holiday") + ": " + cstr(holiday.description),
				"name": holiday.name,
				"allDay": 1,
			}
		)


def mark_attendance(
	employee,
	attendance_date,
	status,
	shift=None,
	leave_type=None,
	late_entry=False,
	early_exit=False,
):
	savepoint = "attendance_creation"

	try:
		frappe.db.savepoint(savepoint)
		attendance = frappe.new_doc("Attendance")
		attendance.update(
			{
				"doctype": "Attendance",
				"employee": employee,
				"attendance_date": attendance_date,
				"status": status,
				"shift": shift,
				"leave_type": leave_type,
				"late_entry": late_entry,
				"early_exit": early_exit,
			}
		)
		attendance.insert()
		attendance.submit()
	except (DuplicateAttendanceError, OverlappingShiftAttendanceError):
		frappe.db.rollback(save_point=savepoint)
		return

	return attendance.name


@frappe.whitelist()
def mark_bulk_attendance(data):
	import json

	if isinstance(data, str):
		data = json.loads(data)
	data = frappe._dict(data)
	if not data.unmarked_days:
		frappe.throw(_("Please select a date."))
		return

	for date in data.unmarked_days:
		doc_dict = {
			"doctype": "Attendance",
			"employee": data.employee,
			"attendance_date": get_datetime(date),
			"status": data.status,
		}
		attendance = frappe.get_doc(doc_dict).insert()
		attendance.submit()


@frappe.whitelist()
def get_unmarked_days(employee, from_date, to_date, exclude_holidays=0):
	joining_date, relieving_date = frappe.get_cached_value(
		"Employee", employee, ["date_of_joining", "relieving_date"]
	)

	from_date = max(getdate(from_date), joining_date or getdate(from_date))
	to_date = min(getdate(to_date), relieving_date or getdate(to_date))

	records = frappe.get_all(
		"Attendance",
		fields=["attendance_date", "employee"],
		filters=[
			["attendance_date", ">=", from_date],
			["attendance_date", "<=", to_date],
			["employee", "=", employee],
			["docstatus", "!=", 2],
		],
	)

	marked_days = [getdate(record.attendance_date) for record in records]

	if cint(exclude_holidays):
		holiday_dates = get_holiday_dates_for_employee(employee, from_date, to_date)
		holidays = [getdate(record) for record in holiday_dates]
		marked_days.extend(holidays)

	unmarked_days = []

	while from_date <= to_date:
		if from_date not in marked_days:
			unmarked_days.append(from_date)

		from_date = add_days(from_date, 1)

	return unmarked_days
