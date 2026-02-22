/**
 * Workspace management for Macaron Agent Platform.
 * Handles panel resizing, keyboard shortcuts, and session management.
 */
document.addEventListener('DOMContentLoaded', () => {
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl+N: New session
        if (e.ctrlKey && e.key === 'n') {
            e.preventDefault();
            window.location.href = '/sessions/new';
        }
        // Ctrl+M: Monitoring
        if (e.ctrlKey && e.key === 'm') {
            e.preventDefault();
            window.location.href = '/monitoring';
        }
    });

    // Auto-scroll message timeline
    const timeline = document.getElementById('message-timeline');
    if (timeline) {
        const observer = new MutationObserver(() => {
            timeline.scrollTop = timeline.scrollHeight;
        });
        observer.observe(timeline, { childList: true, subtree: true });
    }
});
