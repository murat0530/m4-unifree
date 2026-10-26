// Çevrimdışı ve anında açılış: önce önbellekten ver, arka planda güncelle.
// Uygulama dosyaları değiştiğinde VERSION'ı artırın.
const VERSION = 'm4kasa-v2';
const SHELL = [
  './',
  'index.html',
  'app.css',
  'app.js',
  'calc.js',
  'barcode.js',
  'manifest.webmanifest',
  'data/kurallar.json',
  'data/kampanyalar.json',
  'data/ifadeler.json',
  'data/barkodlar.json',
  'icons/icon-192.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  // Sayfa açılışları için her zaman ana sayfayı kullan (#doviz gibi adresler dahil)
  const key = req.mode === 'navigate' ? 'index.html' : req;
  e.respondWith(caches.open(VERSION).then(async (cache) => {
    const cached = await cache.match(key, { ignoreSearch: true });
    const fresh = fetch(req).then((res) => {
      if (res.ok) cache.put(key, res.clone());
      return res;
    }).catch(() => cached);
    if (cached) {
      e.waitUntil(fresh);
      return cached;
    }
    return fresh;
  }));
});
