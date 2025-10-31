import frappe
import json
from collections import defaultdict

@frappe.whitelist()
def create_delivery_note_from_picklists(picklists):
    if isinstance(picklists, str):
        picklists = json.loads(picklists)

    if not picklists:
        frappe.throw("No Pick Lists selected")

    # Group picklists by Sales Order
    so_picklist_map = defaultdict(list)

    for pl_name in picklists:
        pl = frappe.get_doc("Pick List", pl_name)

        if pl.docstatus != 1:
            frappe.throw(f"Pick List {pl_name} must be submitted before creating Delivery Note")

        if not pl.locations:
            frappe.throw(f"Pick List {pl_name} has no items in locations table")

        sales_orders = {loc.sales_order for loc in pl.locations if loc.sales_order}

        if not sales_orders:
            frappe.throw(f"Pick List {pl_name} has no linked Sales Order")

        if len(sales_orders) > 1:
            frappe.throw(f"Pick List {pl_name} contains items from multiple Sales Orders: {', '.join(sales_orders)}")

        so_picklist_map[sales_orders.pop()].append(pl)

    delivery_notes = []

    # Create one DN per Sales Order
    for sales_order, pls in so_picklist_map.items():
        dn = frappe.new_doc("Delivery Note")
        dn.customer = frappe.db.get_value("Sales Order", sales_order, "customer")
        dn.sales_order = sales_order

        for pl in pls:
            for loc in pl.locations:
                dn.append("items", {
                    "item_code": loc.item_code,
                    "item_name": loc.item_name,
                    "uom": loc.uom,
                    "conversion_factor": loc.conversion_factor,
                    "qty": loc.qty,
                    "against_sales_order": sales_order,
                    "so_detail": loc.sales_order_item,
                    "warehouse": loc.warehouse,
                })

        dn.insert(ignore_permissions=True)
        dn.submit()
        delivery_notes.append(dn.name)

    return delivery_notes
