/* Minimal service worker for PWA installability. It deliberately does not cache API responses or authenticated documents. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
