/* Splitwise Mini — minimal PWA service worker.
 * Only caches GET /static/*. Never caches /api, auth pages, admin, or navigations.
 */
const CACHE_NAME = 'swmini-static-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  let url;
  try {
    url = new URL(req.url);
  } catch (e) {
    return;
  }

  // Same-origin only; never touch cross-origin
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/api/')) return;
  if (/^\/(login|register|logout|admin)(\/|$)/.test(url.pathname)) return;
  if (req.mode === 'navigate') return;
  if (req.destination === 'document') return;
  if (!url.pathname.startsWith('/static/')) return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(req);
      if (cached) return cached;
      try {
        const res = await fetch(req);
        if (res && res.ok) {
          cache.put(req, res.clone());
        }
        return res;
      } catch (err) {
        if (cached) return cached;
        throw err;
      }
    })
  );
});
