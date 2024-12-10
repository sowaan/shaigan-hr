// Copyright (c) 2024, Sowaan and contributors
// For license information, please see license.txt

frappe.ui.form.on("ZKT Setting", {
    refresh(frm) {
        frm.add_custom_button('Make Token', async () => {
            frappe.call({
                method: "get_token",
                doc: frm.doc,
                freeze: true,
                freeze_message: __("Wait..."),
                callback: function (r) {
                    frm.reload_doc();
                }
            });
        })

        frm.add_custom_button('Get Logs', async () => {
            frappe.call({
                method: "shaigan_hr.shaigan_hr.doctype.zkt_setting.zkt_setting.get_zkt_log",
                args: {
                    setting: frm.doc,
                },
                freeze: true,
                freeze_message: __("Wait..."),
                callback: function (r) {
                    frm.reload_doc();
                }
            });
        })
    },
});
