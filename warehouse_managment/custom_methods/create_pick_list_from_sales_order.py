import frappe
from frappe.utils import flt, cint
from silent_print.utils.print_format import print_silently
from frappe import _

from frappe.realtime import publish_realtime


# ------------------ VALIDATE CONVERSION FACTORS ------------------ #
def validate_conversion_factors(so):
    """Ensure all items in SO have valid conversion factors defined."""
    missing_items = []
    for item in so.items:
        cf = frappe.db.get_value("UOM Conversion Detail", {"parent": item.item_code, "uom": item.uom}, "conversion_factor")
        if not cf and not item.conversion_factor:
            missing_items.append(item.item_code)
    if missing_items:
        frappe.throw(
            _("The following Items are missing UOM Conversion Factor(s): {0}").format(", ".join(missing_items))
        )

# ------------------ MULTI WAREHOUSE PICK LIST ------------------ #
@frappe.whitelist()
def create_picklists_grouped_by_warehouse(sales_order):
    
    so = frappe.get_doc("Sales Order", sales_order)

    # group items by warehouse
    wh_items = {}
    for item in so.items:
        if flt(item.delivered_qty) < flt(item.qty):
            pending_qty = flt(item.qty) - flt(item.delivered_qty)
            default_wh = frappe.db.get_value("Item", item.item_code, "default_warehouse")
            if pending_qty > 0:
                wh_items.setdefault(default_wh, []).append({
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "uom": item.uom,
                    "conversion_factor": item.conversion_factor or 1,
                    "sales_order": so.name,
                    "sales_order_item": item.name,
                    "qty": pending_qty,
                    "stock_qty": pending_qty * (flt(item.conversion_factor) or 1),
                    "warehouse": default_wh,
                })

    if not wh_items:
        frappe.throw("No pending items to pick for this Sales Order.")

    picklists = []
    frappe.msgprint(f"Creating {len(wh_items)} picklists (one per warehouse)")

    for wh, items in wh_items.items():
        pick_list = frappe.new_doc("Pick List")
        pick_list.purpose = "Delivery"
        pick_list.sales_order = so.name
        # pick_list.pick_manually = 1      
        pick_list.parent_warehouse= wh
        for it in items:
            pick_list.append("locations", {
                "item_code": it["item_code"],
                "item_name": it["item_name"],
                "uom": it["uom"],
                "conversion_factor": it["conversion_factor"],
                "qty": it["qty"],
                "stock_qty": it["stock_qty"],
                "warehouse": it["warehouse"],
                "sales_order": it["sales_order"],
                "sales_order_item": it["sales_order_item"],
            })

        pick_list.insert(ignore_permissions=True)       
        picklists.append(pick_list.name)
        pick_list.pick_manually = 1    
        pick_list.save()   
        print_pick_list(pick_list.name, wh)
        frappe.enqueue(
            method=send_notification_to_assigned_users,
            queue='short',
            timeout=300,
            is_async=True,
            job_name=f"Notify Users for Pick List {pick_list.name}",
            pick_list_name=pick_list.name,
            warehouse=wh
        )
        frappe.msgprint(f"✅ Created Pick List: {pick_list.name} for Warehouse: {wh}")

    return picklists



# ------------------ SINGLE WAREHOUSE PICK LIST ------------------ #

