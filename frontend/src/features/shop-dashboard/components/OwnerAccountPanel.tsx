import * as React from 'react';
import { LogOut, Sun, Moon, Settings, MoreHorizontal, User } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAuth } from '../../../contexts/AuthContext';
import { useThemeContext } from '../../../contexts/ThemeContext';

function getDisplayName(user: ReturnType<typeof useAuth>['user']) {
  if (!user) return 'Shop Owner';
  return user.username || user.email || 'Shop Owner';
}

function getInitials(value: string) {
  const parts = value.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return 'SO';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

export default function OwnerAccountPanel() {
  const { user, logout } = useAuth();
  const { mode, toggleMode } = useThemeContext();
  const displayName = getDisplayName(user);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center gap-3 rounded-xl border border-border bg-muted/40 p-3 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Avatar className="h-8 w-8 flex-shrink-0">
            <AvatarImage src={user?.profile_photo_url} alt={displayName} />
            <AvatarFallback
              className="text-xs font-semibold text-white"
              style={{ backgroundColor: 'var(--owner-primary, #7c3aed)' }}
            >
              {getInitials(displayName)}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold leading-tight text-foreground">{displayName}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.email || 'Account settings'}</p>
          </div>
          <MoreHorizontal className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium">{displayName}</p>
            <p className="text-xs text-muted-foreground">{user?.email}</p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>
          <User className="mr-2 h-4 w-4" />
          Profile
        </DropdownMenuItem>
        <DropdownMenuItem onClick={toggleMode}>
          {mode === 'dark' ? <Sun className="mr-2 h-4 w-4" /> : <Moon className="mr-2 h-4 w-4" />}
          {mode === 'dark' ? 'Light mode' : 'Dark mode'}
        </DropdownMenuItem>
        <DropdownMenuItem disabled>
          <Settings className="mr-2 h-4 w-4" />
          Preferences
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={logout} className="text-destructive focus:text-destructive">
          <LogOut className="mr-2 h-4 w-4" />
          Logout
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
