// Service worker for queue alerts.
//
// It carries no push subscription and no cache: the only reason it exists is
// that Chrome refuses `new Notification(...)` from a page and requires
// notifications to be shown through a registration. It is served from the site
// root so its scope covers the whole site.

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

// Tapping the alert should bring the queue page back, not open a second copy.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/dashboard/me/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes("/dashboard/me/") && "focus" in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    })
  );
});
