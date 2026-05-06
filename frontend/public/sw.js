// Cache-first service worker for Clash Royale card icons.
// CDN URLs are content-hashed, so they only change when Supercell publishes
// new art — safe to cache forever. Bump CACHE_NAME to force re-fetching.

const CACHE_NAME = "cr-card-icons-v1";
const CDN_HOST = "api-assets.clashroyale.com";

self.addEventListener("install", () => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((k) => k.startsWith("cr-card-icons-") && k !== CACHE_NAME)
                    .map((k) => caches.delete(k))
            )
        )
    );
    event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "GET") return;

    const url = new URL(req.url);
    if (url.hostname !== CDN_HOST) return;

    event.respondWith(
        caches.open(CACHE_NAME).then(async (cache) => {
            const cached = await cache.match(req);
            if (cached) return cached;
            const response = await fetch(req);
            if (response.ok) {
                cache.put(req, response.clone());
            }
            return response;
        })
    );
});
