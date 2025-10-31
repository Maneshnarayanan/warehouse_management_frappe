frappe.listview_settings['Pick List'] = {
    onload: function(listview) {
        listview.page.add_actions_menu_item(__('Create Delivery Note'), function() {
            let selected = listview.get_checked_items();
            if (!selected.length) {
                frappe.msgprint(__('Please select Pick Lists.'));
                return;
            }
            let picklists = selected.map(d => d.name);

            frappe.call({
                method: "warehouse_managment.custom_methods.create_delivery_note.create_delivery_note_from_picklists",
                args: { picklists: picklists },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: __('Delivery Notes Created'),
                            indicator: 'green',
                            message: Array.isArray(r.message) 
                                ? r.message.join('<br>') 
                                : r.message
                        });
                        listview.refresh();
                    }
                }
            });
        });
    }
};
