frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Create Pick List"), function () {
                frappe.db.get_single_value("Stock Settings", "picking_based_on_default_warehouse")
                    .then(is_based_on_default => {
                        console.log("Picking based on default warehouse:", is_based_on_default);
                        
                        if (is_based_on_default) {
                            // ✅ If setting is checked → use grouped method
                            frappe.call({
                                method: "warehouse_managment.custom_methods.create_pick_list_from_sales_order.create_picklists_grouped_by_warehouse",
                                args: { sales_order: frm.doc.name },
                                callback: function (r) {
                                    if (r.message) {
                                        r.message.forEach(pl => {
                                            frappe.show_alert({
                                                message: __("Pick List {0} created", [pl]),
                                                indicator: "green"
                                            });
                                        });
                                    }
                                }
                            });
                        } else {
                            // 🚨 Else → prompt user to choose a warehouse
                            frappe.prompt(
                                [
                                    {
                                        fieldtype: "Link",
                                        label: "Warehouse",
                                        fieldname: "warehouse",
                                        options: "Warehouse",
                                        reqd: 1
                                    }
                                ],
                                (values) => {
                                    frappe.call({
                                        method: "warehouse_managment.custom_methods.create_pick_list_from_sales_order.create_picklist_for_single_warehouse",
                                        args: {
                                            sales_order: frm.doc.name,
                                            warehouse: values.warehouse
                                        },
                                        callback: function (r) {
                                            if (r.message) {
                                                frappe.show_alert({
                                                    message: __("Pick List {0} created", [r.message]),
                                                    indicator: "green"
                                                });
                                            }
                                        }
                                    });
                                },
                                __("Select Warehouse"),
                                __("Create")
                            );
                        }
                    });
            });
        }
    }
});
