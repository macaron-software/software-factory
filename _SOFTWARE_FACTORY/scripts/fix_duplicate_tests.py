#!/usr/bin/env python3
"""Fix duplicate test function names in Rust files."""
import re
import sys

def fix_duplicates(file_path: str):
    with open(file_path, 'r') as f:
        content = f.read()

    # Find all test function names
    pattern = r'fn (test_\w+)\(\)'
    matches = list(re.finditer(pattern, content))

    # Count occurrences
    seen = {}
    for m in matches:
        name = m.group(1)
        if name not in seen:
            seen[name] = []
        seen[name].append(m.start())

    # Find duplicates
    duplicates = {name: positions for name, positions in seen.items() if len(positions) > 1}

    if not duplicates:
        print("No duplicates found")
        return

    print(f"Found {len(duplicates)} duplicate test names:")
    for name, positions in duplicates.items():
        print(f"  {name}: {len(positions)} occurrences")

    # Rename duplicates (keep first, rename subsequent)
    # Process from end to start to preserve positions
    all_renames = []
    for name, positions in duplicates.items():
        for i, pos in enumerate(positions[1:], start=2):  # Skip first (i=1)
            all_renames.append((pos, name, i))

    # Sort by position descending
    all_renames.sort(key=lambda x: x[0], reverse=True)

    for pos, name, i in all_renames:
        old_name = f"fn {name}()"
        new_name = f"fn {name}_v{i}()"
        content = content[:pos] + content[pos:].replace(old_name, new_name, 1)

    with open(file_path, 'w') as f:
        f.write(content)

    print(f"Fixed {sum(len(p)-1 for p in duplicates.values())} duplicate names")

if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/sylvain/_LAPOSTE/_VELIGO2/veligo-platform/backend/src/modules/payment_module.rs"
    fix_duplicates(file_path)
