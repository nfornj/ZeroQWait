import * as React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import MuiAvatar from '@mui/material/Avatar';
import MuiListItemAvatar from '@mui/material/ListItemAvatar';
import MenuItem from '@mui/material/MenuItem';
import ListItemText from '@mui/material/ListItemText';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListSubheader from '@mui/material/ListSubheader';
import Select, { SelectChangeEvent, selectClasses } from '@mui/material/Select';
import Divider from '@mui/material/Divider';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';
import AutorenewRoundedIcon from '@mui/icons-material/AutorenewRounded';
import DevicesRoundedIcon from '@mui/icons-material/DevicesRounded';
import LogoutRoundedIcon from '@mui/icons-material/LogoutRounded';
import PersonRoundedIcon from '@mui/icons-material/PersonRounded';
import { useShop } from '../../../contexts/ShopContext';
import { useAuth } from '../../../contexts/AuthContext';

const Avatar = styled(MuiAvatar)(({ theme }) => ({
  width: 28,
  height: 28,
  backgroundColor: (theme.vars || theme).palette.background.paper,
  color: (theme.vars || theme).palette.text.secondary,
  border: `1px solid ${(theme.vars || theme).palette.divider}`,
}));

const ListItemAvatar = styled(MuiListItemAvatar)({
  minWidth: 0,
  marginRight: 12,
});

export default function SelectContent() {
  const { shop, loading, ownedShops, shopsLoading, refreshOwnedShops, selectOwnedShop } = useShop();
  const { user, logout } = useAuth();
  const [company, setCompany] = React.useState('');

  React.useEffect(() => {
    if (shop) {
      setCompany(shop.id.toString());
    }
  }, [shop]);

  React.useEffect(() => {
    if (!loading && !shop && user) {
      void refreshOwnedShops();
    }
  }, [loading, shop, user, refreshOwnedShops]);

  const handleChange = (event: SelectChangeEvent) => {
    const nextShopId = Number(event.target.value as string);
    setCompany(String(nextShopId));
    selectOwnedShop(nextShopId);
  };

  const resolveShopLogoSrc = () => {
    if (!shop?.id || !shop?.logo_url) return undefined;
    return `/api/shops/${shop.id}/logo`;
  };

  return (
    <Box
      sx={{
        width: '100%',
        bgcolor: 'var(--owner-glass-bg)',
        backdropFilter: 'blur(18px)',
        borderRadius: 3,
        boxShadow: 'var(--owner-glass-shadow)',
        border: '1px solid var(--owner-glass-border)',
        p: 1.25,
      }}
    >
      <Stack spacing={1.25}>
        <Stack direction="row" spacing={1.25} alignItems="center">
          <Avatar alt={user?.username || shop?.name || 'Owner'} src={resolveShopLogoSrc()} sx={{ width: 36, height: 36 }}>
            {user ? <PersonRoundedIcon sx={{ fontSize: '1rem' }} /> : <DevicesRoundedIcon sx={{ fontSize: '1rem' }} />}
          </Avatar>
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="body2" sx={{ fontWeight: 700 }} noWrap>
              {user?.username || 'Shop Owner'}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap>
              {user?.email || shop?.name || 'No shop selected'}
            </Typography>
          </Box>
        </Stack>

        <Divider />

        <Box>
          <Typography variant="overline" sx={{ color: 'text.secondary', fontWeight: 700, px: 0.25 }}>
            Active Shop
          </Typography>
          <Select
            labelId="company-select"
            id="company-simple-select"
            value={company}
            onChange={handleChange}
            displayEmpty
            inputProps={{ 'aria-label': 'Select company' }}
            fullWidth
            size="small"
            sx={{
              mt: 0.5,
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: 'var(--owner-glass-border)',
              },
              [`& .${selectClasses.select}`]: {
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
                pl: 1,
              },
            }}
          >
            <ListSubheader sx={{ pt: 0 }}>My Shops</ListSubheader>
            {ownedShops.map((ownedShop) => (
              <MenuItem key={ownedShop.id} value={ownedShop.id.toString()}>
                <ListItemAvatar>
                  <Avatar alt={ownedShop.name} sx={{ width: 30, height: 30 }}>
                    <DevicesRoundedIcon sx={{ fontSize: '0.95rem' }} />
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={ownedShop.name}
                  primaryTypographyProps={{ variant: 'body2', fontWeight: 600, noWrap: true }}
                />
              </MenuItem>
            ))}
            {!shop && !loading && ownedShops.length === 0 && (
              <MenuItem value="">
                <ListItemText primary="No Shop Selected" />
              </MenuItem>
            )}
          </Select>
        </Box>

        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            fullWidth
            size="small"
            onClick={() => void refreshOwnedShops()}
            disabled={shopsLoading}
            startIcon={<AutorenewRoundedIcon />}
          >
            Refresh
          </Button>
          <Button
            variant="outlined"
            color="inherit"
            fullWidth
            size="small"
            onClick={logout}
            startIcon={<LogoutRoundedIcon />}
          >
            Logout
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}
