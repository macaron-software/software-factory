/**
 * SSE client utilities for Macaron Agent Platform.
 * Handles reconnection with exponential backoff + Last-Event-ID tracking.
 */
class MacaronSSE {
  constructor(url, options = {}) {
    this.baseUrl = url;
    this.onMessage = options.onMessage || (() => {});
    this.onError = options.onError || (() => {});
    this.onReconnect = options.onReconnect || (() => {});
    this.onConnect = options.onConnect || (() => {});
    this.baseDelay = options.reconnectDelay || 2000;
    this.maxDelay = options.maxDelay || 30000;
    this.retries = 0;
    this.lastEventId = null;
    this.source = null;
    this._reconnectTimer = null;
    this._closed = false;
  }

  get url() {
    // Append Last-Event-ID as query param for nginx proxy compatibility
    if (this.lastEventId) {
      const sep = this.baseUrl.includes('?') ? '&' : '?';
      return `${this.baseUrl}${sep}_lastId=${encodeURIComponent(this.lastEventId)}`;
    }
    return this.baseUrl;
  }

  connect() {
    if (this._closed) return;
    this.source = new EventSource(this.url);

    this.source.onopen = () => {
      this.retries = 0;
      this._reconnectTimer = null;
      console.log(`[SSE] Connected: ${this.baseUrl}`);
      this.onConnect();
    };

    this.source.onmessage = (event) => {
      if (event.lastEventId) this.lastEventId = event.lastEventId;
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data, event);
      } catch {
        this.onMessage(event.data, event);
      }
    };

    this.source.onerror = () => {
      this.source.close();
      this.source = null;
      if (this._closed) return;
      // Exponential backoff with jitter (never give up)
      this.retries++;
      const exp = Math.min(this.retries, 8);
      const jitter = Math.random() * 1000;
      const delay = Math.min(this.baseDelay * Math.pow(1.5, exp - 1) + jitter, this.maxDelay);
      console.log(`[SSE] Reconnecting in ${Math.round(delay)}ms (attempt ${this.retries})`);
      this.onReconnect(this.retries, delay);
      this._reconnectTimer = setTimeout(() => this.connect(), delay);
    };
  }

  disconnect() {
    this._closed = true;
    if (this._reconnectTimer) clearTimeout(this._reconnectTimer);
    if (this.source) {
      this.source.close();
      this.source = null;
    }
  }

  // Allow re-use after explicit disconnect
  reset() {
    this._closed = false;
    this.retries = 0;
    this.lastEventId = null;
  }
}

window.MacaronSSE = MacaronSSE;
