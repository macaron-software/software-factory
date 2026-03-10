# Workaround: this package shadows stdlib 'platform'. Re-export critical attrs
# so that libraries like httpx/zstandard that call platform.python_implementation() work.
import importlib.util as _ilu
import os as _os
import sys as _sys
import sysconfig as _sc

# Find the stdlib platform.py directly
_stdlib_path = _os.path.join(_sc.get_path("stdlib"), "platform.py")
_spec = _ilu.spec_from_file_location("_stdlib_platform", _stdlib_path)
_stdlib_platform = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_stdlib_platform)

python_implementation = _stdlib_platform.python_implementation
system = _stdlib_platform.system
machine = _stdlib_platform.machine
python_version = _stdlib_platform.python_version
release = _stdlib_platform.release
version = _stdlib_platform.version
uname = _stdlib_platform.uname  # Needed by watchfiles

del _ilu, _os, _sc, _spec, _stdlib_path, _stdlib_platform
