# PWA & Offline-First Architecture

## Purpose
Build web applications that work reliably regardless of network conditions. Users should be able to continue working offline, with seamless sync when connectivity returns.

## Service Worker Lifecycle

```typescript
// sw.ts — Service Worker registration
if ('serviceWorker' in navigator) {
  const registration = await navigator.serviceWorker.register('/sw.js', {
    scope: '/',
    updateViaCache: 'none',
  });

  // Prompt user on update
  registration.addEventListener('updatefound', () => {
    const newWorker = registration.installing!;
    newWorker.addEventListener('statechange', () => {
      if (newWorker.state === 'activated' && navigator.serviceWorker.controller) {
        showBanner('Mise à jour disponible', {
          action: { label: 'Recharger', onClick: () => location.reload() }
        });
      }
    });
  });
}
```

## Caching Strategies

### Cache-First (Static Assets)
```typescript
// For: fonts, icons, images, CSS, JS bundles
self.addEventListener('fetch', (event: FetchEvent) => {
  if (isStaticAsset(event.request)) {
    event.respondWith(
      caches.match(event.request).then(cached =>
        cached || fetch(event.request).then(response => {
          const clone = response.clone();
          caches.open('static-v1').then(cache => cache.put(event.request, clone));
          return response;
        })
      )
    );
  }
});
```

### Stale-While-Revalidate (API Data)
```typescript
// For: GET /api/* — show cached data immediately, update in background
self.addEventListener('fetch', (event: FetchEvent) => {
  if (isApiGet(event.request)) {
    event.respondWith(
      caches.open('api-cache').then(async cache => {
        const cached = await cache.match(event.request);
        const fetchPromise = fetch(event.request).then(response => {
          if (response.ok) cache.put(event.request, response.clone());
          return response;
        }).catch(() => cached); // offline fallback to cache

        return cached || fetchPromise;
      })
    );
  }
});
```

### Network-First (Critical Data)
```typescript
// For: user profile, auth state, real-time data
async function networkFirst(request: Request): Promise<Response> {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open('critical-cache');
      await cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ offline: true }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
```

## Background Sync

```typescript
// Queue mutations when offline
async function submitForm(data: FormData) {
  if (navigator.onLine) {
    return await fetch('/api/submit', { method: 'POST', body: data });
  }

  // Store in IndexedDB and register sync
  await saveToOfflineQueue({ url: '/api/submit', method: 'POST', body: data });

  if ('serviceWorker' in navigator && 'SyncManager' in window) {
    const reg = await navigator.serviceWorker.ready;
    await reg.sync.register('sync-queue');
  }
}

// In service worker
self.addEventListener('sync', (event: SyncEvent) => {
  if (event.tag === 'sync-queue') {
    event.waitUntil(flushOfflineQueue());
  }
});
```

## IndexedDB for Offline Storage

```typescript
import { openDB, DBSchema } from 'idb';

interface AppDB extends DBSchema {
  'offline-queue': { key: string; value: QueuedRequest };
  'cached-data': { key: string; value: { data: any; timestamp: number } };
}

const db = await openDB<AppDB>('app-store', 1, {
  upgrade(db) {
    db.createObjectStore('offline-queue', { keyPath: 'id' });
    db.createObjectStore('cached-data', { keyPath: 'key' });
  },
});

// Stale data detection
async function getCachedOrFetch<T>(key: string, fetcher: () => Promise<T>, maxAge = 300_000): Promise<T> {
  const cached = await db.get('cached-data', key);
  if (cached && Date.now() - cached.timestamp < maxAge) {
    return cached.data as T;
  }
  try {
    const fresh = await fetcher();
    await db.put('cached-data', { key, data: fresh, timestamp: Date.now() });
    return fresh;
  } catch {
    if (cached) return cached.data as T; // stale fallback
    throw new Error('Données indisponibles hors ligne');
  }
}
```

## Web App Manifest

```json
{
  "name": "TechLearn",
  "short_name": "TechLearn",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0f0a1a",
  "theme_color": "#a855f7",
  "icons": [
    { "src": "/icons/192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

## Sync State Management

```typescript
type SyncState = 'synced' | 'syncing' | 'pending' | 'conflict' | 'error';

interface SyncStatus {
  state: SyncState;
  pendingCount: number;
  lastSynced: Date | null;
  error?: string;
}

// UI indicator
function SyncIndicator({ status }: { status: SyncStatus }) {
  const labels: Record<SyncState, string> = {
    synced: 'Tout est à jour',
    syncing: 'Synchronisation...',
    pending: `${status.pendingCount} modification(s) en attente`,
    conflict: 'Conflit de synchronisation',
    error: 'Erreur de synchronisation',
  };
  return (
    <span role="status" aria-live="polite" className={`sync sync--${status.state}`}>
      <Icon name={iconMap[status.state]} aria-hidden="true" />
      {labels[status.state]}
    </span>
  );
}
```

## Conflict Resolution

```typescript
type ConflictStrategy = 'last-write-wins' | 'server-wins' | 'client-wins' | 'manual';

async function resolveConflict<T>(
  local: T & { updatedAt: number },
  remote: T & { updatedAt: number },
  strategy: ConflictStrategy = 'last-write-wins'
): Promise<T> {
  switch (strategy) {
    case 'last-write-wins':
      return local.updatedAt > remote.updatedAt ? local : remote;
    case 'server-wins':
      return remote;
    case 'client-wins':
      return local;
    case 'manual':
      return await promptUserForResolution(local, remote);
  }
}
```

## Rules
- ALWAYS register service worker on first load (not lazy)
- ALWAYS version caches (static-v1, static-v2) for cache busting
- ALWAYS show sync state to users (subtle indicator, not modal)
- ALWAYS handle IndexedDB quota exceeded (clean old data)
- NEVER cache POST/PUT/DELETE responses
- NEVER cache auth tokens in service worker cache (use memory/Keychain)
- Offline queue: max 100 items, FIFO, discard after 24h
- Background Sync: exponential backoff, max 5 retries
- Cache TTL: static assets = 7 days, API data = 5 minutes, critical = 1 minute
- Test with Chrome DevTools "Offline" toggle + Lighthouse PWA audit
