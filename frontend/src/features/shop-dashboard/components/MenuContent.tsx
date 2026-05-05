import { Bot, GitBranch, TrendingUp, Scissors, CalendarDays, List, Settings, Users } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../../contexts/AuthContext';
import { cn } from '@/lib/utils';

const primaryNavItems = [
  { text: 'Agent', icon: Bot, path: '/dashboard' },
  { text: 'Brain', icon: GitBranch, path: '/agent-brain' },
  { text: 'Overview', icon: TrendingUp, path: '/overview' },
];

const managementNavItems = [
  { text: 'Services', icon: Scissors, path: '/services' },
  { text: 'Appointments', icon: CalendarDays, path: '/appointments' },
  { text: 'Queues', icon: List, path: '/queues' },
  { text: 'Team', icon: Users, path: '/employees' },
  { text: 'Settings', icon: Settings, path: '/settings' },
];

interface NavItemProps {
  icon: React.ElementType;
  text: string;
  path: string;
  active: boolean;
  onClick: () => void;
}

function NavItem({ icon: Icon, text, active, onClick }: NavItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
        active
          ? 'text-foreground'
          : 'text-muted-foreground hover:bg-accent hover:text-foreground',
      )}
      style={active ? {
        backgroundColor: 'color-mix(in srgb, var(--owner-primary) 12%, transparent)',
        color: 'var(--owner-primary)',
      } : undefined}
    >
      <Icon className="h-4 w-4 flex-shrink-0" />
      {text}
    </button>
  );
}

export default function MenuContent() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const isSelected = (path: string) => location.pathname === path;
  const isEmployee = user?.role === 'employee';

  const mainItems = isEmployee
    ? [{ text: 'Queue', icon: List, path: '/employee-dashboard' }]
    : primaryNavItems;
  const manageItems = isEmployee ? [] : managementNavItems;

  return (
    <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3 py-2">
      <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
        Workspace
      </p>
      {mainItems.map((item) => (
        <NavItem
          key={item.path}
          icon={item.icon}
          text={item.text}
          path={item.path}
          active={isSelected(item.path)}
          onClick={() => navigate(item.path)}
        />
      ))}

      {manageItems.length > 0 && (
        <>
          <p className="mb-1 mt-4 px-3 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
            Manage
          </p>
          {manageItems.map((item) => (
            <NavItem
              key={item.path}
              icon={item.icon}
              text={item.text}
              path={item.path}
              active={isSelected(item.path)}
              onClick={() => navigate(item.path)}
            />
          ))}
        </>
      )}
    </nav>
  );
}
