// Place this file in app_include_js (hooks) or load it so it runs in Desk.
// This file waits for socket initialization, handles string/object payloads,
// and shows toast reliably.

console.log("picklist_notifications: script loaded");

frappe.realtime.ready(function () {
    // `ready` wraps socket initialization when available (safer across versions)
    console.log("picklist_notifications: socket ready");

    // Utility to normalize message payloads (some transports send JSON strings)
    function normalizePayload(data) {
        if (!data) return null;
        if (typeof data === 'string') {
            try {
                return JSON.parse(data);
            } catch (e) {
                // Not JSON — return a wrapper
                return { message: data };
            }
        }
        return data;
    }

    // Primary listener for our custom event
    frappe.realtime.on("picklist_update_alert", function (raw) {
        console.log("picklist_update_alert received raw:", raw);
        var data = normalizePayload(raw);

        // If we don't have a picklist field, bail
        if (!data || !data.picklist) {
            console.warn("picklist_update_alert: no picklist field in payload", data);
            return;
        }

        var changesHTML = "";
        if (Array.isArray(data.changes)) {
            changesHTML = data.changes.map(function (c) {
                return '<div style="font-size:12px;margin:2px 0;">' + frappe.utils.escape_html(c) + '</div>';
            }).join('');
        }

        var message = '<div>' +
            '<strong>Pick List ' + frappe.utils.escape_html(data.picklist) + '</strong> updated by ' +
            frappe.utils.escape_html(data.updated_by || '') +
            (changesHTML ? ('<div style="margin-top:8px;"><strong>Changes:</strong>' + changesHTML + '</div>') : '') +
            '<div style="margin-top:8px;">' +
            '<a href="/app/pick-list/' + encodeURIComponent(data.picklist) + '" target="_blank" class="btn btn-xs btn-primary">Open Pick List</a>' +
            '</div>' +
            '</div>';

        frappe.show_alert({
            message: message,
            indicator: 'blue'
        }, 15);

        console.log("picklist_update_alert: shown toast for", data.picklist);
    });

    // Fallback listener for msgprint messages (some systems prefer this)
    frappe.realtime.on("msgprint", function (raw) {
        var payload = normalizePayload(raw);
        if (!payload) return;

        // payload may be {message: "..."} or a simple string
        var text = payload.message || payload;
        if (typeof text === 'object' && text.message) text = text.message;

        if (text && text.indexOf("Pick List") !== -1) {
            console.log("msgprint fallback showing alert:", text);
            frappe.show_alert({
                message: text,
                indicator: 'green'
            }, 10);
        }
    });



    // Listener for pick list assignment notifications
    frappe.realtime.on('pick_list_assigned', function (data) {
        // Show alert notification
        frappe.show_alert({
            message: data.message,
            indicator: 'blue',
            timeout: 10
        });

        // Optional: Play sound notification
        playNotificationSound();

        // Refresh if on Pick List list view
        if (cur_list && cur_list.doctype === 'Pick List') {
            cur_list.refresh();
        }

        // Optional: Show desktop notification
        if (frappe.get_route()[0] !== 'List' || frappe.get_route()[1] !== 'Pick List') {
            showDesktopNotification(data);
        }
    });

    function playNotificationSound() {
        // Play a subtle notification sound
        var audio = new Audio('/assets/erpnext/sounds/alert.mp3');
        audio.play().catch(e => console.log('Audio play failed:', e));
    }

    function showDesktopNotification(data) {
        if ("Notification" in window && Notification.permission === "granted") {
            new Notification(data.title, {
                body: data.message,
                icon: '/assets/erpnext/images/erpnext-logo.png'
            });
        }
    }

    // Request notification permission when needed
    function requestNotificationPermission() {
        if ("Notification" in window && Notification.permission === "default") {
            Notification.requestPermission();
        }
    }



});