@frappe.whitelist()
def create_picklist_for_single_warehouse(sales_order, warehouse):
    frappe.msgprint(_("Creating Pick List for Sales Order {0} from Warehouse {1}").format(sales_order, warehouse))
    try:
        so = frappe.get_doc("Sales Order", sales_order)
        validate_conversion_factors(so)

        pick_list = frappe.new_doc("Pick List")
        pick_list.company = so.company
        pick_list.customer = so.customer
        pick_list.sales_order = so.name
        pick_list.parent_warehouse = warehouse
        pick_list.purpose = "Delivery"
        pick_list.delivery_date = so.delivery_date or so.transaction_date

        for item in so.items:
            if flt(item.delivered_qty) < flt(item.qty):
                # Ensure conversion factor is not None
                conversion_factor = flt(item.conversion_factor) or 1.0
                stock_qty = flt(item.stock_qty) or (flt(item.qty) * conversion_factor)
                
                pick_list.append("locations", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "description": item.description,
                    "uom": item.uom,
                    "qty": item.qty,
                    "stock_qty": stock_qty,  
                    "sales_order": sales_order,                  
                    "sales_order_item": item.name,
                    "conversion_factor": conversion_factor
                })

        if not pick_list.locations:
            frappe.throw(_("All items are already delivered for Sales Order {0}").format(sales_order))

        
        pick_list.insert(ignore_permissions=True)
        # pick_list.submit()
        pick_list.pick_manually = 1    
        pick_list.save()   
        print_pick_list(pick_list.name, warehouse)
        frappe.enqueue(
            method=send_notification_to_assigned_users,
            queue='short',
            timeout=300,
            is_async=True,
            job_name=f"Notify Users for Pick List {pick_list.name}",
            pick_list_name=pick_list.name,
            warehouse=warehouse
        )
        frappe.msgprint(_("Pick List {0} created successfully").format(pick_list.name))
        return pick_list.name

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Pick List Creation Error")
        frappe.throw(_("Error creating Pick List for {0}: {1}").format(sales_order, str(e)))



# # ------------------ NOTIFY ASSIGNED USERS ------------------ #
def send_notification_to_assigned_users(pick_list_name, warehouse):
    """
    Send realtime notification to users whose dflt_warehouse matches the specified warehouse
    """
    try:
        # Get all users who have the specified warehouse as their dflt_warehouse
        users = frappe.get_all("User",
            filters={
                "dflt_warehouse": warehouse,
                "enabled": 1
            },
            fields=["name", "full_name", "email"]
        )
        
        if not users:
            frappe.log_error(f"No active users found with dflt_warehouse: {warehouse}", "Pick List Notification")
            return
        
        # Get Pick List details for the notification
        pick_list = frappe.get_doc("Pick List", pick_list_name)
        
        # Prepare notification message
        message = _("New Pick List {0} has been created for your warehouse {1}").format(
            pick_list_name, warehouse
        )
        
        notification_subject = _("📦 New Pick List Assigned")
        
        # Send notification to each user
        for user in users:
            user_id = user.name
            
            # Create system notification
            create_system_notification(user_id, notification_subject, message, pick_list_name)
            
            # Send realtime notification
            send_realtime_notification(user_id, message, notification_subject, pick_list_name, warehouse)
        
        frappe.msgprint(_("Notifications sent to {0} users").format(len(users)))
        frappe.log_error(f"Pick List notifications sent to {len(users)} users for warehouse {warehouse}", "Pick List Notification")
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Pick List Notification Error")
        frappe.throw(_("Error sending notifications: {0}").format(str(e)))


def create_system_notification(user_id, subject, message, pick_list_name):
    """
    Create system notification log
    """
    try:
        notification = frappe.get_doc({
            "doctype": "Notification Log",
            "subject": subject,
            "email_content": message,
            "type": "Alert",
            "document_type": "Pick List",
            "document_name": pick_list_name,
            "for_user": user_id,
            "read": 0
        })
        notification.insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Error creating system notification for {user_id}: {str(e)}", "Notification Error")


def send_realtime_notification(user_id, message, title, pick_list_name, warehouse):
    """
    Send realtime notification to specific user
    """
    try:
        # Main alert notification
        publish_realtime(
            event="msgprint",
            message={
                "message": message,
                "title": title,
                "alert": True,
                "indicator": "blue"
            },
            user=user_id
        )
        
        # Custom event for frontend listening with more details
        publish_realtime(
            event="pick_list_assigned",
            message={
                "message": message,
                "title": title,
                "pick_list_name": pick_list_name,
                "warehouse": warehouse,
                "timestamp": frappe.utils.now(),
                "type": "pick_list_alert"
            },
            user=user_id
        )
    except Exception as e:
        frappe.log_error(f"Error sending realtime notification to {user_id}: {str(e)}", "Realtime Notification Error")




# # ------------------ PRINT PICK LIST ------------------ #
def print_pick_list(pick_list_name, warehouse):

    spf = frappe.db.get_value(
        "Silent Print Format",
        {"warehouse": warehouse},
        ["print_format", "default_print_type"],
        as_dict=True
    )

    if not spf:
        frappe.msgprint(f"No Silent Print Format found for warehouse {warehouse}")
        return

    print_silently("Pick List", pick_list_name, spf.print_format, spf.default_print_type)

