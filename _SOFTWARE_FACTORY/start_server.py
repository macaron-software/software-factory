"""Server launcher that ignores SIGTERM/SIGHUP from shell cleanup."""
import signal, os, sys, logging

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("macaron-server")

# Ignore SIGHUP (shell disconnect) and SIGTERM (external kills)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
signal.signal(signal.SIGTERM, signal.SIG_IGN)

log.warning(f"Server PID {os.getpid()} — SIGTERM/SIGHUP IGNORED")

import uvicorn

class NoSignalServer(uvicorn.Server):
    """Override uvicorn's signal handling to ignore SIGTERM."""
    def install_signal_handlers(self):
        # Don't install signal handlers — we handle signals ourselves
        pass

config = uvicorn.Config(
    "platform.server:app",
    host="0.0.0.0",
    port=8099,
    timeout_keep_alive=300,
)
server = NoSignalServer(config)
server.run()
