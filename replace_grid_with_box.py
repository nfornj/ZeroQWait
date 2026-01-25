#!/usr/bin/env python3
"""
Replace MUI Grid with Box flexbox for MUI v7 compatibility.
Grid responsive props (xs, md, etc.) are not supported in MUI v7 without Grid2.
"""

import re
from pathlib import Path

def replace_grid_with_box(filepath):
    """Replace Grid components with Box flexbox."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Remove Grid from imports and ensure Box is imported
    if 'from \'@mui/material\'' in content or 'from "@mui/material"' in content:
        # Check if Grid is imported
        if re.search(r'{\s*[^}]*\bGrid\b[^}]*}.*from\s+[\'"]@mui/material', content):
            # Remove Grid from import
            content = re.sub(
                r'(\{\s*[^}]*),?\s*Grid\s*,?\s*([^}]*}.*from\s+[\'"]@mui/material)',
                r'\1\2',
                content
            )
            # Clean up double commas
            content = re.sub(r',\s*,', ',', content)
    
    # Replace <Grid container ...> with <Box display="flex" flexWrap="wrap" ...>
    content = re.sub(
        r'<Grid\s+container\s+spacing={(\d+)}([^>]*)>',
        r'<Box display="flex" flexWrap="wrap" gap={\1}\2>',
        content
    )
    
    # Replace Grid child elements with Box
    # Pattern: <Grid xs={...} md={...} ...>
    content = re.sub(
        r'<Grid\s+([^>]*)>',
        r'<Box \1>',
        content
    )
    
    # Replace closing </Grid>
    content = re.sub(r'</Grid>', r'</Box>', content)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    src_dir = Path('/Users/neekrish/zeroqwait/frontend/src')
    
    files_modified = []
    
    for filepath in src_dir.rglob('*.tsx'):
        if replace_grid_with_box(filepath):
            files_modified.append(str(filepath.relative_to(src_dir)))
    
    print(f"Modified {len(files_modified)} files:")
    for f in sorted(files_modified):
        print(f"  - {f}")

if __name__ == '__main__':
    main()
