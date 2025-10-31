import frappe
from frappe.utils import nowdate

@frappe.whitelist()
def move_items_to_default_warehouse(purchase_receipt):
    """Create one Stock Entry to move all items of a Purchase Receipt to their default warehouses"""
    pr_doc = frappe.get_doc("Purchase Receipt", purchase_receipt)

    # Create Stock Entry
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Transfer"
    se.posting_date = nowdate()
    se.purchase_receipt = pr_doc.name  # link back for reference

    for item in pr_doc.items:
        default_wh = frappe.db.get_value("Item", item.item_code, "default_warehouse")
        if default_wh and item.warehouse != default_wh:
            se.append("items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "uom": item.uom,
                "s_warehouse": item.warehouse,
                "t_warehouse": default_wh,
            })

    if not se.items:
        frappe.throw("All items are already in their default warehouses.")

    se.insert(ignore_permissions=True)

    # Instead of submitting, open it for the user
    return {
        "stock_entry": se.name,
        "redirect_url": f"/app/stock-entry/{se.name}"
    }
