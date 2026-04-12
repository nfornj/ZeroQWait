import React, { useState, useEffect } from 'react';
import Stack from '@mui/material/Stack';
import Box from '@mui/material/Box';
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded';
import CustomDatePicker from './CustomDatePicker';
import NavbarBreadcrumbs from './NavbarBreadcrumbs';
import MenuButton from './MenuButton';
import Typography from '@mui/material/Typography';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Button from '@mui/material/Button';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useThemeContext } from '../../../contexts/ThemeContext';

dayjs.extend(utc);
dayjs.extend(timezone);

// Common Timezones for Simplicity
const COMMON_TIMEZONES = [
  { label: 'Local (System)', value: Intl.DateTimeFormat().resolvedOptions().timeZone },
  { label: 'UTC', value: 'UTC' },
  { label: 'New York (EST/EDT)', value: 'America/New_York' },
  { label: 'Los Angeles (PST/PDT)', value: 'America/Los_Angeles' },
  { label: 'Chicago (CST/CDT)', value: 'America/Chicago' },
  { label: 'London (GMT/BST)', value: 'Europe/London' },
  { label: 'Tokyo (JST)', value: 'Asia/Tokyo' },
  { label: 'India (IST)', value: 'Asia/Kolkata' },
];

export default function Header() {
  const { timeZone, setTimeZone } = useThemeContext();
  const [currentDateTime, setCurrentDateTime] = useState(dayjs().tz(timeZone));
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  useEffect(() => {
    // Update time immediately when timezone changes
    setCurrentDateTime(dayjs().tz(timeZone));

    // Timer to update every second
    const timer = setInterval(() => {
      setCurrentDateTime(dayjs().tz(timeZone));
    }, 1000);
    return () => clearInterval(timer);
  }, [timeZone]);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = (tz?: string) => {
    if (tz) setTimeZone(tz);
    setAnchorEl(null);
  };

  // Format: "11:27 AM"
  const formattedTime = currentDateTime.format('h:mm A');
  // Get short timezone name (e.g. EST, GMT) - tricky with dayjs, simpler to show the Label or City
  // Or use 'z' format if timezone plugin supports it well, but often returns full name.
  // We'll stick to a simple clean display: "11:27 AM | New York"

  // Find label for current timezone value
  const currentTzLabel = COMMON_TIMEZONES.find(t => t.value === timeZone)?.label || timeZone.split('/')[1] || timeZone;
  const shortLabel = currentTzLabel.includes('(') ? currentTzLabel.split('(')[1].replace(')', '') : currentTzLabel;

  return (
    <Stack
      direction="row"
      sx={{
        display: { xs: 'none', md: 'flex' },
        width: '100%',
        alignItems: { xs: 'flex-start', md: 'center' },
        justifyContent: 'space-between',
        maxWidth: { sm: '100%', md: '1700px' },
        pt: 0.5,
        pb: 1.5,
      }}
      spacing={2}
    >
      <NavbarBreadcrumbs />
      <Stack direction="row" sx={{ gap: 1, alignItems: 'center' }}>

        {/* Time & Timezone Selector */}
        <Box sx={{ display: 'flex', alignItems: 'center', mr: 2, bgcolor: 'var(--owner-glass-bg)', backdropFilter: 'blur(18px)', borderRadius: 2, px: 1, border: '1px solid', borderColor: 'var(--owner-glass-border)', boxShadow: 'var(--owner-glass-shadow)' }}>
          <Typography variant="body1" sx={{ fontWeight: 'bold', mr: 1, minWidth: 70, textAlign: 'right' }}>
            {formattedTime}
          </Typography>
          <Button
            size="small"
            onClick={handleClick}
            endIcon={<KeyboardArrowDownIcon />}
            sx={{ textTransform: 'none', color: 'text.secondary', minWidth: 'auto', px: 1 }}
          >
            {shortLabel}
          </Button>

          <Menu
            anchorEl={anchorEl}
            open={open}
            onClose={() => handleClose()}
          >
            {COMMON_TIMEZONES.map((tz) => (
              <MenuItem key={tz.value} onClick={() => handleClose(tz.value)} selected={timeZone === tz.value}>
                {tz.label}
              </MenuItem>
            ))}
          </Menu>
        </Box>

        <CustomDatePicker />
        <MenuButton showBadge aria-label="Open notifications">
          <NotificationsRoundedIcon />
        </MenuButton>
      </Stack>
    </Stack>
  );
}
