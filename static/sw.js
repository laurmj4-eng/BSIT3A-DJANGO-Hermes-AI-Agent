const CACHE = 'hermes-static-v18';
const RUNTIME_CACHE = 'hermes-runtime-v1';

const CORE_URLS = [
  '/',
  '/news/',
  '/offline.html',
  '/static/css/tabler.css',
  '/static/css/tabler-themes.css',
  '/static/css/app-theme.css',
  '/static/css/app-ui.css',
  '/static/css/hermes-refresh.css',
  '/static/css/ai-overview.css',
  '/static/css/dashboard.css',
  '/static/css/cosmic-hero.css',
  '/static/js/theme-init.js',
  '/static/js/theme-settings.js',
  '/static/js/app-ui.js',
  '/static/js/scroll-reveal.js',
  '/static/js/cosmic-hero.js',
  '/static/manifest.webmanifest',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon-maskable-512.png',
  '/static/icons/models/platform-anthropic.svg',
  '/static/icons/models/platform-google.svg',
  '/static/icons/models/platform-openai.svg',
  '/static/icons/models/platform-meta.svg',
  '/static/icons/models/platform-mistral.svg',
  '/static/icons/models/platform-deepseek.svg',
  '/static/icons/models/platform-groq.svg',
  '/static/icons/models/model-claude.svg',
  '/static/icons/models/model-gemini.svg',
  '/static/icons/models/model-openai.svg',
  '/static/icons/models/model-meta.svg',
  '/static/icons/models/model-mistral.svg',
  '/static/icons/models/model-deepseek.svg',
  '/static/icons/models/model-groq.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => {
      return cache.addAll(CORE_URLS).catch((err) => {
        // Individual failures are OK for optional URLs
        console.log('Some core cache entries failed:', err);
        // Still try to cache what we can
        return cache;
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE && name !== RUNTIME_CACHE) {
            return caches.delete(name);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Passthrough for admin and API endpoints - network only
  if (url.pathname.startsWith('/admin/')
      || url.pathname.startsWith('/news/refresh/')
      || url.pathname.startsWith('/news/api/')
      || url.pathname.startsWith('/news/image-proxy/')
      || url.pathname.startsWith('/news/export/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Same-origin static assets: cache-first with background refresh.
  // One respondWith per event: nested respondWith() makes the fetch fail,
  // which is how an unstyled page happens once the SW controls the origin.
  if (url.origin === self.location.origin && url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        const network = fetch(event.request)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.ok) {
              const copy = networkResponse.clone();
              caches.open(CACHE).then((cache) => {
                cache.put(event.request, copy).catch(() => {
                  // Ignore quota errors
                });
              });
            }
            return networkResponse;
          })
          .catch(() => cached || new Response(null, { status: 504 }));
        return cached || network;
      })
    );
    return;
  }

  // Navigations & GET HTML: network-first, store in runtime cache, fallback chain
  if (event.request.mode === 'navigate' || (event.request.method === 'GET' &&
      url.pathname.endsWith('.html'))) {
    event.respondWith(
      fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.ok) {
          const copy = networkResponse.clone();
          caches.open(RUNTIME_CACHE).then((cache) => {
            cache.put(event.request, copy).catch(() => {
              // Ignore quota errors
            });
          });
        }
        return networkResponse;
      }).catch(() => {
        // Cache fallback -> cached navigation -> offline page -> inline HTML
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          return caches.match('/offline.html').then((offline) => {
            if (offline) return offline;
            // Inline offline HTML
            return new Response(
              '<!DOCTYPE html><html><head><title>Hermes AI News - Offline</title>' +
              '<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>' +
              '<link rel="stylesheet" href="/static/css/tabler.css"/>' +
              '<style>' +
              'body{font-family:sans-serif;max-width:600px;margin:2rem;padding:1rem;}' +
              '.retry{padding:1rem;background:#f8f9fa;border-radius:4px;margin-top:1rem;}' +
              '</style>' +
              '</head><body>' +
              '<h1>Hermes AI News</h1>' +
              '<p>You are offline. <button class="btn btn-accent retry" id="retryBtn">Retry</button></p>' +
              '<script>' +
              'document.getElementById("retryBtn").addEventListener("click", () => window.location.reload());' +
              '</script>' +
              '</body></html>',
              { headers: { 'Content-Type': 'text/html' } }
            );
          });
        });
      })
    );
    return;
  }

  // Other same-origin GET: network-first with cache fallback
  if (url.origin === self.location.origin) {
    event.respondWith(
      fetch(event.request).then((networkResponse) => {
        const copy = networkResponse.clone();
        caches.open(CACHE).then((cache) => {
          try {
            cache.put(event.request, copy);
          } catch (e) {
            // Ignore quota errors
          }
        });
        return networkResponse;
      }).catch(() => {
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          return new Response(null, { status: 404 });
        });
      })
    );
    return;
  }

  // Cross-origin: pass through
  event.respondWith(fetch(event.request));
});