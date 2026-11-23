/* Cache only a public offline notice. Never cache API, pages, or user data. */
const CACHE = 'goldnam-public-offline-v1';
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(['/offline.html', '/offline.js'])));
  self.skipWaiting();
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => caches.match('/offline.html')));
  } else if (new URL(event.request.url).pathname === '/offline.js') {
    event.respondWith(fetch(event.request).catch(() => caches.match('/offline.js')));
  }
});
