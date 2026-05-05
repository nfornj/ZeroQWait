import * as React from 'react';
import { Menu, Bell, Search, Calendar, ChevronDown } from 'lucide-react';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import MenuButton from './MenuButton';
import SideMenuMobile from './SideMenuMobile';
import { useShop } from '../../../contexts/ShopContext';
import { useAuth } from '../../../contexts/AuthContext';
import { useThemeContext } from '../../../contexts/ThemeContext';

dayjs.extend(utc);
dayjs.extend(timezone);

const COMMON_TIMEZONES = [
  { label: 'System', value: Intl.DateTimeFormat().resolvedOptions().timeZone },
  { label: 'UTC', value: 'UTC' },
  { label: 'EST/EDT', value: 'America/New_York' },
  { label: 'PST/PDT', value: 'America/Los_Angeles' },
  { label: 'CST/CDT', value: 'America/Chicago' },
  { label: 'GMT/BST', value: 'Europe/London' },
  { label: 'JST', value: 'Asia/Tokyo' },
  { label: 'IST', value: 'Asia/Kolkata' },
];

export default function AppNavbar() {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [currentDateTime, setCurrentDateTime] = React.useState(dayjs());
  const { shop, ownedShops, selectOwnedShop } = useShop();
  const { user } = useAuth();
  const { timeZone, setTimeZone } = useThemeContext();

  React.useEffect(() => {
    setCurrentDateTime(dayjs().tz(timeZone));
    const timer = window.setInterval(() => {
      setCurrentDateTime(dayjs().tz(timeZone));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [timeZone]);

  const toggleDrawer = (v: boolean) => () => setMobileOpen(v);
  const isEmployee = user?.role === 'employee';
  const formattedTime = currentDateTime.format('h:mm A');
  const formattedDate = currentDateTime.format('MMM DD, YYYY');
  const shortTzLabel = COMMON_TIMEZONES.find((tz) => tz.value === timeZone)?.label
    ?? timeZone.split('/').pop() ?? timeZone;

  return (
    <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border bg-background px-4">

      {/* Search bar — command palette style */}
      <div className="flex flex-1 items-center">
        <button
          type="button"
          className="flex h-9 w-full max-w-sm items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <Search className="h-3.5 w-3.5 flex-shrink-0" />
          <span className="flex-1 text-left">Search...</span>
          <kbd className="hidden items-center gap-0.5 rounded border border-border bg-background px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground sm:flex">
            <span>⌘</span><span>K</span>
          </kbd>
        </button>

        {/* Multi-shop selector (desktop, when owner has > 1 shop) */}
        {!isEmployee && ownedShops.length > 1 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="ml-2 hidden md:flex items-center gap-1.5 rounded-lg border border-border bg-muted/40 px-3 py-1.5 text-sm font-medium text-foreground hover:bg-accent transition-colors"
              >
                {shop?.name ?? 'Select shop'}
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {ownedShops.map((s) => (
                <DropdownMenuItem
                  key={s.id}
                  onClick={() => selectOwnedShop(s.id)}
                  className={s.id === shop?.id ? 'font-semibold' : ''}
                >
                  {s.name}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>

      {/* Right cluster — time, timezone, date, notifications */}
      <div className="hidden md:flex items-center gap-1">
        {/* Live clock + timezone dropdown */}
        <div className="flex items-center gap-0.5 rounded-lg border border-border bg-muted/40 px-2.5 py-1.5">
          <span className="min-w-[52px] text-right text-sm font-semibold tabular-nums text-foreground">
            {formattedTime}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs text-muted-foreground hover:bg-background transition-colors"
              >
                {shortTzLabel}
                <ChevronDown className="h-3 w-3" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              {COMMON_TIMEZONES.map((tz) => (
                <DropdownMenuItem
                  key={tz.value}
                  onClick={() => setTimeZone(tz.value)}
                  className={timeZone === tz.value ? 'font-semibold' : ''}
                >
                  {tz.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Date display */}
        <button
          type="button"
          className="flex items-center gap-1.5 rounded-lg border border-border bg-muted/40 px-2.5 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
        >
          <Calendar className="h-3.5 w-3.5" />
          <span className="text-sm font-medium text-foreground">{formattedDate}</span>
        </button>

        {/* Notifications */}
        <MenuButton showBadge aria-label="Open notifications">
          <Bell className="h-4 w-4" />
        </MenuButton>
      </div>

      {/* Mobile hamburger */}
      <MenuButton
        className="md:hidden"
        aria-label="Open menu"
        onClick={toggleDrawer(true)}
      >
        <Menu className="h-5 w-5" />
      </MenuButton>

      <SideMenuMobile open={mobileOpen} toggleDrawer={toggleDrawer} />
    </header>
  );
}
