// RESTYLED: Perplexity-style
import * as React from 'react';
import { styled } from '@mui/material/styles';
import AppBar from '@mui/material/AppBar';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import MuiToolbar from '@mui/material/Toolbar';
import { tabsClasses } from '@mui/material/Tabs';
import Typography from '@mui/material/Typography';
import MenuRoundedIcon from '@mui/icons-material/MenuRounded';
import AutorenewRoundedIcon from '@mui/icons-material/AutorenewRounded';
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded';
import SideMenuMobile from './SideMenuMobile';
import MenuButton from './MenuButton';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import { useLocation } from 'react-router-dom';
import { useShop } from '../../../contexts/ShopContext';
import { useAuth } from '../../../contexts/AuthContext';

const drawerWidth = 240;

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
  const location = useLocation();
  const { user } = useAuth();
  const { shop, ownedShops, shopsLoading, refreshOwnedShops, selectOwnedShop } = useShop();

  const toggleDrawer = (newOpen: boolean) => () => {
    setOpen(newOpen);
  };

  const handleShopChange = (event: SelectChangeEvent<string>) => {
    const nextShopId = Number(event.target.value);
    if (!Number.isFinite(nextShopId)) return;
    selectOwnedShop(nextShopId);
  };

  const isEmployeeRoute = location.pathname.startsWith('/employee-dashboard');
  const isEmployee = user?.role === 'employee' || isEmployeeRoute;
  const subtitle = [shop?.city, shop?.shop_type].filter(Boolean).join(' • ')
    || (isEmployee ? 'Employee workspace' : 'Owner workspace');
  const logoSrc = shop?.id && shop?.logo_url ? `/api/shops/${shop.id}/logo` : undefined;

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
            {!isEmployee && (
              <Tooltip title="Refresh shop list">
                <span>
                  <IconButton
                    onClick={() => void refreshOwnedShops()}
                    disabled={shopsLoading}
                    sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2 }}
                  >
                    {shopsLoading ? <CircularProgress size={18} /> : <AutorenewRoundedIcon />}
                  </IconButton>
                </span>
              </Tooltip>
            )}
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
