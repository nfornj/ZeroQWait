// RESTYLED: Perplexity-style
import { styled } from '@mui/material/styles';
import Typography from '@mui/material/Typography';
import Breadcrumbs, { breadcrumbsClasses } from '@mui/material/Breadcrumbs';
import NavigateNextRoundedIcon from '@mui/icons-material/NavigateNextRounded';
import { useLocation } from 'react-router-dom';

const StyledBreadcrumbs = styled(Breadcrumbs)(({ theme }) => ({
  margin: 0,
  [`& .${breadcrumbsClasses.separator}`]: {
    color: (theme.vars || theme).palette.action.disabled,
    margin: 1,
  },
  [`& .${breadcrumbsClasses.ol}`]: {
    alignItems: 'center',
  },
}));

const routeNameMap: { [key: string]: string } = {
  '/dashboard': 'Agent',
  '/overview': 'Overview',

  '/appointments': 'Appointments',
  '/queues': 'Queues',
  '/agent-inbox': 'Agent Inbox',
  '/employees': 'Team',
  '/employee-dashboard': 'Employee Dashboard',
  '/analytics': 'Analytics',
  '/settings': 'Settings',
};

function resolvePageName(pathname: string) {
  if (pathname.startsWith('/queues/')) {
    return 'Queue Details';
  }

  return routeNameMap[pathname] || 'Overview';
}

export default function NavbarBreadcrumbs() {
  const location = useLocation();
  const currentPath = location.pathname;
  const pageName = resolvePageName(currentPath);

  return (
    <StyledBreadcrumbs
      aria-label="breadcrumb"
      separator={<NavigateNextRoundedIcon fontSize="small" />}
    >
      <Typography variant="body2" color="text.secondary">Workspace</Typography>
      <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 600 }}>
        {pageName}
      </Typography>
    </StyledBreadcrumbs>
  );
}
