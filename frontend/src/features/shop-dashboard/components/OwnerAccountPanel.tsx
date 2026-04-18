import * as React from 'react';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import Divider from '@mui/material/Divider';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import ButtonBase from '@mui/material/ButtonBase';
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded';
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded';
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded';
import MoreHorizRoundedIcon from '@mui/icons-material/MoreHorizRounded';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import TuneRoundedIcon from '@mui/icons-material/TuneRounded';
import { useAuth } from '../../../contexts/AuthContext';
import { useThemeContext } from '../../../contexts/ThemeContext';

const getDisplayName = (user: ReturnType<typeof useAuth>['user']) => {
  if (!user) return 'Shop Owner';
  return user.username || user.email || 'Shop Owner';
};

const getInitials = (value: string) => {
  const parts = value.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'SO';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ''}${parts[1][0] || ''}`.toUpperCase();
};

export default function OwnerAccountPanel() {
  const { user, logout } = useAuth();
  const { mode, toggleMode } = useThemeContext();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const displayName = getDisplayName(user);
  const subtitle = user?.email || 'Account settings';

  const handleOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleThemeToggle = () => {
    toggleMode();
    handleClose();
  };

  const handleLogout = () => {
    logout();
    handleClose();
  };

  return (
    <>
      <Card
        variant="outlined"
        sx={{
          bgcolor: 'var(--owner-glass-bg)',
          backdropFilter: 'blur(18px)',
          borderColor: 'var(--owner-glass-border)',
          boxShadow: 'var(--owner-glass-shadow)',
          borderRadius: 3,
        }}
      >
        <ButtonBase
          onClick={handleOpen}
          sx={{
            width: '100%',
            borderRadius: 3,
            textAlign: 'left',
            p: 1.25,
          }}
        >
          <Stack direction="row" spacing={1.25} alignItems="center" sx={{ width: '100%', minWidth: 0 }}>
            <Avatar
              alt={displayName}
              src={user?.profile_photo_url}
              sx={{
                width: 38,
                height: 38,
                bgcolor: 'var(--owner-primary)',
                color: '#fff',
                flexShrink: 0,
              }}
            >
              {getInitials(displayName)}
            </Avatar>
            <Box sx={{ minWidth: 0, flexGrow: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 700, lineHeight: 1.25 }} noWrap>
                {displayName}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }} noWrap>
                {subtitle}
              </Typography>
            </Box>
            <MoreHorizRoundedIcon sx={{ color: 'text.secondary', flexShrink: 0 }} />
          </Stack>
        </ButtonBase>
      </Card>

      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        anchorOrigin={{ horizontal: 'right', vertical: 'top' }}
        transformOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <MenuItem disabled>
          <ListItemIcon>
            <PersonRoundedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary={displayName}
            secondary="Profile preferences coming soon"
          />
        </MenuItem>
        <Divider />
        <MenuItem onClick={handleThemeToggle}>
          <ListItemIcon>
            {mode === 'dark' ? <LightModeRoundedIcon fontSize="small" /> : <DarkModeRoundedIcon fontSize="small" />}
          </ListItemIcon>
          <ListItemText
            primary={mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            secondary="Appearance"
          />
        </MenuItem>
        <MenuItem disabled>
          <ListItemIcon>
            <TuneRoundedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Preferences" secondary="More settings coming soon" />
        </MenuItem>
        <Divider />
        <MenuItem onClick={handleLogout}>
          <ListItemIcon>
            <LogoutRoundedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText primary="Logout" />
        </MenuItem>
      </Menu>
    </>
  );
}