#!/usr/bin/env python3
"""
Script to fix MUI v7 Grid API breaking changes by removing 'item' prop from Grid components.
In MUI v7, the Grid component no longer accepts the 'item' prop.
"""

import re
import os
from pathlib import Path

def fix_grid_in_file(filepath):
    """Fix Grid item prop usage in a single file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match <Grid item ...> with various props
    # This captures the opening Grid tag with 'item' prop
    pattern = r'<Grid\s+item\s+([^>]*)>'
    
    def replace_grid(match):
        # Keep all other props except 'item'
        other_props = match.group(1).strip()
        if other_props:
            return f'<Grid {other_props}>'
        else:
            return '<Grid>'
    
    # Replace all occurrences
    content = re.sub(pattern, replace_grid, content)
    
    # Only write if changes were made
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    # Find all .tsx and .ts files in frontend/src
    src_dir = Path('/Users/neekrish/zeroqwait/frontend/src')
    
    files_modified = []
    
    for filepath in src_dir.rglob('*.tsx'):
        if fix_grid_in_file(filepath):
            files_modified.append(str(filepath))
    
    for filepath in src_dir.rglob('*.ts'):
        if fix_grid_in_file(filepath):
            files_modified.append(str(filepath))
    
    print(f"Modified {len(files_modified)} files:")
    for f in files_modified:
        print(f"  - {f}")

if __name__ == '__main__':
    main()
