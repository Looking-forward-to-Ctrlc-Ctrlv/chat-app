const userId = JSON.parse(document.getElementById('json-current-user-id').textContent);
const notificationSocket = new WebSocket(
    'ws://' + window.location.host + '/ws/notification/' + userId + '/'
);

let unseenNotifications = [];
let unseenCount = 0;


document.addEventListener('DOMContentLoaded', function() {
    const notificationBell = document.querySelector('.notification');
    const countBadge = document.getElementById('count_badge');

    let notificationDropdown = document.getElementById('notification-dropdown');
    if (!notificationDropdown) {
        notificationDropdown = document.createElement('div');
        notificationDropdown.id = 'notification-dropdown';
        notificationDropdown.className = 'notification-dropdown';
        notificationDropdown.style.display = 'none';
        notificationDropdown.style.position = 'absolute';
        notificationDropdown.style.backgroundColor = 'white';
        notificationDropdown.style.border = '1px solid #ddd';
        notificationDropdown.style.borderRadius = '5px';
        notificationDropdown.style.padding = '10px';
        notificationDropdown.style.width = '300px';
        notificationDropdown.style.maxHeight = '400px';
        notificationDropdown.style.overflowY = 'auto';
        notificationDropdown.style.zIndex = '1000';
        notificationDropdown.style.boxShadow = '0 2px 5px rgba(0,0,0,0.2)';
        notificationDropdown.style.top = '30px';
        notificationDropdown.style.right = '0';

        notificationBell.parentNode.style.position = 'relative';
        notificationBell.parentNode.appendChild(notificationDropdown);
    }

    notificationBell.addEventListener('click', function(event) {
        event.stopPropagation();
        notificationDropdown.style.display =
            notificationDropdown.style.display === 'none' ? 'block' : 'none';
    });

    document.addEventListener('click', function(event) {
        if (!notificationBell.contains(event.target) && !notificationDropdown.contains(event.target)) {
            notificationDropdown.style.display = 'none';
        }
    });
});

notificationSocket.onopen = function(e) {
    console.log("🔗 Notification socket connected");
};

notificationSocket.onclose = function(e) {
    console.log("🔌 Notification socket disconnected");
};

notificationSocket.onmessage = function(e) {
    const data = JSON.parse(e.data);

    if (data.notification) {
        showBrowserNotification(data.notification);
    }

    if (data.hasOwnProperty('unseen_notifications')) {
        unseenNotifications = data.unseen_notifications;
        unseenCount = data.unseen_count;

        updateNotificationBadge();
        updateNotificationDropdown();
    }
};

function updateNotificationBadge() {
    const countBadge = document.getElementById('count_badge');
    if (unseenCount > 0) {
        countBadge.textContent = unseenCount;
        countBadge.style.display = 'inline';
    } else {
        countBadge.style.display = 'none';
    }
}

function updateNotificationDropdown() {
    const dropdown = document.getElementById('notification-dropdown');
    dropdown.innerHTML = '';

    if (unseenNotifications.length === 0) {
        dropdown.innerHTML = '<p style="text-align: center; color: #888;">No new notifications</p>';
        return;
    }

    unseenNotifications.forEach(notification => {
        const notificationItem = document.createElement('div');
        notificationItem.className = 'notification-item';
        notificationItem.style.padding = '8px 0';
        notificationItem.style.borderBottom = '1px solid #eee';
        notificationItem.style.cursor = 'pointer';

        let messagePreview = notification.message_preview
            ? `<p style="margin: 0; color: #666; font-size: 12px;">${notification.message_preview}</p>`
            : '';

        notificationItem.innerHTML = `
            <p style="margin: 0; font-weight: bold;">
                <strong>${notification.sender_username}</strong> messaged you
            </p>
            <p style="margin: 0; font-size: 12px; color: #888;">
                ${formatTimestamp(notification.timestamp)}
            </p>
            ${messagePreview}
        `;

        notificationItem.addEventListener('click', function() {
            window.location.href = `/chat/${notification.sender_username}/`;
        });

        dropdown.appendChild(notificationItem);
    });

    const markAllReadBtn = document.createElement('button');
    markAllReadBtn.textContent = 'Mark all as Read';
    markAllReadBtn.className = 'mark-all-read-btn';
    markAllReadBtn.style.cssText = `
        margin-top: 10px; width: 100%; padding: 8px;
        background-color: #007bff; color: white;
        border: none; border-radius: 5px; cursor: pointer;
        font-weight: bold;
    `;

    markAllReadBtn.addEventListener('click', function(event) {
        event.stopPropagation();
        markNotificationsAsSeen();
    });

    dropdown.appendChild(markAllReadBtn);
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'just now';
    const date = new Date(timestamp);
    const now = new Date();

    if (date.toDateString() === now.toDateString()) {
        return `Today at ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    }

    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (date.toDateString() === yesterday.toDateString()) {
        return `Yesterday at ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    }

    return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
}

function markNotificationsAsSeen() {
    if (unseenCount > 0) {
        fetch('/mark-notifications-seen/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                unseenCount = 0;
                unseenNotifications = [];
                updateNotificationBadge();
                updateNotificationDropdown();
            }
        })
        .catch(error => {
            console.error('Error marking notifications as seen:', error);
        });
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function showBrowserNotification(notification) {
console.log("showBrowserReached")
    if (!("Notification" in window)) {
        console.warn("This browser does not support notifications");
        return;
    }

    if (!notification || !notification.sender_username) {
        console.error("Invalid notification data:", notification);
        return;
    }

    if (Notification.permission === "granted") {

        forwardToServiceWorker(notification);
    } else if (Notification.permission !== "denied") {
        Notification.requestPermission().then(permission => {
            if (permission === "granted") {
                forwardToServiceWorker(notification);
            }
        });
    }
}


function forwardToServiceWorker(notification) {

    const title = `${notification.sender_username} sent you a message`;
    const options = {
        body: notification.message_preview || "You have a new message",
        icon: "/static/assets/icon.png",
        data: {
            url: `/chat/${notification.sender_username}/`
        }
    };

    if (navigator.serviceWorker.controller) {
    console.log("1st iffff")
        navigator.serviceWorker.controller.postMessage({
            type: 'SHOW_NOTIFICATION',
            title: title,
            options: options
        });
    } else {
    console.log("elseeeee")
        // Retry after ensuring the SW is ready
        navigator.serviceWorker.ready.then(registration => {
            if (registration.active) {
                registration.active.postMessage({
                    type: 'SHOW_NOTIFICATION',
                    title: title,
                    options: options
                });
            } else {
                console.warn("No active service worker to show notification.");
            }
        });
    }
}




// ✅ Register the service worker for global notifications
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register("/service_worker/sw.js", {  // Updated path to the correct URL
            scope: "/" // Now the scope should be valid
        })
        .then(function(registration) {
            console.log("✅ Service Worker registered with scope:", registration.scope);
        })
        .catch(function(error) {
            console.error("❌ Service Worker registration failed:", error);
        });
    });
}


