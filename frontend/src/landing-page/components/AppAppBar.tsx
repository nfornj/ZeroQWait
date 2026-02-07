import * as React from 'react';
import { styled, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Container from '@mui/material/Container';
import Divider from '@mui/material/Divider';
import MenuItem from '@mui/material/MenuItem';
import Drawer from '@mui/material/Drawer';
import MenuIcon from '@mui/icons-material/Menu';
import Typography from '@mui/material/Typography';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import SmartToyIcon from '@mui/icons-material/SmartToy';


import ColorModeIconDropdown from '../../features/auth/components/auth-shared-theme/ColorModeIconDropdown';

const StyledToolbar = styled(Toolbar)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  flexShrink: 0,
  borderRadius: `calc(${theme.shape.borderRadius}px + 8px)`,
  backdropFilter: 'blur(24px)',
  border: '1px solid',
  borderColor: (theme.vars || theme).palette.divider,
  backgroundColor: theme.vars
    ? `rgba(${theme.vars.palette.background.defaultChannel} / 0.4)`
    : alpha(theme.palette.background.default, 0.4),
  boxShadow: (theme.vars || theme).shadows[1],
  padding: '8px 12px',
}));

export default function AppAppBar() {
  const [open, setOpen] = React.useState(false);

  const toggleDrawer = (newOpen: boolean) => () => {
    setOpen(newOpen);
  };

  const scrollToSection = (sectionId: string) => {
    const sectionElement = document.getElementById(sectionId);
    const offset = 128;
    if (sectionElement) {
      const targetScroll = sectionElement.offsetTop - offset;
      sectionElement.scrollIntoView({ behavior: 'smooth' });
      window.scrollTo({
        top: targetScroll,
        behavior: 'smooth',
      });
      setOpen(false);
    }
  };

  const handleSignIn = () => {
    const currentHost = window.location.hostname;
    const protocol = window.location.protocol;

    // Check if we're on a shop subdomain (anything other than bare domain or www)
    const isShopSubdomain = () => {
      if (currentHost === 'localhost') return false;
      if (currentHost.match(/^\d+\.\d+\.\d+\.\d+\.(nip|np)\.io$/)) return false; // bare nip.io
      if (currentHost.match(/^www\./)) return false; // www subdomain

      // If hostname has more than 2 parts (excluding nip.io which has 4), it's a subdomain
      const parts = currentHost.split('.');
      if (currentHost.includes('nip.io') || currentHost.includes('np.io')) {
        // For nip.io: shop.192.168.1.1.nip.io has 5 parts
        return parts.length > 4;
      } else {
        // For normal domains: shop.example.com has 3 parts
        return parts.length > 2;
      }
    };

    if (isShopSubdomain()) {
      // Redirect to main domain
      let mainDomainUrl;
      if (currentHost.includes('nip.io') || currentHost.includes('np.io')) {
        // Extract IP and redirect to bare IP domain
        const ipMatch = currentHost.match(/(\d+\.\d+\.\d+\.\d+\.(nip|np)\.io)$/);
        if (ipMatch) {
          mainDomainUrl = `${protocol}//${ipMatch[1]}/login`;
        } else {
          mainDomainUrl = '/login'; // fallback
        }
      } else {
        // Extract main domain (last 2 parts)
        const parts = currentHost.split('.');
        const mainDomain = parts.slice(-2).join('.');
        mainDomainUrl = `${protocol}//${mainDomain}/login`;
      }

      console.log('[AppAppBar] Redirecting from shop subdomain to main domain:', mainDomainUrl);
      window.location.href = mainDomainUrl;
    } else {
      // Already on main domain, use relative navigation
      window.location.href = '/login';
    }
  };

  const handleSignUp = () => {
    const currentHost = window.location.hostname;
    const protocol = window.location.protocol;

    // Same subdomain detection logic
    const isShopSubdomain = () => {
      if (currentHost === 'localhost') return false;
      if (currentHost.match(/^\d+\.\d+\.\d+\.\d+\.(nip|np)\.io$/)) return false;
      if (currentHost.match(/^www\./)) return false;

      const parts = currentHost.split('.');
      if (currentHost.includes('nip.io') || currentHost.includes('np.io')) {
        return parts.length > 4;
      } else {
        return parts.length > 2;
      }
    };

    if (isShopSubdomain()) {
      let mainDomainUrl;
      if (currentHost.includes('nip.io') || currentHost.includes('np.io')) {
        const ipMatch = currentHost.match(/(\d+\.\d+\.\d+\.\d+\.(nip|np)\.io)$/);
        if (ipMatch) {
          mainDomainUrl = `${protocol}//${ipMatch[1]}/signup`;
        } else {
          mainDomainUrl = '/signup';
        }
      } else {
        const parts = currentHost.split('.');
        const mainDomain = parts.slice(-2).join('.');
        mainDomainUrl = `${protocol}//${mainDomain}/signup`;
      }

      console.log('[AppAppBar] Redirecting from shop subdomain to main domain:', mainDomainUrl);
      window.location.href = mainDomainUrl;
    } else {
      window.location.href = '/signup';
    }
  };

  return (
    <AppBar
      position="fixed"
      enableColorOnDark
      sx={{
        boxShadow: 0,
        bgcolor: 'transparent',
        backgroundImage: 'none',
        mt: 'calc(var(--template-frame-height, 0px) + 28px)',
      }}
    >
      <Container maxWidth="lg">
        <StyledToolbar variant="dense" disableGutters>
          <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', px: 0 }}>
            {/* Logo wrapper to allow scroll to top */}
            <Box
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              sx={{ cursor: 'pointer', display: 'flex', alignItems: 'center', mr: 2 }}
            >
              <Typography variant="h6" sx={{ color: 'text.primary', fontWeight: 'bold' }}>
                ZeroQwait
              </Typography>
            </Box>
            <Box sx={{ display: { xs: 'none', md: 'flex' } }}>
              <Button variant="text" color="info" size="small" onClick={() => scrollToSection('features')}>
                Features
              </Button>
              <Button variant="text" color="info" size="small" onClick={() => scrollToSection('testimonials')}>
                Testimonials
              </Button>
              <Button variant="text" color="info" size="small" onClick={() => scrollToSection('highlights')}>
                Highlights
              </Button>
              <Button variant="text" color="info" size="small" onClick={() => scrollToSection('pricing')}>
                Pricing
              </Button>
              <Button variant="text" color="info" size="small" onClick={() => scrollToSection('faq')} sx={{ minWidth: 0 }}>
                FAQ
              </Button>
              <Button variant="text" color="info" size="small" sx={{ minWidth: 0 }}>
                Blog
              </Button>
            </Box>
          </Box>
          <Box
            sx={{
              display: { xs: 'none', md: 'flex' },
              gap: 1,
              alignItems: 'center',
            }}
          >
            <Button color="primary" variant="text" size="small" onClick={handleSignIn}>
              Sign in
            </Button>
            <Button color="primary" variant="contained" size="small" onClick={handleSignUp}>
              Sign up
            </Button>
            <ColorModeIconDropdown />
          </Box>
          <Box sx={{ display: { xs: 'flex', md: 'none' }, gap: 1 }}>
            <IconButton aria-label="Menu button" onClick={toggleDrawer(true)}>
              <MenuIcon />
            </IconButton>
            <Drawer
              anchor="top"
              open={open}
              onClose={toggleDrawer(false)}
              PaperProps={{
                sx: {
                  top: 'var(--template-frame-height, 0px)',
                },
              }}
            >
              <Box sx={{ p: 2, backgroundColor: 'background.default' }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                  }}
                >
                  <IconButton onClick={toggleDrawer(false)}>
                    <CloseRoundedIcon />
                  </IconButton>
                </Box>

                <MenuItem onClick={() => scrollToSection('features')}>Features</MenuItem>
                <MenuItem onClick={() => scrollToSection('testimonials')}>Testimonials</MenuItem>
                <MenuItem onClick={() => scrollToSection('highlights')}>Highlights</MenuItem>
                <MenuItem onClick={() => scrollToSection('pricing')}>Pricing</MenuItem>
                <MenuItem onClick={() => scrollToSection('faq')}>FAQ</MenuItem>
                <MenuItem>Blog</MenuItem>
                <Divider sx={{ my: 3 }} />
                <MenuItem>
                  <Button color="primary" variant="contained" fullWidth onClick={handleSignUp}>
                    Sign up
                  </Button>
                </MenuItem>
                <MenuItem>
                  <Button color="primary" variant="outlined" fullWidth onClick={handleSignIn}>
                    Sign in
                  </Button>
                </MenuItem>
              </Box>
            </Drawer>
          </Box>
        </StyledToolbar>
      </Container>
    </AppBar>
  );
}
