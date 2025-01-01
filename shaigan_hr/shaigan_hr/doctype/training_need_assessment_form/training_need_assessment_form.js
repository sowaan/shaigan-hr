// Copyright (c) 2024, Sowaan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Training Need Assessment Form", {
	refresh(frm) {

	},
});
frappe.ui.form.on("Essential Functions Table", {
    job_duty_details_add(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        let row_index = frm.doc.job_duty_details.indexOf(row) + 1;
        
        // Update the job_duty field
        frappe.model.set_value(cdt, cdn, "job_duty", `Job Duty #${row_index}`);
    }
});

frappe.ui.form.on("Domain A Table", {
    domain_a_table_add(frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        let row_index = frm.doc.domain_a_table.indexOf(row) + 1;
        frappe.model.set_value(cdt, cdn, "job_duty", `Job Duty #${row_index}`);
    }
});
