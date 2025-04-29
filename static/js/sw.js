self.addEventListener('install', function(event) {
    console.log('[SW] Installed');
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    console.log('[SW] Activated');
    self.clients.claim();
});

self.addEventListener('message', function(event) {
    console.log('[SW] Message received:', event.data);

    if (event.data && event.data.type === 'SHOW_NOTIFICATION') {
        const title = event.data.title || 'Notification';
        const options = event.data.options || {};

        try {
            self.registration.showNotification(title, options);
            console.log('[SW] showNotification() called with:', title, options);
        } catch (err) {
            console.error('[SW] Error showing notification:', err);
        }
    }
});


self.addEventListener('notificationclick', function(event) {
    const url = event.notification.data?.url;
    event.notification.close();

    if (url) {
        event.waitUntil(
            clients.matchAll({ type: 'window' }).then(windowClients => {
                for (let client of windowClients) {
                    if (client.url.includes(url) && 'focus' in client) {
                        return client.focus();
                    }
                }
                if (clients.openWindow) {
                    return clients.openWindow(url);
                }
            })
        );
    }
});
