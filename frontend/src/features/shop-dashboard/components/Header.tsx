// RESTYLED: Perplexity-style
import React from 'react';
import Stack from '@mui/material/Stack';
import NavbarBreadcrumbs from './NavbarBreadcrumbs';

export default function Header() {
  return (
    <Stack
      direction="row"
      sx={{
        display: { xs: 'none', md: 'flex' },
        width: '100%',
        alignItems: { xs: 'flex-start', md: 'center' },
        justifyContent: 'flex-start',
        maxWidth: { sm: '100%', md: '1700px' },
        pt: 0,
        pb: 1,
      }}
      spacing={2}
    >
      <NavbarBreadcrumbs />
    </Stack>
  );
}
