import frappe
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	date_diff,
	flt,
	formatdate,
	get_first_day,
	getdate,
)
from frappe.query_builder.functions import Count, Sum
from hrms.payroll.doctype.payroll_period.payroll_period import get_period_factor
from hrms.payroll.doctype.salary_slip.salary_slip_loan_utils import set_loan_repayment
from hrms.hr.utils import validate_active_employee
from hrms.payroll.doctype.payroll_entry.payroll_entry import get_salary_withholdings, get_start_end_dates

from hrms.payroll.doctype.salary_slip.salary_slip import (SalarySlip, calculate_tax_by_tax_slab)
from sowaan_hr.sowaan_hr.api.api import create_salary_adjustment_for_negative_salary

class OverrideSalarySlip(SalarySlip):
    def validate(self):
        self.check_salary_withholding()
        self.status = self.get_status()
        validate_active_employee(self.employee)
        self.validate_dates()
        self.check_existing()

        if not self.salary_slip_based_on_timesheet:
            self.get_date_details()

        if not (len(self.get("earnings")) or len(self.get("deductions"))):
            # get details from salary structure
            self.get_emp_and_working_day_details()
        else:
            self.get_working_days_details(lwp=self.leave_without_pay)

        self.set_salary_structure_assignment()
        self.calculate_net_pay()
        self.compute_year_to_date()
        self.compute_month_to_date()
        self.compute_component_wise_year_to_date()

        self.add_leave_balances()
        self.update_basic_for_month()
        self.pf_calculation()

        max_working_hours = frappe.db.get_single_value(
            "Payroll Settings", "max_working_hours_against_timesheet"
        )
        if max_working_hours:
            if self.salary_slip_based_on_timesheet and (self.total_working_hours > int(max_working_hours)):
                frappe.msgprint(
                    _("Total working hours should not be greater than max working hours {0}").format(
                        max_working_hours
                    ),
                    alert=True,
                )

    def update_basic_for_month(self):
        joining_date_days_diff = 0

        date_of_joining = frappe.db.get_value('Employee' , self.employee , 'date_of_joining')

        if str(date_of_joining) > str(self.start_date) and str(date_of_joining) <= str(self.end_date) :
            joining_date_days_diff = frappe.utils.date_diff(date_of_joining , self.start_date)

        base = 0

        sys_gen_la_list = frappe.get_list('Leave Application',
                                filters={
                                    'employee' : self.employee ,
                                    'custom_system_generated' : 1 ,
                                    'leave_type' : ['!=','Leave Without Pay'] ,
                                    'from_date' : ['between',[self.start_date , self.end_date]] ,
                                    'status' : 'Approved' ,
                                    'docstatus' : 1 ,
                            },fields=['total_leave_days'])

        total_sys_gen_leaves = 0
        quarter_total_sys_gen_leaves = 0

        if sys_gen_la_list :
            for x in sys_gen_la_list :
                total_sys_gen_leaves = total_sys_gen_leaves + x.total_leave_days

        self.custom_system_generated_leave_days = total_sys_gen_leaves

        quarter_sys_gen_la_list = frappe.get_list('Leave Application',
                                        filters={
                                            'employee' : self.employee ,
                                            # 'custom_system_generated' : 1 ,
                                            'leave_type' : 'Leave Without Pay' ,
                                            'from_date' : ['between',[self.start_date , self.end_date]] ,
                                            'status' : 'Approved' ,
                                            'custom_quarter_day' : 1 ,
                                            'docstatus' : 1 ,
                                    },fields=['total_leave_days'])


        if quarter_sys_gen_la_list :
            for y in quarter_sys_gen_la_list :
                quarter_total_sys_gen_leaves = quarter_total_sys_gen_leaves + y.total_leave_days
            
        self.custom_quarter_leave_without_pay = quarter_total_sys_gen_leaves

        ###############################################################################################################
        emp_doc = frappe.get_doc('Employee',self.employee)

        if emp_doc.custom_allow_manual_attendance != 'Yes' :
            self.custom_payment_day = float(30 - (self.total_working_days - self.payment_days)) - float(self.custom_system_generated_leave_days + self.custom_quarter_leave_without_pay)
        else :
            self.custom_payment_day = 30 - joining_date_days_diff

        if self.custom_payment_day < 0 :
            self.custom_payment_day = 0

        pay_days = self.custom_payment_day

        s_s_ass_list = frappe.get_list("Salary Structure Assignment",
                        filters={
                            'employee' : self.employee ,
                            'salary_structure' : self.salary_structure,
                            'from_date': ['<=', self.start_date],
                            'docstatus' : 1,
                        },
                        order_by = 'from_date desc')
        

        # for new Joinee
        if len(s_s_ass_list) == 0:
            s_s_ass_list = frappe.get_list("Salary Structure Assignment",
                        filters={
                            'employee' : self.employee ,
                            'salary_structure' : self.salary_structure,
                            'docstatus' : 1,
                        },
                        order_by = 'from_date desc')
            
        if s_s_ass_list:
            s_s_ass_doc = frappe.get_doc("Salary Structure Assignment",s_s_ass_list[0].name)
            per_day = s_s_ass_doc.base / 30
            
            base = per_day * pay_days
            self.custom_base = base
            self.custom_absent_deduction = per_day * self.absent_days
            self.custom_monthly_salary = s_s_ass_doc.base

            # print(self.custom_base, pay_days, " check pay days \n\n\n\n")

            self.calculate_net_pay()
            self.compute_year_to_date()
            self.compute_month_to_date()
            self.compute_component_wise_year_to_date()
            
        ####### Monthly and Yearly Scholarship Allowance #######

        self.custom_scholarship_monthly = 0
        self.custom_scholarship_annually = 0
        if emp_doc.custom_scholarship :
            
            monthly_amount = 0
            yearly_amount = 0
            
            for row in emp_doc.custom_scholarship :
                monthly_amount = monthly_amount + row.monthly_amount
                yearly_amount = yearly_amount + row.yearly_amount
                
            
            self.custom_scholarship_monthly = monthly_amount
            self.custom_scholarship_annually = 0
            
            pp_list = frappe.get_list("Payroll Period",
                        filters={
                            'company' : self.company ,
                            'start_date' : ['<=' , self.start_date] ,
                            'end_date' : ['>=' , self.end_date ] ,
                        })
            
            if pp_list :
                pp_doc = frappe.get_doc("Payroll Period", pp_list[0].name)
                
                ss_list = frappe.get_list("Salary Slip",
                            filters = {
                                'employee' : self.employee ,
                                'start_date' : ['>=' , pp_doc.start_date ] ,
                                'end_date' : ['<' , self.start_date ] ,
                                'custom_scholarship_annually' : ['>' , 0 ] ,
                                'docstatus' : 1 ,
                            })
                
                if not ss_list :
                    self.custom_scholarship_annually = yearly_amount

        self.calculate_net_pay()
        self.compute_year_to_date()
        self.compute_month_to_date()
        self.compute_component_wise_year_to_date()


        ################################### Calculate Overtime Hours and Amount ###################################
        ot_ap_list = frappe.get_list("Over Time Approval", 
                            filters = {
                                'employee' : self.employee ,
                                'from_date' : self.start_date ,
                                'to_date' : self.end_date ,
                                'docstatus' : 1 ,
                            }
                    )

        if ot_ap_list :
            ot_ap_doc = frappe.get_doc('Over Time Approval', ot_ap_list[0].name)
            
            self.custom_over_time_approval = ot_ap_doc.name
            self.custom_overtime_hours = ot_ap_doc.total_approved_ot_hours
            
            if ot_ap_doc.total_approved_ot_hours > 0 :
                shift = None
                req_hrs = 9
                
                for t in ot_ap_doc.overtime_hours :
                    shift = frappe.db.get_value('Attendance' , t.attendance , 'shift' )
                    if shift :
                        req_hrs = frappe.db.get_value('Shift Type' , shift , 'custom_overtime_calculation_hours' )
                
                pr_d = self.custom_monthly_salary / 30
                pr_h = pr_d / req_hrs
            
                self.custom_overtime_amount = pr_h * ot_ap_doc.total_approved_ot_hours

        self.calculate_net_pay()
        self.compute_year_to_date()
        self.compute_month_to_date()
        self.compute_component_wise_year_to_date()

    def pf_calculation(self):
        employee = frappe.get_doc("Employee",self.employee)

        start_date = self.start_date
        end_date = self.end_date
        confirmation_date = employee.final_confirmation_date
        basic_amount = 0
        medical_amount = 0
        payment_days = 0
        base = 0

        if employee.custom_employee_pf_status == "Yes" and confirmation_date:
            if str(confirmation_date) > str(end_date):
                return
            
            if (str(start_date) <= str(confirmation_date) <= str(end_date)): 
                payment_days = frappe.utils.date_diff(end_date , confirmation_date) + 1
                        
                for i in self.earnings:
                    if i.salary_component == "Basic":
                        basic_amount = basic_amount+ i.amount
                    if i.salary_component == "Medical":
                        medical_amount = medical_amount + i.amount
                            
                if basic_amount and medical_amount:
                    base = (((basic_amount + medical_amount) / 30) * payment_days) * 0.0833

                salary_structure_list = frappe.get_list(
                "Salary Structure Assignment",
                filters={"employee": self.employee},
                order_by="creation desc",
                )
                exit_between_payroll_date = frappe.db.exists("Salary Structure Assignment", {
                    "employee": self.employee,
                    "from_date": ["Between", [start_date, end_date]],
                })
                # print(exit_between_payroll_date, "pf Salary Slip \n")
                if exit_between_payroll_date:
                    if len(salary_structure_list) > 1:
                        salary_structure = frappe.get_doc("Salary Structure Assignment", exit_between_payroll_date)
                        employee_arrears_list = frappe.get_all("Employee Arrears",
                                                                            {
                                                                                "employee":self.employee,
                                                                                "from_date": self.start_date,
                                                                                "to_date": self.end_date,
                                                                                "docstatus": 1
                                                                            })
                        
                        basic_arrears = 0
                        if employee_arrears_list:
                            employee_arrears = frappe.get_doc("Employee Arrears",employee_arrears_list[0].name)
                            for i in employee_arrears.e_a_earnings:
                                basic_arrears = basic_arrears + i.amount

                        new_base = 0
                        payment_days = frappe.utils.date_diff(end_date , salary_structure.from_date) + 1
                            
                                    
                        if basic_arrears:
                            new_base = (basic_arrears * 0.6667) * 0.0833
                            # print(new_base, salary_structure, "pf Salary Slip \n")
                        base = new_base + base
            # frappe.msgprint(str(base))
            else:
                basic_amount = 0
                medical_amount = 0
                payment_days = 0
                base = 0
                salary_structure_list = frappe.get_all(
                "Salary Structure Assignment",
                filters={"employee": self.employee},
                order_by="creation desc",
                )
                # print(salary_structure_list, "\n")
               
                # print(exit_between_payroll_date, "pf Salary Slip \n")
                if len(salary_structure_list) > 1:
                    currect_month_structure = frappe.db.exists("Salary Structure Assignment", {
                        "employee": self.employee,
                        "from_date": ["Between", [start_date, end_date]],
                        "docstatus": 1,
                    })
                    if currect_month_structure:
                        salary_structure = frappe.get_doc("Salary Structure Assignment",salary_structure_list[1].name)
                        # print(salary_structure.base, "structure Salary Slip \n")
                        base = (salary_structure.base*0.60003+ salary_structure.base*0.06667) * 0.0833
                        # print(base, "pf Salary Slip \n")
                        salary_structure = frappe.get_doc("Salary Structure Assignment",salary_structure_list[0].name)
                        employee_arrears_list = frappe.get_all("Employee Arrears",
                                                                        {
                                                                            "employee":self.employee,
                                                                                "from_date": self.start_date,
                                                                                "to_date": self.end_date,
                                                                                "docstatus": 1
                                                                            })
                        
                        basic_arrears = 0
                        if employee_arrears_list:
                            employee_arrears = frappe.get_doc("Employee Arrears",employee_arrears_list[0].name)
                            for i in employee_arrears.e_a_earnings:
                                basic_arrears = basic_arrears + i.amount

                        new_base = 0
                        payment_days = frappe.utils.date_diff(end_date , salary_structure.from_date) + 1
                            
                                    
                        if basic_arrears:
                            new_base = (basic_arrears * 0.6667) * 0.0833
                            # print(new_base, salary_structure, "pf Salary Slip \n")
                        base = new_base + base
                    else:
                        salary_structure = frappe.get_doc("Salary Structure Assignment",salary_structure_list[0].name)
                        base = (salary_structure.base*0.60003+ salary_structure.base*0.06667) * 0.0833
                        employee_arrears_list = frappe.get_all("Employee Arrears",
                                                                        {
                                                                            "employee":self.employee,
                                                                                "from_date": self.start_date,
                                                                                "to_date": self.end_date,
                                                                                "docstatus": 1
                                                                            })


                        
                        basic_arrears = 0
                        if employee_arrears_list:
                            employee_arrears = frappe.get_doc("Employee Arrears",employee_arrears_list[0].name)
                            for i in employee_arrears.e_a_earnings:
                                basic_arrears = basic_arrears + i.amount

                        new_base = 0
                                    
                        if basic_arrears:
                            new_base = (basic_arrears * 0.6667) * 0.0833
                            # print(new_base, salary_structure, "pf Salary Slip \n")

                        base = new_base + base
                        # print(base, "checking")

                else:
                    salary_structure = frappe.get_doc("Salary Structure Assignment",salary_structure_list[0].name)
                    # print(salary_structure, "pf Salary Slip \n")
                    base = (salary_structure.base*0.60003+ salary_structure.base*0.06667) * 0.0833


            # frappe.msgprint(str(base))
        # print(base, "pf Salary Slip  263 \n")
        self.custom_pf_deduction = base
        self.calculate_net_pay()
        self.compute_year_to_date()
        self.compute_month_to_date()
        self.compute_component_wise_year_to_date()
        # print(self.custom_pf_deduction, "pf Salary Slip \n")
    
    def check_salary_withholding(self):
        withholding = get_salary_withholdings(self.start_date, self.end_date, self.employee)
        if withholding:
            self.salary_withholding = withholding[0].salary_withholding
            self.salary_withholding_cycle = withholding[0].salary_withholding_cycle
        else:
            self.salary_withholding = None

    def validate_dates(self):
        self.validate_from_to_dates("start_date", "end_date")

        if not self.joining_date:
            frappe.throw(
                _("Please set the Date Of Joining for employee {0}").format(frappe.bold(self.employee_name))
            )

        if date_diff(self.end_date, self.joining_date) < 0:
            frappe.throw(_(f'''Cannot create Salary Slip for Employee joining after Payroll Period {self.employee}'''))

        if self.relieving_date and date_diff(self.relieving_date, self.start_date) < 0:
            frappe.throw(_("Cannot create Salary Slip for Employee who has left before Payroll Period"))


    def check_existing(self):
        if not self.salary_slip_based_on_timesheet:
            ss = frappe.qb.DocType("Salary Slip")
            query = (
                frappe.qb.from_(ss)
                .select(ss.name)
                .where(
                    (ss.start_date == self.start_date)
                    & (ss.end_date == self.end_date)
                    & (ss.docstatus != 2)
                    & (ss.employee == self.employee)
                    & (ss.name != self.name)
                )
            )

            if self.payroll_entry:
                query = query.where(ss.payroll_entry == self.payroll_entry)

            ret_exist = query.run()

            if ret_exist:
                frappe.throw(
                    _("Salary Slip of employee {0} already created for this period").format(self.employee)
                )
        else:
            for data in self.timesheets:
                if frappe.db.get_value("Timesheet", data.time_sheet, "status") == "Payrolled":
                    frappe.throw(
                        _("Salary Slip of employee {0} already created for time sheet {1}").format(
                            self.employee, data.time_sheet
                        )
                    )

    def get_date_details(self):
        if not self.end_date:
            date_details = get_start_end_dates(self.payroll_frequency, self.start_date or self.posting_date)
            self.start_date = date_details.start_date
            self.end_date = date_details.end_date

    @frappe.whitelist()
    def get_emp_and_working_day_details(self):
        """First time, load all the components from salary structure"""
        if self.employee:
            self.set("earnings", [])
            self.set("deductions", [])

            if not self.salary_slip_based_on_timesheet:
                self.get_date_details()

            self.validate_dates()

            # getin leave details
            self.get_working_days_details()
            struct = self.check_sal_struct()

            if struct:
                self.set_salary_structure_doc()
                self.salary_slip_based_on_timesheet = (
                    self._salary_structure_doc.salary_slip_based_on_timesheet or 0
                )
                self.set_time_sheet()
                self.pull_sal_struct()

    def get_working_days_details(self, lwp=None, for_preview=0):
        payroll_settings = frappe.get_cached_value(
            "Payroll Settings",
            None,
            (
                "payroll_based_on",
                "include_holidays_in_total_working_days",
                "consider_marked_attendance_on_holidays",
                "daily_wages_fraction_for_half_day",
                "consider_unmarked_attendance_as",
            ),
            as_dict=1,
        )

        consider_marked_attendance_on_holidays = (
            payroll_settings.include_holidays_in_total_working_days
            and payroll_settings.consider_marked_attendance_on_holidays
        )

        daily_wages_fraction_for_half_day = flt(payroll_settings.daily_wages_fraction_for_half_day) or 0.5

        working_days = date_diff(self.end_date, self.start_date) + 1
        if for_preview:
            self.total_working_days = working_days
            self.payment_days = working_days
            return

        holidays = self.get_holidays_for_employee(self.start_date, self.end_date)
        working_days_list = [add_days(getdate(self.start_date), days=day) for day in range(0, working_days)]

        if not cint(payroll_settings.include_holidays_in_total_working_days):
            working_days_list = [i for i in working_days_list if i not in holidays]

            working_days -= len(holidays)
            if working_days < 0:
                frappe.throw(_("There are more holidays than working days this month."))

        if not payroll_settings.payroll_based_on:
            frappe.throw(_("Please set Payroll based on in Payroll settings"))

        if payroll_settings.payroll_based_on == "Attendance":
            actual_lwp, absent = self.calculate_lwp_ppl_and_absent_days_based_on_attendance(
                holidays, daily_wages_fraction_for_half_day, consider_marked_attendance_on_holidays
            )
            self.absent_days = absent
        else:
            actual_lwp = self.calculate_lwp_or_ppl_based_on_leave_application(
                holidays, working_days_list, daily_wages_fraction_for_half_day
            )

        if not lwp:
            lwp = actual_lwp
        elif lwp != actual_lwp:
            frappe.msgprint(
                _("Leave Without Pay does not match with approved {} records").format(
                    payroll_settings.payroll_based_on
                )
            )

        self.leave_without_pay = lwp
        self.total_working_days = working_days

        payment_days = self.get_payment_days(payroll_settings.include_holidays_in_total_working_days)

        if flt(payment_days) > flt(lwp):
            self.payment_days = flt(payment_days) - flt(lwp)

            if payroll_settings.payroll_based_on == "Attendance":
                self.payment_days -= flt(absent)

            consider_unmarked_attendance_as = payroll_settings.consider_unmarked_attendance_as or "Present"

            if (
                payroll_settings.payroll_based_on == "Attendance"
                and consider_unmarked_attendance_as == "Absent"
            ):
                unmarked_days = self.get_unmarked_days(
                    payroll_settings.include_holidays_in_total_working_days, holidays
                )
                self.absent_days += unmarked_days  # will be treated as absent
                self.payment_days -= unmarked_days
        else:
            self.payment_days = 0


    def set_salary_structure_assignment(self):
        self._salary_structure_assignment = frappe.db.get_value(
            "Salary Structure Assignment",
            {
                "employee": self.employee,
                "salary_structure": self.salary_structure,
                "from_date": ("<=", self.actual_start_date),
                "docstatus": 1,
            },
            "*",
            order_by="from_date desc",
            as_dict=True,
        )

        if not self._salary_structure_assignment:
            frappe.throw(
                _(
                    "Please assign a Salary Structure for Employee {0} applicable from or before {1} first"
                ).format(
                    frappe.bold(self.employee_name),
                    frappe.bold(formatdate(self.actual_start_date)),
                )
            )

    def calculate_net_pay(self, skip_tax_breakup_computation: bool = False):
        def set_gross_pay_and_base_gross_pay():
            self.gross_pay = self.get_component_totals("earnings", depends_on_payment_days=1)
            self.base_gross_pay = flt(
                flt(self.gross_pay) * flt(self.exchange_rate), self.precision("base_gross_pay")
            )

        if self.salary_structure:
            self.calculate_component_amounts("earnings")

        # get remaining numbers of sub-period (period for which one salary is processed)
        if self.payroll_period:
            self.remaining_sub_periods = get_period_factor(
                self.employee,
                self.start_date,
                self.end_date,
                self.payroll_frequency,
                self.payroll_period,
                joining_date=self.joining_date,
                relieving_date=self.relieving_date,
            )[1]

        set_gross_pay_and_base_gross_pay()

        if self.salary_structure:
            self.calculate_component_amounts("deductions")

        set_loan_repayment(self)

        self.set_precision_for_component_amounts()
        self.set_net_pay()
        if not skip_tax_breakup_computation:
            self.compute_income_tax_breakup()


    def compute_year_to_date(self):
        year_to_date = 0
        period_start_date, period_end_date = self.get_year_to_date_period()

        salary_slip_sum = frappe.get_list(
            "Salary Slip",
            fields=["sum(net_pay) as net_sum", "sum(gross_pay) as gross_sum"],
            filters={
                "employee": self.employee,
                "start_date": [">=", period_start_date],
                "end_date": ["<", period_end_date],
                "name": ["!=", self.name],
                "docstatus": 1,
            },
        )

        year_to_date = flt(salary_slip_sum[0].net_sum) if salary_slip_sum else 0.0
        gross_year_to_date = flt(salary_slip_sum[0].gross_sum) if salary_slip_sum else 0.0

        year_to_date += self.net_pay
        gross_year_to_date += self.gross_pay
        self.year_to_date = year_to_date
        self.gross_year_to_date = gross_year_to_date


    def compute_month_to_date(self):
        month_to_date = 0
        first_day_of_the_month = get_first_day(self.start_date)
        salary_slip_sum = frappe.get_list(
            "Salary Slip",
            fields=["sum(net_pay) as sum"],
            filters={
                "employee": self.employee,
                "start_date": [">=", first_day_of_the_month],
                "end_date": ["<", self.start_date],
                "name": ["!=", self.name],
                "docstatus": 1,
            },
        )

        month_to_date = flt(salary_slip_sum[0].sum) if salary_slip_sum else 0.0

        month_to_date += self.net_pay
        self.month_to_date = month_to_date


    def compute_component_wise_year_to_date(self):
        period_start_date, period_end_date = self.get_year_to_date_period()

        ss = frappe.qb.DocType("Salary Slip")
        sd = frappe.qb.DocType("Salary Detail")

        for key in ("earnings", "deductions"):
            for component in self.get(key):
                year_to_date = 0
                component_sum = (
                    frappe.qb.from_(sd)
                    .inner_join(ss)
                    .on(sd.parent == ss.name)
                    .select(Sum(sd.amount).as_("sum"))
                    .where(
                        (ss.employee == self.employee)
                        & (sd.salary_component == component.salary_component)
                        & (ss.start_date >= period_start_date)
                        & (ss.end_date < period_end_date)
                        & (ss.name != self.name)
                        & (ss.docstatus == 1)
                    )
                ).run()

                year_to_date = flt(component_sum[0][0]) if component_sum else 0.0
                year_to_date += component.amount
                component.year_to_date = year_to_date


    def add_leave_balances(self):
        self.set("leave_details", [])

        if frappe.db.get_single_value("Payroll Settings", "show_leave_balances_in_salary_slip"):
            from hrms.hr.doctype.leave_application.leave_application import get_leave_details

            leave_details = get_leave_details(self.employee, self.end_date, True)

            for leave_type, leave_values in leave_details["leave_allocation"].items():
                self.append(
                    "leave_details",
                    {
                        "leave_type": leave_type,
                        "total_allocated_leaves": flt(leave_values.get("total_leaves")),
                        "expired_leaves": flt(leave_values.get("expired_leaves")),
                        "used_leaves": flt(leave_values.get("leaves_taken")),
                        "pending_leaves": flt(leave_values.get("leaves_pending_approval")),
                        "available_leaves": flt(leave_values.get("remaining_leaves")),
                    },
                )

    def update_payment_status_for_gratuity(self):
        additional_salary = frappe.db.get_all(
            "Additional Salary",
            filters={
                "payroll_date": ("between", [self.start_date, self.end_date]),
                "employee": self.employee,
                "ref_doctype": "KSA Gratuity",
                "docstatus": 1,
            },
            fields=["ref_docname", "name"],
            limit=1,
        )

        if additional_salary:
            status = "Paid" if self.docstatus == 1 else "Unpaid"
            if additional_salary[0].name in [entry.additional_salary for entry in self.earnings]:
                frappe.db.set_value("KSA Gratuity", additional_salary[0].ref_docname, "status", status)

    def get_tax_paid_in_period(self, start_date, end_date, tax_component):
		# find total_tax_paid, tax paid for benefit, additional_salary
        total_tax_paid = self.get_salary_slip_details(
            start_date,
            end_date,
            parentfield="deductions",
            salary_component=tax_component,
            variable_based_on_taxable_salary=1,
        )

        tax_deducted_till_date = self.get_opening_for("tax_deducted_till_date", start_date, end_date)

        # Minus the amount from annual tax that is already paid to tax authorities
        total_extra_tax = 0
        if frappe.db.exists("DocType", "Paid Income Tax"):
            total_extra_tax = flt(frappe.db.sql("""
                select 
                    sum(pit.amount) 
                from 
                    `tabPaid Income Tax` pit
                where
                    pit.docstatus=1
                    and %(from_date)s>=pit.period_from
                    and  %(to_date)s<=pit.period_to
                    and pit.employee=%(employee)s
            """,{
                "employee": self.employee,
                "from_date": start_date,
                "to_date": end_date
            })[0][0])

        # Minus the previous additional monthly tax
        extra_current_tax_amount = 0
        if frappe.db.exists("DocType", "Paid Income Tax Monthly"):
            extra_current_tax_amount = flt(frappe.db.sql("""
                select 
                    sum(pitm.amount) 
                from 
                    `tabPaid Income Tax Monthly` pitm
                where
                    pitm.docstatus=1
                    and %(from_date)s>=pitm.period_from
                    and  %(to_date)s<=pitm.period_to
                    and pitm.payroll_date < %(from_date)s
                    and pitm.payroll_date < %(to_date)s
                    and pitm.employee=%(employee)s
            """,{
                "employee": self.employee,
                "from_date": self.start_date,
                "to_date": self.end_date
            })[0][0])

            
        return total_tax_paid + tax_deducted_till_date + total_extra_tax + extra_current_tax_amount
    
    def calculate_variable_tax(self, tax_component):
        self.previous_total_paid_taxes = self.get_tax_paid_in_period(
            self.payroll_period.start_date, self.start_date, tax_component
        )


        # Structured tax amount
        eval_locals, default_data = self.get_data_for_eval()
        self.total_structured_tax_amount = calculate_tax_by_tax_slab(
            self.total_taxable_earnings_without_full_tax_addl_components,
            self.tax_slab,
            self.whitelisted_globals,
            eval_locals,
        )

        self.current_structured_tax_amount = (
            self.total_structured_tax_amount - self.previous_total_paid_taxes
        ) / self.remaining_sub_periods

        # Total taxable earnings with additional earnings with full tax
        self.full_tax_on_additional_earnings = 0.0
        if self.current_additional_earnings_with_full_tax:
            self.total_tax_amount = calculate_tax_by_tax_slab(
                self.total_taxable_earnings, self.tax_slab, self.whitelisted_globals, eval_locals
            )
            self.full_tax_on_additional_earnings = self.total_tax_amount - self.total_structured_tax_amount

        current_tax_amount = self.current_structured_tax_amount + self.full_tax_on_additional_earnings
        if flt(current_tax_amount) < 0:
            current_tax_amount = 0

        self._component_based_variable_tax[tax_component].update(
            {
                "previous_total_paid_taxes": self.previous_total_paid_taxes,
                "total_structured_tax_amount": self.total_structured_tax_amount,
                "current_structured_tax_amount": self.current_structured_tax_amount,
                "full_tax_on_additional_earnings": self.full_tax_on_additional_earnings,
                "current_tax_amount": current_tax_amount,
            }
        )

        # Minus the amount from monthly tax that is already paid to tax authorities
        extra_current_tax_amount = 0
        if frappe.db.exists("DocType", "Paid Income Tax Monthly"):
            extra_current_tax_amount = flt(frappe.db.sql("""
                select 
                    sum(pitm.amount) 
                from 
                    `tabPaid Income Tax Monthly` pitm
                where
                    pitm.docstatus=1
                    and %(from_date)s>=pitm.period_from
                    and  %(to_date)s<=pitm.period_to
                    and %(from_date)s<=pitm.payroll_date
                    and  %(to_date)s>=pitm.payroll_date
                    and pitm.employee=%(employee)s
            """,{
                "employee": self.employee,
                "from_date": self.start_date,
                "to_date": self.end_date
            })[0][0])

        return current_tax_amount - extra_current_tax_amount

    def before_save(self) :

        if self.custom_adjust_negative_salary == 1 and self.custom_check_adjustment == 1 and self.net_pay < 0 :
            create_salary_adjustment_for_negative_salary(self.name)
        
        elif self.net_pay < 0 :
            self.custom_adjust_negative_salary = 0

        self.custom_check_adjustment = 0

        self.calculate_net_pay()
        self.compute_year_to_date()
        self.compute_month_to_date()
        self.compute_component_wise_year_to_date()





