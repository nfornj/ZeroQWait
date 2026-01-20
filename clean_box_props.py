#!/usr/bin/env python3
"""
Final comprehensive cleanup: Remove ALL Grid-specific props from Box components.
This includes: container, item, spacing, and any leftover responsive props.
"""

import re
from pathlib import Path

def clean_box_props(filepath):
    """Remove all Grid-specific props from Box components."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Remove Grid-specific props from Box: container, item, spacing, xs, sm, md, lg, xl
    grid_props = ['container', 'item', 'spacing', 'xs', 'sm', 'md', 'lg', 'xl']
    
    for prop in grid_props:
        # Remove prop={value} or prop
        content = re.sub(rf'\s+{prop}(?:=\{{[^}}]+\}}|\s|\>)', lambda m: ' ' if m.group(0).endswith('>') else '', content)
        content = re.sub(rf'\s+{prop}(?:=\{{[^}}]+\}})?', '', content)
    
    # Clean up multiple spaces
    content = re.sub(r'\s+', ' ', content)
    # Fix spacing around > and <
    content = re.sub(r'\s+>', '>', content)
    content = re.sub(r'<\s+', '<', content)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    src_dir = Path('/Users/neekrish/zeroqwait/frontend/src')
    
    files_modified = []
    
    for filepath in src_dir.rglob('*.tsx'):
        if clean_box_props(filepath):
            files_modified.append(str(filepath.relative_to(src_dir)))
    
    print(f"Modified {len(files_modified)} files:")
    for f in sorted(files_modified):
        print(f"  - {f}")

if __name__ == '__main__':
    main()
