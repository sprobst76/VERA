// VERA Service Worker – Web Push + Offline Caching

const CACHE_VERSION = "vera-v2";
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE    = `${CACHE_VERSION}-api`;

// App-Shell: Seiten und Assets die immer gecacht werden
const PRECACHE_URLS = [
  "/",
  "/shifts",
  "/calendar",
  "/payroll",
  "/absences",
  "/icon-192.png",
  "/icon-512.png",
];

// API-Routen die bei fehlender Verbindung aus Cache serviert werden
const CACHE_API_PATTERNS = [
  /\/api\/v1\/shifts/,
  /\/api\/v1\/employees/,
  /\/api\/v1\/shift-templates/,
  /\/api\/v1\/payroll/,
];

// ── Install: App-Shell voraus-cachen ──────────────────────────────────────────

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache =>
      cache.addAll(PRECACHE_URLS).catch(() => {
        // Ignore errors during pre-caching (e.g. offline during install)
      })
    ).then(() => self.skipWaiting())
  );
});

// ── Activate: Alte Cache-Versionen löschen ────────────────────────────────────

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k.startsWith("vera-") && !k.startsWith(CACHE_VERSION))
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: Netzwerk-First mit Cache-Fallback ──────────────────────────────────

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Nur GET-Requests cachen
  if (request.method !== "GET") return;

  // API-Anfragen: Network-first, bei Fehler aus Cache
  if (CACHE_API_PATTERNS.some(p => p.test(url.pathname))) {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(API_CACHE).then(cache => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Navigation (HTML-Seiten): Network-first, dann Cache-Fallback auf /
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then(cache => cache.put(request, clone));
          }
          return response;
        })
        .catch(() =>
          caches.match(request).then(cached => cached || caches.match("/"))
        )
    );
    return;
  }

  // Statische Assets: Cache-first
  if (
    url.pathname.match(/\.(png|ico|svg|woff2?|css|js)$/) ||
    url.pathname.startsWith("/_next/static/")
  ) {
    event.respondWith(
      caches.match(request).then(cached => {
        if (cached) return cached;
        return fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then(cache => cache.put(request, clone));
          }
          return response;
        });
      })
    );
  }
});

// ── Push Notifications ────────────────────────────────────────────────────────

self.addEventListener("push", (event) => {
  const data = event.data?.json() ?? {};
  const title = data.title ?? "VERA";
  const options = {
    body: data.body ?? "",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    data: { url: data.url ?? "/" },
    vibrate: [200, 100, 200],
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url ?? "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      const existing = list.find((c) => "focus" in c);
      if (existing) return existing.focus();
      return clients.openWindow(url);
    })
  );
});
