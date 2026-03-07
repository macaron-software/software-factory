// Why: Workflow: TMA Auto-Heal → Phase: Diagnostic
// A2A MessageBus Dashboard - Application Logic

class MessageBusDashboard {
    constructor() {
        this.ws = null;
        this.subscriptions = new Map();
        this.metrics = {
            messagesSent: 0,
            messagesReceived: 0,
            errors: 0
        };
        this.messageHistory = [];
        this.maxMessages = 100;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.connect();
    }
    
    bindEvents() {
        // Subscribe button
        document.getElementById('subscribe-btn').addEventListener('click', () => {
            const channelInput = document.getElementById('channel-input');
            const channel = channelInput.value.trim();
            if (channel) {
                this.subscribe(channel);
                channelInput.value = '';
            }
        });
        
        // Enter key to subscribe
        document.getElementById('channel-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                document.getElementById('subscribe-btn').click();
            }
        });
        
        // Filter messages
        document.getElementById('message-filter').addEventListener('input', () => {
            this.renderMessages();
        });
        
        document.getElementById('message-type-filter').addEventListener('change', () => {
            this.renderMessages();
        });
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.updateConnectionStatus('connecting');
        this.log('info', `Connecting to MessageBus at ${wsUrl}...`);
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            this.updateConnectionStatus('connected');
            this.log('info', 'Connected to MessageBus');
            
            // Resubscribe to previous channels
            this.subscriptions.forEach((callbacks, channel) => {
                this.sendMessage('subscribe', { channel });
            });
        };
        
        this.ws.onmessage = (event) => {
            this.handleMessage(event.data);
        };
        
        this.ws.onclose = () => {
            this.updateConnectionStatus('disconnected');
            this.log('warn', 'Connection closed, reconnecting...');
            
            // Reconnect after 3 seconds
            setTimeout(() => this.connect(), 3000);
        };
        
        this.ws.onerror = (error) => {
            this.updateConnectionStatus('error');
            this.log('error', 'WebSocket error occurred');
            this.metrics.errors++;
            this.updateMetrics();
        };
    }
    
    sendMessage(type, payload) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({ type, payload, timestamp: Date.now() });
            this.ws.send(message);
            
            if (type !== 'subscribe' && type !== 'unsubscribe') {
                this.metrics.messagesSent++;
                this.updateMetrics();
            }
        }
    }
    
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            
            switch (message.type) {
                case 'message':
                    this.handleBusMessage(message.payload);
                    break;
                case 'subscribed':
                    this.log('info', `Subscribed to channel: ${message.payload.channel}`);
                    break;
                case 'unsubscribed':
                    this.log('info', `Unsubscribed from channel: ${message.payload.channel}`);
                    break;
                case 'error':
                    this.log('error', `Error: ${message.payload.message}`);
                    this.metrics.errors++;
                    this.updateMetrics();
                    break;
                default:
                    this.log('info', `Received: ${JSON.stringify(message)}`);
            }
        } catch (e) {
            this.log('error', `Failed to parse message: ${e.message}`);
        }
    }
    
    handleBusMessage(payload) {
        this.metrics.messagesReceived++;
        this.updateMetrics();
        
        const messageData = {
            type: payload.type || 'event',
            channel: payload.channel,
            content: payload.data,
            timestamp: Date.now()
        };
        
        this.messageHistory.unshift(messageData);
        if (this.messageHistory.length > this.maxMessages) {
            this.messageHistory.pop();
        }
        
        this.renderMessages();
        this.log('info', `[${payload.channel}] ${JSON.stringify(payload.data)}`);
    }
    
    subscribe(channel) {
        if (!this.subscriptions.has(channel)) {
            this.subscriptions.set(channel, {});
            this.sendMessage('subscribe', { channel });
            this.renderSubscriptions();
        }
    }
    
    unsubscribe(channel) {
        if (this.subscriptions.has(channel)) {
            this.subscriptions.delete(channel);
            this.sendMessage('unsubscribe', { channel });
            this.renderSubscriptions();
        }
    }
    
    updateConnectionStatus(status) {
        const statusDot = document.getElementById('connection-status');
        const statusText = document.getElementById('connection-text');
        
        statusDot.className = 'status-dot';
        
        switch (status) {
            case 'connected':
                statusDot.classList.add('connected');
                statusText.textContent = 'Connected';
                break;
            case 'connecting':
                statusText.textContent = 'Connecting...';
                break;
            case 'disconnected':
                statusText.textContent = 'Disconnected';
                break;
            case 'error':
                statusDot.classList.add('error');
                statusText.textContent = 'Error';
                break;
        }
    }
    
    updateMetrics() {
        document.getElementById('messages-sent').textContent = this.metrics.messagesSent;
        document.getElementById('messages-received').textContent = this.metrics.messagesReceived;
        document.getElementById('active-subscriptions').textContent = this.subscriptions.size;
        document.getElementById('error-count').textContent = this.metrics.errors;
    }
    
    renderMessages() {
        const container = document.getElementById('messages-list');
        const filter = document.getElementById('message-filter').value.toLowerCase();
        const typeFilter = document.getElementById('message-type-filter').value;
        
        let filtered = this.messageHistory;
        
        if (filter) {
            filtered = filtered.filter(m => 
                JSON.stringify(m.content).toLowerCase().includes(filter) ||
                m.channel.toLowerCase().includes(filter)
            );
        }
        
        if (typeFilter) {
            filtered = filtered.filter(m => m.type === typeFilter);
        }
        
        container.innerHTML = filtered.map(msg => `
            <div class="message-item">
                <span class="message-type ${msg.type}">${msg.type}</span>
                <span class="message-channel">${msg.channel}</span>
                <div class="message-content">${this.formatContent(msg.content)}</div>
            </div>
        `).join('');
    }
    
    formatContent(content) {
        if (typeof content === 'object') {
            return JSON.stringify(content, null, 2);
        }
        return content;
    }
    
    renderSubscriptions() {
        const container = document.getElementById('subscriptions-list');
        
        if (this.subscriptions.size === 0) {
            container.innerHTML = '<p style="color: #666; font-size: 0.9rem;">No active subscriptions</p>';
            return;
        }
        
        container.innerHTML = Array.from(this.subscriptions.keys()).map(channel => `
            <div class="subscription-item">
                <span class="channel-name">${channel}</span>
                <button class="unsubscribe-btn" onclick="dashboard.unsubscribe('${channel}')">×</button>
            </div>
        `).join('');
    }
    
    log(level, message) {
        const container = document.getElementById('logs-container');
        const timestamp = new Date().toLocaleTimeString();
        
        const entry = document.createElement('div');
        entry.className = `log-entry ${level}`;
        entry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${message}`;
        
        container.appendChild(entry);
        container.scrollTop = container.scrollHeight;
        
        // Keep only last 500 log entries
        while (container.children.length > 500) {
            container.removeChild(container.firstChild);
        }
    }
}

// Initialize dashboard when DOM is ready
let dashboard;
document.addEventListener('DOMContentLoaded', () => {
    dashboard = new MessageBusDashboard();
    
    // Subscribe to default channels for demo
    setTimeout(() => {
        dashboard.subscribe('system');
        dashboard.subscribe('tasks');
    }, 1000);
});

// Export for use in HTML
window.dashboard = dashboard;