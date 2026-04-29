// RESTYLED: Perplexity-style
import * as React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import MuiAvatar from '@mui/material/Avatar';
import MuiListItemAvatar from '@mui/material/ListItemAvatar';
import Divider from '@mui/material/Divider';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import { useLocation } from 'react-router-dom';
import { useShop } from '../../../contexts/ShopContext';
import { useAuth } from '../../../contexts/AuthContext';

const Avatar = styled(MuiAvatar)(({ theme }) => ({
  width: 28,
  height: 28,
  backgroundColor: (theme.vars || theme).palette.background.paper,
  color: (theme.vars || theme).palette.text.secondary,
  border: `1px solid ${(theme.vars || theme).palette.divider}`,
}));

const ListItemAvatar = styled(MuiListItemAvatar)({
  minWidth: 0,
  marginRight: 12,
});

export default function SelectContent() {
  const location = useLocation();
  const { shop, loading } = useShop();
  const { user, logout } = useAuth();
  const isEmployee = user?.role === 'employee' || location.pathname.startsWith('/employee-dashboard');

  if (isEmployee) {
    return (
      <Box
        sx={{
          width: '100%',
          bgcolor: 'var(--owner-glass-bg)',
          backdropFilter: 'blur(18px)',
          borderRadius: 3,
          boxShadow: 'var(--owner-glass-shadow)',
          border: '1px solid var(--owner-glass-border)',
          p: 1.25,
        }}
      >
        <Stack spacing={1.25}>
          <Stack direction="row" spacing={1.25} alignItems="center">
            <Avatar alt={user?.username || 'Employee'} src={user?.profile_photo_url} sx={{ width: 36, height: 36 }}>
              <PersonRoundedIcon sx={{ fontSize: '1rem' }} />
            </Avatar>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }} noWrap>
                {user?.username || 'Employee'}
              </Typography>
              <Typography variant="caption" color="text.secondary" noWrap>
                {user?.email || 'Queue workspace'}
              </Typography>
            </Box>
          </Stack>

          <Divider />

          <Button
            variant="outlined"
            color="inherit"
            fullWidth
            size="small"
            onClick={logout}
            startIcon={<LogoutRoundedIcon />}
          >
            Logout
          </Button>
        </Stack>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      <Box sx={{ px: 1.5, py: 1.5, mb: 0.5 }}>
        {loading || !shop ? (
          <Skeleton variant="text" width={140} height={22} />
        ) : (
          <Typography
            sx={{
              fontSize: '0.9375rem',
              fontWeight: 600,
              letterSpacing: '-0.01em',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '188px',
              color: 'text.primary',
            }}
          >
            {shop.name}
          </Typography>
        )}
      </Box>

      <Button
        variant="text"
        color="inherit"
        size="small"
        onClick={logout}
        startIcon={<LogoutRoundedIcon />}
        sx={{
          justifyContent: 'flex-start',
          px: 1.5,
          minHeight: 32,
          color: 'text.secondary',
        }}
      >
        Logout
      </Button>
    </Box>
  );
}
