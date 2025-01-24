
import frappe

def designation_allowance_update(self, method):
   if self.custom_allowance:
        for row in self.custom_allowance:
            if row.company:
                all_employees = frappe.get_list("Employee", filters={"designation": self.name, "company": row.company})
                for employee in all_employees:
                    if row.maintenance_allowance:
                        frappe.db.set_value("Employee", employee.name, "custom_maintenance_allowances_amount", row.maintenance_allowance)
                    if row.vehicle_allowance:
                        frappe.db.set_value("Employee", employee.name, "custom_vehicle_allowances_amount", row.vehicle_allowance)
                    if row.inflation_allowance:
                        frappe.db.set_value("Employee", employee.name, "custom_inflation_allowance_amount", row.inflation_allowance)
                    if row.postage_allowance:
                        frappe.db.set_value("Employee", employee.name, "custom_postage_allowance", row.postage_allowance)
                    if row.entertainment_allowance:
                        frappe.db.set_value("Employee", employee.name, "custom_entertainment_allowance_", row.entertainment_allowance)
                    if row.conveyance_allowance:
                        frappe.db.set_value("Employee", employee.name, "custom_conveyance_allowance_amount_1", row.conveyance_allowance)