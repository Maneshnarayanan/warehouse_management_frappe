
frappe.ui.form.on("Purchase Receipt", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Move to Warehouse'), () => {
                frappe.call({
                    method:"warehouse_managment.custom_methods.move_to_default_wh.move_items_to_default_warehouse",
                    args: {
                        purchase_receipt: frm.doc.name
                    },
                    callback: function(r) {
                        if (!r.exc && r.message) {
                            frappe.msgprint(__("Stock Entry created: " + r.message.stock_entry));
                            frm.reload_doc();
                            // Redirect to Stock Entry form
                            window.location.href = r.message.redirect_url;
                        }
                    }
                });
            });
        }
    }
});
