import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import DashboardRoundedIcon from '@mui/icons-material/DashboardRounded';
import InsightsRoundedIcon from '@mui/icons-material/InsightsRounded';
import QueueRoundedIcon from '@mui/icons-material/QueueRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import ContentCutRoundedIcon from '@mui/icons-material/ContentCutRounded';
import InfoRoundedIcon from '@mui/icons-material/InfoRounded';
import HelpRoundedIcon from '@mui/icons-material/HelpRounded';
import SmartToyRoundedIcon from '@mui/icons-material/SmartToyRounded';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../../contexts/AuthContext';

const mainListItems = [
  { text: 'Dashboard', icon: <DashboardRoundedIcon />, path: '/dashboard' },
  { text: 'Overview', icon: <InsightsRoundedIcon />, path: '/overview' },
  { text: 'Services', icon: <ContentCutRoundedIcon />, path: '/services' },
  { text: 'Queues', icon: <QueueRoundedIcon />, path: '/queues' },
  { text: 'Shop Setup', icon: <SettingsRoundedIcon />, path: '/settings' },
  { text: 'Team', icon: <PeopleRoundedIcon />, path: '/employees' },
];

const secondaryListItems = [
  { text: 'About', icon: <InfoRoundedIcon />, path: '/about' },
  { text: 'Feedback', icon: <HelpRoundedIcon />, path: '/feedback' },
];

export default function MenuContent() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const isSelected = (path: string) => location.pathname === path;

  const isEmployee = user?.role === 'employee';
  const visibleMainItems = isEmployee
    ? [{ text: 'Queue', icon: <QueueRoundedIcon />, path: '/employee-dashboard' }]
    : mainListItems;
  const visibleSecondaryItems = isEmployee ? [] : secondaryListItems;

  return (
    <Stack sx={{ flexGrow: 1, p: 1.25, justifyContent: 'space-between' }}>
      <List dense sx={{ p: 0 }}>
        <Typography variant="overline" sx={{ px: 1.5, color: 'text.secondary', fontWeight: 700 }}>
          Workspace
        </Typography>
        {visibleMainItems.map((item, index) => (
          <ListItem key={index} disablePadding sx={{ display: 'block' }}>
            <ListItemButton
              selected={isSelected(item.path)}
              onClick={() => navigate(item.path)}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                '&.Mui-selected': {
                  bgcolor: 'var(--owner-primary)',
                  color: '#fff',
                  boxShadow: 'var(--owner-glass-shadow)',
                  '& .MuiListItemIcon-root': { color: '#fff' },
                  '&:hover': { bgcolor: 'var(--owner-primary)' },
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      {visibleSecondaryItems.length > 0 && (
      <List dense sx={{ p: 0 }}>
        <Typography variant="overline" sx={{ px: 1.5, color: 'text.secondary', fontWeight: 700 }}>
          Support
        </Typography>
        {visibleSecondaryItems.map((item, index) => (
          <ListItem key={index} disablePadding sx={{ display: 'block' }}>
            <ListItemButton
              selected={isSelected(item.path)}
              onClick={() => navigate(item.path)}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                '&.Mui-selected': {
                  bgcolor: 'var(--owner-glass-bg)',
                  border: '1px solid var(--owner-glass-border)',
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.text} />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
      )}
    </Stack>
  );
}
