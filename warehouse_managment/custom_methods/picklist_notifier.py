import frappe
from frappe.utils import now

def notify_creator(doc, method):
    """
    Notify the Pick List creator when picked_qty changes.
    Creates both push notification and realtime toast (and a msgprint fallback).
    """
    # Quick debug log (remove in production)
    frappe.logger().debug(f"notify_creator called for {doc.doctype} {doc.name} by {frappe.session.user}")

    # Skip if newly created
    if getattr(doc.flags, "in_insert", False):
        frappe.logger().debug("Skipping notify: in_insert")
        return

    # Skip if updated by the creator themselves
    if doc.owner == frappe.session.user:
        frappe.logger().debug("Skipping notify: updated by owner")
        return

    # Get previous doc before save
    previous = doc.get_doc_before_save()
    if not previous:
        frappe.logger().debug("Skipping notify: no previous doc")
        return

    # Track picked_qty changes
    changes = []
    prev_rows_by_name = {row.name: row for row in previous.get("locations", [])}

    for row in doc.get("locations", []):
        prev_row = prev_rows_by_name.get(row.name)
        if prev_row and (row.picked_qty or 0) != (prev_row.picked_qty or 0):
            changes.append(f"{row.item_code}: {prev_row.picked_qty or 0} → {row.picked_qty or 0}")

    if not changes:
        frappe.logger().debug("No picked_qty changes detected")
        return

    recipient = doc.owner or None
    if not recipient:
        frappe.logger().warning(f"Pick List {doc.name} has no owner to notify")
        return

    try:
        # 1. Create push notification (appears in bell icon)
        notification_doc = frappe.new_doc("Notification Log")
        notification_doc.subject = f"Pick List {doc.name} was updated"
        notification_doc.document_type = doc.doctype
        notification_doc.document_name = doc.name
        notification_doc.for_user = recipient

        changes_html = "<br>".join([f"• {change}" for change in changes])
        notification_doc.message = (
            f"Pick List <b>{doc.name}</b> was updated by {frappe.session.user}"
            f"<br><br><b>Changes:</b><br>{changes_html}"
        )

        notification_doc.insert(ignore_permissions=True)

        # 2. Send realtime toast alert to the owner
        payload = {
            "picklist": doc.name,
            "updated_by": frappe.session.user,
            "changes": changes,
            "message": f"Pick List {doc.name} updated with {len(changes)} item change(s)"
        }

        # Important: recipient must exactly match the target user's name (frappe User.name)
        frappe.publish_realtime(
            event="picklist_update_alert",
            message=payload,
            user=recipient,
            after_commit=True
        )

        # 3. Fallback: also send a msgprint realtime message (some clients may handle this naturally)
        frappe.publish_realtime(
            event="msgprint",
            message={"message": f"Pick List {doc.name} updated by {frappe.session.user}", "alert": False},
            user=recipient,
            after_commit=True
        )

        frappe.logger().info(f"Sent push + realtime to {recipient} for Pick List {doc.name}")

    except Exception as e:
        frappe.log_error(message=str(e), title="Pick List Notification Error")
        frappe.logger().error(f"Error sending pick list notification: {e}")