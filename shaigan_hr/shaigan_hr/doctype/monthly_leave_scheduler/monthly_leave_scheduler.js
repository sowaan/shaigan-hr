// Copyright (c) 2024, Sowaan and contributors
// For license information, please see license.txt

frappe.ui.form.on("Monthly Leave Scheduler", {
	
    async refresh(frm) {

        if (!frm.doc.workflow_exist)
        {

            frm.set_value('workflow_exist' , 0) ;
            
            var work_flow_doc_name = null ;
            var work_flow_states = null ;

            frm.set_query("workflow_state", function () {
                return {
                    filters: [["Workflow State", "name", "in", null]],
                };
            });
            
            
            await frappe.call({
                method: "shaigan_hr.shaigan_hr.api.api.check_work_flow_exist",
                args: {
                    doctype: "Leave Application",
                },
                async: false,
                callback: function (r) {
                    if (r.message) {
                        
                        work_flow_doc_name = r.message ;
                        frm.set_df_property("workflow_state", "reqd", 1);
                        frm.set_value('workflow_exist' , 1) ;
                    }
                },
            });
            
            
            if (work_flow_doc_name) 
                {
                    await frappe.call({
                        method: "shaigan_hr.shaigan_hr.api.api.get_workflow_states",
                        args: {
                            docname : work_flow_doc_name ,
                        },
                        async: false,
                        callback: function (r) {
                        if (r.message) {
                            
                            work_flow_states = r.message ;
                            frm.set_query("workflow_state", function () {
                                return {
                                    filters: [["Workflow State", "name", "in", r.message]],
                                };
                            });

                        }
                    },
                });

            }

        }
	},

});
