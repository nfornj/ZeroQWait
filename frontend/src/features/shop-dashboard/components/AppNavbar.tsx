// RESTYLED: Perplexity-style
import * as React from 'react';
import { styled } from '@mui/material/styles';
import AppBar from '@mui/material/AppBar';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import MuiToolbar from '@mui/material/Toolbar';
import { tabsClasses } from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import MenuRoundedIcon from '@mui/icons-material/MenuRounded';
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded';
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import SideMenuMobile from './SideMenuMobile';
import Button from '@mui/material/Button';
import MenuButton from './MenuButton';
import Menu from '@mui/material/Menu';
import { useLocation } from 'react-router-dom';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import { useShop } from '../../../contexts/ShopContext';
import { useAuth } from '../../../contexts/AuthContext';
import { useThemeContext } from '../../../contexts/ThemeContext';
import CustomDatePicker from './CustomDatePicker';

const drawerWidth = 240;

dayjs.extend(utc);
dayjs.extend(timezone);

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

const Toolbar = styled(MuiToolbar)({
  width: '100%',
  padding: '10px 16px',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: '10px',
  flexShrink: 0,
  [`& ${tabsClasses.flexContainer}`]: {
    gap: '8px',
    p: '8px',
    pb: 0,
  },
});

export default function AppNavbar() {
  const [open, setOpen] = React.useState(false);
  const [currentDateTime, setCurrentDateTime] = React.useState(dayjs());
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const location = useLocation();
  const { user } = useAuth();
  const { shop, ownedShops, selectOwnedShop } = useShop();
  const { timeZone, setTimeZone } = useThemeContext();

  React.useEffect(() => {
    setCurrentDateTime(dayjs().tz(timeZone));
    const timer = window.setInterval(() => {
      setCurrentDateTime(dayjs().tz(timeZone));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [timeZone]);

  const toggleDrawer = (newOpen: boolean) => () => {
    setOpen(newOpen);
  };

  const handleTimeZoneClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleTimeZoneClose = (nextTimeZone?: string) => {
    if (nextTimeZone) {
      setTimeZone(nextTimeZone);
    }
    setAnchorEl(null);
  };

  const handleShopChange = (event: SelectChangeEvent<string>) => {
    const nextShopId = Number(event.target.value);
    if (!Number.isFinite(nextShopId)) return;
    selectOwnedShop(nextShopId);
  };

  const isEmployeeRoute = location.pathname.startsWith('/employee-dashboard');
  const isEmployee = user?.role === 'employee' || isEmployeeRoute;
  const timeMenuOpen = Boolean(anchorEl);
  const subtitle = [shop?.city, shop?.shop_type].filter(Boolean).join(' • ')
    || (isEmployee ? 'Employee workspace' : 'Owner workspace');
  const logoSrc = shop?.id && shop?.logo_url ? `/api/shops/${shop.id}/logo` : undefined;
  const formattedTime = currentDateTime.format('h:mm A');
  const currentTzLabel = COMMON_TIMEZONES.find((tz) => tz.value === timeZone)?.label
    || timeZone.split('/')[1]
    || timeZone;
  const shortLabel = currentTzLabel.includes('(')
    ? currentTzLabel.split('(')[1].replace(')', '')
    : currentTzLabel;

  return (
    <AppBar
      position="fixed"
      sx={{
        display: 'block',
        boxShadow: 'none',
        bgcolor: 'background.paper',
        backgroundImage: 'none',
        borderBottom: '1px solid',
        borderColor: 'divider',
        top: 'var(--template-frame-height, 0px)',
        width: { md: `calc(100% - ${drawerWidth}px)` },
        ml: { md: `${drawerWidth}px` },
      }}
    >
      <Toolbar variant="regular">
        <Stack
          direction="row"
          sx={{
            alignItems: 'center',
            flexGrow: 1,
            width: '100%',
            gap: { xs: 1, md: 2 },
          }}
        >
          <Stack
            direction="row"
            spacing={1.25}
            sx={{ alignItems: 'center', mr: 'auto', minWidth: 0 }}
          >
            <Avatar
              alt={shop?.name || 'Active shop'}
              src={logoSrc}
              sx={{
                width: { xs: 32, md: 36 },
                height: { xs: 32, md: 36 },
                bgcolor: 'background.default',
                color: 'text.secondary',
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <BusinessRoundedIcon fontSize="small" />
            </Avatar>
            <Box sx={{ minWidth: 0 }}>
              <Typography
                variant={shop?.name ? 'subtitle1' : 'body1'}
                component="h1"
                sx={{ color: 'text.primary', fontWeight: 600, lineHeight: 1.15 }}
                noWrap
              >
                {shop?.name || 'Shop Dashboard'}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25 }} noWrap>
                {subtitle}
              </Typography>
            </Box>
          </Stack>

          <Stack direction="row" spacing={1} alignItems="center" sx={{ display: { xs: 'none', md: 'flex' } }}>
            {!isEmployee && ownedShops.length > 1 && (
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel id="desktop-shop-select-label">Shop</InputLabel>
                <Select
                  labelId="desktop-shop-select-label"
                  label="Shop"
                  value={shop?.id ? String(shop.id) : ''}
                  onChange={handleShopChange}
                  sx={{
                    bgcolor: 'background.paper',
                    borderRadius: 2,
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: 'divider',
                    },
                  }}
                >
                  {ownedShops.map((ownedShop) => (
                    <MenuItem key={ownedShop.id} value={String(ownedShop.id)}>
                      {ownedShop.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                bgcolor: 'background.paper',
                borderRadius: 2,
                px: 1,
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  color: 'text.primary',
                  fontWeight: 600,
                  mr: 1,
                  minWidth: 64,
                  textAlign: 'right',
                }}
              >
                {formattedTime}
              </Typography>
              <Button
                size="small"
                onClick={handleTimeZoneClick}
                endIcon={<KeyboardArrowDownIcon />}
                sx={{ textTransform: 'none', color: 'text.secondary', minWidth: 'auto', px: 1, fontWeight: 500 }}
              >
                {shortLabel}
              </Button>
              <Menu anchorEl={anchorEl} open={timeMenuOpen} onClose={() => handleTimeZoneClose()}>
                {COMMON_TIMEZONES.map((tz) => (
                  <MenuItem
                    key={tz.value}
                    onClick={() => handleTimeZoneClose(tz.value)}
                    selected={timeZone === tz.value}
                  >
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

          <MenuButton aria-label="menu" onClick={toggleDrawer(true)} sx={{ display: { xs: 'inline-flex', md: 'none' } }}>
            <MenuRoundedIcon />
          </MenuButton>
          <SideMenuMobile open={open} toggleDrawer={toggleDrawer} />
        </Stack>
      </Toolbar>
    </AppBar>
  );
}
