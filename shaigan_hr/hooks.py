app_name = "shaigan_hr"
app_title = "Shaigan HR"
app_publisher = "Sowaan"
app_description = "Enhanced ERP leave module to support \'Quarter Day Leave\' for 0.25 days, in addition to full and half-day options."
app_email = "sufyan.sadiq@sowaan.com"
app_license = "mit"
# required_apps = []


fixtures = [
    {
      "doctype" : "Custom Field",
      "filters" : [
        [  
          "module" , "=" , "Shaigan HR" ,
          "fieldname" , "in" , ("custom_quarter_leave_without_pay","custom_working_days","custom_system_generated_leave_days","custom_payment_day","custom_base")
        ]  
      ]
	  },
    {
      "doctype" : "Print Format",
      "filters" : [
        [  
          "name", "IN", ["Reconciliation Report Print", "Payorder Report"]
        ]
      ]
    },
    {
      "doctype" : "Letter Head",
      "filters" : [
        [  
          "name", "=" , "Payorder Report Letter Head"
        ]
      ]
    }
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/shaigan_hr/css/shaigan_hr.css"
# app_include_js = "/assets/shaigan_hr/js/shaigan_hr.js"

# include js, css files in header of web template
# web_include_css = "/assets/shaigan_hr/css/shaigan_hr.css"
# web_include_js = "/assets/shaigan_hr/js/shaigan_hr.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "shaigan_hr/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Leave Application" : "shaigan_hr/overrides/leave_application.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "shaigan_hr/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "shaigan_hr.utils.jinja_methods",
# 	"filters": "shaigan_hr.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "shaigan_hr.install.before_install"
# after_install = "shaigan_hr.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "shaigan_hr.uninstall.before_uninstall"
# after_uninstall = "shaigan_hr.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "shaigan_hr.utils.before_app_install"
# after_app_install = "shaigan_hr.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "shaigan_hr.utils.before_app_uninstall"
# after_app_uninstall = "shaigan_hr.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "shaigan_hr.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Leave Application": "shaigan_hr.shaigan_hr.overrides.quarter_leave_application.QuarterLeaveApplication" ,
  "Shift Type": "shaigan_hr.shaigan_hr.overrides.override_shift_type.OverrideShiftType" ,
	"Attendance" : "shaigan_hr.shaigan_hr.overrides.override_attendance.OverrideAttendance" ,
  "Employee Checkin" : "shaigan_hr.shaigan_hr.overrides.override_employee_checkin.OverrideEmployeeCheckin" ,
  "Salary Slip" : "shaigan_hr.shaigan_hr.overrides.override_salary_slip.OverrideSalarySlip" ,
  "Employee Increment" : "shaigan_hr.shaigan_hr.overrides.override_employee_increment.OverrideEmployeeIncrement",
  "Arrears Process" : "shaigan_hr.shaigan_hr.overrides.override_arrears_process.OverrideArrearsProcess",
  "Compensatory Leave Request" : "shaigan_hr.shaigan_hr.overrides.compensatory_leave_request.OverrideCompensatoryLeaveRequest" ,
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Designation":{
		"before_save": "shaigan_hr.shaigan_hr.events.designation.designation_allowance_update"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"shaigan_hr.tasks.all"
# 	],
# 	"daily": [
# 		"shaigan_hr.tasks.daily"
# 	],
# 	"hourly": [
# 		"shaigan_hr.tasks.hourly"
# 	],
# 	"weekly": [
# 		"shaigan_hr.tasks.weekly"
# 	],
# 	"monthly": [
# 		"shaigan_hr.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "shaigan_hr.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	"hrms.hr.doctype.leave_application.leave_application.get_number_of_leave_days" : "shaigan_hr.shaigan_hr.overrides.quarter_leave_application.get_number_of_leave_day",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "shaigan_hr.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["shaigan_hr.utils.before_request"]
# after_request = ["shaigan_hr.utils.after_request"]

# Job Events
# ----------
# before_job = ["shaigan_hr.utils.before_job"]
# after_job = ["shaigan_hr.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"shaigan_hr.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

