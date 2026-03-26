from django.http import HttpResponse


def manifest(request):
    body = """{
  \"name\": \"2M Platform Mobile\",
  \"short_name\": \"2M Platform\",
  \"start_url\": \"/mobile/\",
  \"scope\": \"/\",
  \"display\": \"standalone\",
  \"background_color\": \"#0d0f14\",
  \"theme_color\": \"#0d0f14\",
  \"icons\": [
    {
      \"src\": \"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='192' height='192'><rect width='192' height='192' fill='%230d0f14'/><circle cx='96' cy='96' r='64' fill='%2322d3ee'/><text x='96' y='112' font-size='48' text-anchor='middle' fill='white' font-family='Arial'>2M</text></svg>\",
      \"sizes\": \"192x192\",
      \"type\": \"image/svg+xml\"
    },
    {
      \"src\": \"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='512' height='512'><rect width='512' height='512' fill='%230d0f14'/><circle cx='256' cy='256' r='180' fill='%2322d3ee'/><text x='256' y='290' font-size='120' text-anchor='middle' fill='white' font-family='Arial'>2M</text></svg>\",
      \"sizes\": \"512x512\",
      \"type\": \"image/svg+xml\"
    }
  ]
}
"""
    return HttpResponse(body, content_type="application/manifest+json")


def offline_page(request):
    body = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Offline</title>
    <style>
      body {
        margin: 0;
        font-family: system-ui, sans-serif;
        background: #0d0f14;
        color: #f8fafc;
        display: grid;
        place-items: center;
        min-height: 100vh;
        text-align: center;
      }
      .card {
        background: #171b24;
        border: 1px solid rgba(148,163,184,0.2);
        border-radius: 16px;
        padding: 24px;
        max-width: 320px;
      }
      .muted { color: #a3b1c6; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>You're offline</h2>
      <p class="muted">Reconnect to continue using 2M Platform.</p>
    </div>
  </body>
</html>
"""
    return HttpResponse(body, content_type="text/html")


def service_worker(request):
    body = """const CACHE_NAME = 'vwallet-pwa-v3';
const CORE_ASSETS = ['/mobile/', '/manifest.webmanifest', '/offline/'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const req = event.request;
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => caches.match('/offline/'))
    );
    return;
  }
  event.respondWith(
    caches.match(req).then((cached) => cached || fetch(req))
  );
});
"""
    return HttpResponse(body, content_type="application/javascript")
