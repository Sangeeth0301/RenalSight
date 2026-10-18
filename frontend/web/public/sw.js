/* RenalSight service worker: the app opens offline and shows the last saved information.
   - static files: cache first
   - page navigations: network first, falling back to the cached app shell
   - a few read-only API calls: network first, falling back to the last saved response
   The API cache is deleted when the user logs out (see session store). */
const SHELL = "rs-shell-v1";
const API = "rs-api-v1";
const API_PATHS = ["/clinical/me/kidney-state", "/labs", "/me", "/offline/emergency-card", "/research/search", "/rituals/today", "/population/estimate", "/population/regions", "/care-hub/providers", "/channels"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/", "/favicon.svg", "/manifest.webmanifest"])).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL && k !== API).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  if (req.mode === "navigate") {
    e.respondWith(fetch(req).then((r) => { const copy = r.clone(); caches.open(SHELL).then((c) => c.put("/", copy)); return r; }).catch(() => caches.match("/")));
    return;
  }
  if (url.origin === self.location.origin) {
    if (url.pathname.startsWith("/assets/") || url.pathname.endsWith(".svg") || url.pathname.endsWith(".webmanifest")) {
      e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((r) => { const copy = r.clone(); caches.open(SHELL).then((c) => c.put(req, copy)); return r; })));
    }
    return;
  }
  if (API_PATHS.some((p) => url.pathname === p || url.pathname.startsWith(p + "/")) && url.port === "8000") {
    e.respondWith(fetch(req).then((r) => { if (r.ok) { const copy = r.clone(); caches.open(API).then((c) => c.put(req.url, copy)); } return r; })
      .catch(() => caches.open(API).then((c) => c.match(req.url)).then((hit) => hit || new Response(JSON.stringify({ detail: "offline" }), { status: 503, headers: { "Content-Type": "application/json" } }))));
  }
});
