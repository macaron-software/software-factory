# Network Resilience

## Purpose
Build apps that gracefully handle network instability: disconnection, slow connections, timeouts, and server errors. Users should never see a blank screen or cryptic error.

## Connectivity Detection

### Web
```typescript
// Navigator API + event listeners
const isOnline = () => navigator.onLine;
window.addEventListener('online', () => showBanner('Connexion rétablie', 'success'));
window.addEventListener('offline', () => showBanner('Vous êtes hors ligne', 'warning'));

// Heartbeat probe (more reliable than navigator.onLine)
async function checkConnectivity(): Promise<boolean> {
  try {
    const r = await fetch('/api/health', { method: 'HEAD', cache: 'no-store' });
    return r.ok;
  } catch { return false; }
}
```

### iOS (Swift)
```swift
import Network
let monitor = NWPathMonitor()
monitor.pathUpdateHandler = { path in
  DispatchQueue.main.async {
    if path.status == .satisfied {
      NotificationCenter.default.post(name: .connectivityRestored, object: nil)
    } else {
      NotificationCenter.default.post(name: .connectivityLost, object: nil)
    }
  }
}
monitor.start(queue: DispatchQueue(label: "NetworkMonitor"))
```

### Android (Kotlin)
```kotlin
val connectivityManager = getSystemService(ConnectivityManager::class.java)
val networkCallback = object : ConnectivityManager.NetworkCallback() {
  override fun onAvailable(network: Network) = showBanner("Connexion rétablie", BannerType.SUCCESS)
  override fun onLost(network: Network) = showBanner("Vous êtes hors ligne", BannerType.WARNING)
}
connectivityManager.registerDefaultNetworkCallback(networkCallback)
```

## Retry with Exponential Backoff

```typescript
async function fetchWithRetry<T>(
  url: string,
  options: RequestInit = {},
  config = { maxRetries: 3, baseDelay: 1000, maxDelay: 30000 }
): Promise<T> {
  let lastError: Error;
  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    try {
      const response = await fetch(url, {
        ...options,
        signal: AbortSignal.timeout(10_000),
      });
      if (response.status === 429) {
        const retryAfter = parseInt(response.headers.get('Retry-After') || '5');
        await sleep(retryAfter * 1000);
        continue;
      }
      if (!response.ok) throw new HttpError(response.status, await response.text());
      return await response.json();
    } catch (error) {
      lastError = error as Error;
      if (attempt < config.maxRetries) {
        const jitter = Math.random() * 500;
        const delay = Math.min(config.baseDelay * 2 ** attempt + jitter, config.maxDelay);
        await sleep(delay);
      }
    }
  }
  throw lastError!;
}
```

## Circuit Breaker

```typescript
class CircuitBreaker {
  private failures = 0;
  private lastFailure = 0;
  private state: 'closed' | 'open' | 'half-open' = 'closed';

  constructor(
    private threshold = 5,
    private resetTimeout = 30_000
  ) {}

  async call<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailure > this.resetTimeout) {
        this.state = 'half-open';
      } else {
        throw new CircuitOpenError('Service temporairement indisponible');
      }
    }
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess() { this.failures = 0; this.state = 'closed'; }
  private onFailure() {
    this.failures++;
    this.lastFailure = Date.now();
    if (this.failures >= this.threshold) this.state = 'open';
  }
}
```

## SSE Reconnection

```typescript
function createResilientSSE(url: string, onMessage: (data: any) => void) {
  let retryDelay = 1000;
  let lastEventId = '';

  function connect() {
    const headers: Record<string, string> = {};
    if (lastEventId) headers['Last-Event-ID'] = lastEventId;

    const eventSource = new EventSource(`${url}?lastId=${lastEventId}`);

    eventSource.onopen = () => { retryDelay = 1000; };

    eventSource.onmessage = (event) => {
      lastEventId = event.lastEventId;
      onMessage(JSON.parse(event.data));
    };

    eventSource.onerror = () => {
      eventSource.close();
      const jitter = Math.random() * 1000;
      setTimeout(connect, Math.min(retryDelay + jitter, 30_000));
      retryDelay *= 2;
    };

    return eventSource;
  }
  return connect();
}
```

## Offline Queue (Request Buffering)

```typescript
class OfflineQueue {
  private queue: QueuedRequest[] = [];
  private readonly storageKey = 'offline_queue';

  constructor() {
    this.queue = JSON.parse(localStorage.getItem(this.storageKey) || '[]');
    window.addEventListener('online', () => this.flush());
  }

  enqueue(request: QueuedRequest) {
    this.queue.push({ ...request, timestamp: Date.now() });
    localStorage.setItem(this.storageKey, JSON.stringify(this.queue));
  }

  async flush() {
    const pending = [...this.queue];
    this.queue = [];
    localStorage.removeItem(this.storageKey);

    for (const req of pending) {
      try {
        await fetchWithRetry(req.url, req.options);
      } catch {
        this.enqueue(req); // re-queue on failure
        break;
      }
    }
  }
}
```

## Rules
- NEVER show raw HTTP error codes to users
- ALWAYS provide a retry action (button or auto-retry)
- ALWAYS persist user input before network calls (prevent data loss)
- ALWAYS use exponential backoff with jitter (never fixed delay)
- ALWAYS show connectivity state changes (banner, not alert)
- NEVER block the UI during retry (use background retry + loading indicator)
- Timeout: 10s for API calls, 30s for file uploads, 5s for health checks
- Max retries: 3 for idempotent (GET), 1 for mutations (POST/PUT/DELETE)
- Cache GET responses for offline fallback (stale-while-revalidate)
