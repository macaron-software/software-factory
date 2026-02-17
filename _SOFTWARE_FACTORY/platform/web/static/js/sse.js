/**
 * SSE client utilities for Macaron Agent Platform.
 * Handles reconnection and message parsing for real-time updates.
 */
class MacaronSSE {
    constructor(url, options = {}) {
        this.url = url;
        this.onMessage = options.onMessage || (() => {});
        this.onError = options.onError || (() => {});
        this.reconnectDelay = options.reconnectDelay || 3000;
        this.maxRetries = options.maxRetries || 10;
        this.retries = 0;
        this.source = null;
    }

    connect() {
        this.source = new EventSource(this.url);

        this.source.onopen = () => {
            this.retries = 0;
            console.log(`[SSE] Connected: ${this.url}`);
        };

        this.source.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.onMessage(data);
            } catch {
                this.onMessage(event.data);
            }
        };

        this.source.onerror = () => {
            this.source.close();
            if (this.retries < this.maxRetries) {
                this.retries++;
                const delay = this.reconnectDelay * Math.min(this.retries, 5);
                console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${this.retries})`);
                setTimeout(() => this.connect(), delay);
            } else {
                this.onError('Max retries reached');
            }
        };
    }

    disconnect() {
        if (this.source) {
            this.source.close();
            this.source = null;
        }
    }
}

// Global SSE connections
window.MacaronSSE = MacaronSSE;
