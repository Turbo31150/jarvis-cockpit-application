// Coquille hors-ligne : l'interface reste ouvrable même sans le serveur.
const CACHE = "jarvis-cockpit-v1";
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(["/", "/manifest.json", "/icone.png"])));
  self.skipWaiting();
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(k =>
    Promise.all(k.filter(x => x !== CACHE).map(x => caches.delete(x)))));
  self.clients.claim();
});
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (u.pathname.startsWith("/api/")) return;          // jamais de cache sur l'API
  e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
