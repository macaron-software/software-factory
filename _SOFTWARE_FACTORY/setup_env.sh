#!/bin/bash
# Setup environment for Macaron Agent Platform
# Source this file before running factory commands

# Add parent directory to PYTHONPATH so we can import _FACTORY_CORE
export PYTHONPATH="/Users/sylvain/_MACARON-SOFTWARE:$PYTHONPATH"

echo "✅ Environment configured"
echo "PYTHONPATH: $PYTHONPATH"
