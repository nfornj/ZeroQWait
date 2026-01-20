#!/usr/bin/env python3
"""
Remove responsive props from Box components and add proper flex sizing.
"""

import re
from pathlib import Path

def remove_responsive_props_from_box(filepath):
    """Remove xs, md, sm, lg, xl props from Box and add flex sizing."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern to match <Box xs={...} md={...} ...> and extract all attributes
    def replace_box(match):
        full_tag = match.group(0)
        
        # Extract existing attributes
        attrs = match.group(1).strip() if match.group(1) else ''
        
        # Remove responsive grid props (xs, sm, md, lg, xl)
        attrs = re.sub(r'\s*(?:xs|sm|md|lg|xl)=\{[^}]+\}', '', attrs)
        
        # Add flex: 1 to make boxes responsive within flex container
        # Only if there are other attributes and no existing sx prop
        if attrs and 'sx=' not in attrs:
            attrs = f'sx={{{{ flex: 1, minWidth: \'250px\' }}}} {attrs}'
        elif not attrs:
            attrs = 'sx={{ flex: 1, minWidth: \'250px\' }}'
        
        # Clean up extra spaces
        attrs = re.sub(r'\s+', ' ', attrs).strip()
        
        return f'<Box {attrs}>' if attrs else '<Box>'
    
    # Replace Box tags that have responsive props
    content = re.sub(
        r'<Box\s+([^>]*(?:xs|sm|md|lg|xl)=[^>]*)>',
        replace_box,
        content
    )
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    src_dir = Path('/Users/neekrish/zeroqwait/frontend/src')
    
    files_modified = []
    
    for filepath in src_dir.rglob('*.tsx'):
        if remove_responsive_props_from_box(filepath):
            files_modified.append(str(filepath.relative_to(src_dir)))
    
    print(f"Modified {len(files_modified)} files:")
    for f in sorted(files_modified):
        print(f"  - {f}")

if __name__ == '__main__':
    main()
