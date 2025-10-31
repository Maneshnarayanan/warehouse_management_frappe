
frappe.views.ListView = class ListView extends frappe.views.ListView {
    get_menu_items() {
        let items = super.get_menu_items();

        // check client-side permissions (from boot)
        if (frappe.boot.user.can_write.includes("List View Settings")) {
            if (this.get_view_settings) {
                items.push(this.get_view_settings());
            }
        }

        return items;
    }
};
