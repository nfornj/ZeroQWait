import { ChevronRight } from 'lucide-react';
import { useLocation } from 'react-router-dom';

const routeNameMap: Record<string, string> = {
  '/dashboard': 'Agent',
  '/overview': 'Overview',

  '/appointments': 'Appointments',
  '/queues': 'Queues',
  '/agent-inbox': 'Agent Inbox',
  '/agent-brain': 'Brain',
  '/employees': 'Team',
  '/employee-dashboard': 'Employee Dashboard',
  '/analytics': 'Analytics',
  '/settings': 'Settings',
};

function resolvePageName(pathname: string) {
  if (pathname.startsWith('/queues/')) return 'Queue Details';
  return routeNameMap[pathname] || 'Overview';
}

export default function NavbarBreadcrumbs() {
  const location = useLocation();
  const pageName = resolvePageName(location.pathname);

  return (
    <nav className="flex items-center gap-1 text-sm" aria-label="breadcrumb">
      <span className="text-muted-foreground">Workspace</span>
      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/50" />
      <span className="font-semibold text-foreground">{pageName}</span>
    </nav>
  );
}
