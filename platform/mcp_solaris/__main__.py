"""Allow ``python3 -m platform.mcp_solaris`` or ``python3 -m mcp_solaris``."""
from .server import main
import asyncio

asyncio.run(main())
