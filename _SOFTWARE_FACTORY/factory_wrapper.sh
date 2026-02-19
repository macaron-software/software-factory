#!/bin/bash
# Wrapper for factory CLI that sets up PYTHONPATH automatically

# Add parent directory to PYTHONPATH
export PYTHONPATH="/Users/sylvain/_MACARON-SOFTWARE:$PYTHONPATH"

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run factory CLI with all arguments
python3 "$SCRIPT_DIR/cli/factory.py" "$@"
