/* Software Factory — Service Worker for Web Push Notifications */
const CACHE_VERSION = 'sf-v1';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('push', function(event) {
  if (!event.data) return;

  let data = {};
  try { data = event.data.json(); } catch(e) { data = { title: 'Software Factory', body: event.data.text() }; }

  const title = data.title || 'Software Factory';
  const options = {
    body: data.body || data.message || '',
    icon: data.icon || '/static/icon-192.png',
    badge: data.badge || '/static/icon-192.png',
    tag: data.tag || 'sf-notification',
    data: { url: data.url || '/' },
    actions: data.url ? [{ action: 'open', title: 'Voir' }] : [],
    requireInteraction: data.severity === 'critical',
    silent: data.severity === 'info',
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then(clients => {
      for (const client of clients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
