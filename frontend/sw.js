// Service Worker - 处理离线缓存和网络请求
// 这是一个空的Service Worker文件，避免404错误

const CACHE_NAME = 'miapi-v2';
const urlsToCache = [
  '/',
  '/css/main.css',
  '/js/api.js',
  '/js/utils.js'
];

self.addEventListener('install', function(event) {
  // 缓存关键资源
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function(cache) {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('activate', function(event) {
  // 清理旧缓存
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

self.addEventListener('fetch', function(event) {
  // 网络优先策略
  event.respondWith(
    fetch(event.request)
      .catch(function() {
        return caches.match(event.request);
      })
  );
});
