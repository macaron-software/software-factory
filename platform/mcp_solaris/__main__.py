"""Allow ``python3 -m platform.mcp_solaris`` or ``python3 -m mcp_solaris``."""
# Ref: feat-design-system
from .server import main
import asyncio

asyncio.run(main())
