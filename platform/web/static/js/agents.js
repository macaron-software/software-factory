/**
 * Agent interaction logic for Macaron Agent Platform.
 * Handles agent card updates and status rendering.
 */
document.addEventListener('DOMContentLoaded', () => {
    // Update monitoring metrics from SSE
    document.body.addEventListener('sse:message', (event) => {
        try {
            const data = typeof event.detail === 'string' ? JSON.parse(event.detail) : event.detail;
            if (data.type === 'metrics') {
                const el = (id) => document.getElementById(id);
                if (el('metric-agents')) el('metric-agents').textContent = data.agents_active || 0;
                if (el('metric-messages')) el('metric-messages').textContent = data.messages_total || 0;
                if (el('metric-sessions')) el('metric-sessions').textContent = data.sessions_active || 0;
            }
        } catch { /* ignore parse errors */ }
    });
});
