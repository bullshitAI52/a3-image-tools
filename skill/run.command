#!/bin/bash

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$DIR")"

# Navigate to project root
cd "$PROJECT_ROOT"

# Check for venv
if [ -d "venv" ]; then
    echo "Using venv..."
    source venv/bin/activate
else
    echo "⚠️  Virtual environment (venv) not found at $PROJECT_ROOT/venv"
    echo "Attempting to run with system python3..."
fi

# Run the python script
echo "Starting A3 to A4 Cutting Skill..."
python3 "$DIR/process_skill.py"

echo ""
echo "Press any key to close..."
read -n 1 -s
