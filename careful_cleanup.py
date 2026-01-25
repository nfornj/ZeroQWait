#!/usr/bin/env python3
"""
Carefully remove Grid-specific props from Box without breaking syntax.
"""

import re
from pathlib import Path

def remove_box_grid_props(filepath):
    """Remove container, item, spacing props from Box tags."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    original = ''.join(lines)
    modified = []
    changed = False
    
    for line in lines:
        original_line = line
        
        # Only process lines that have <Box with the problematic props
        if '<Box' in line and any(prop in line for prop in [' container', ' item', ' spacing=']):
            # Remove container prop (standalone or with space)
            line = re.sub(r'\s+container(?=[\s>])', '', line)
            # Remove item prop
            line = re.sub(r'\s+item(?=[\s>])', '', line)
            # Remove spacing prop with value
            line = re.sub(r'\s+spacing=\{[^}]+\}', '', line)
        
        if line != original_line:
            changed = True
        
        modified.append(line)
    
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(modified)
        return True
    return False

def main():
    src_dir = Path('/Users/neekrish/zeroqwait/frontend/src')
    
    files_modified = []
    
    for filepath in src_dir.rglob('*.tsx'):
        if remove_box_grid_props(filepath):
            files_modified.append(str(filepath.relative_to(src_dir)))
    
    print(f"Modified {len(files_modified)} files:")
    for f in sorted(files_modified):
        print(f"  - {f}")

if __name__ == '__main__':
    main()
