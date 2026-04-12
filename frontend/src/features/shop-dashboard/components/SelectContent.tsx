import * as React from 'react';
import MuiAvatar from '@mui/material/Avatar';
import MuiListItemAvatar from '@mui/material/ListItemAvatar';
import MenuItem from '@mui/material/MenuItem';
import ListItemText from '@mui/material/ListItemText';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListSubheader from '@mui/material/ListSubheader';
import Select, { SelectChangeEvent, selectClasses } from '@mui/material/Select';
import Divider from '@mui/material/Divider';
import { styled } from '@mui/material/styles';
import AddRoundedIcon from '@mui/icons-material/AddRounded';
import DevicesRoundedIcon from '@mui/icons-material/DevicesRounded';
import SmartphoneRoundedIcon from '@mui/icons-material/SmartphoneRounded';
import ConstructionRoundedIcon from '@mui/icons-material/ConstructionRounded';
import { useShop } from '../../../contexts/ShopContext';

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
  const { shop, loading } = useShop();
  // Map shop to the select value, or empty string if not loaded
  const [company, setCompany] = React.useState('');

  React.useEffect(() => {
    if (shop) {
      setCompany(shop.id.toString());
    }
  }, [shop]);

  const handleChange = (event: SelectChangeEvent) => {
    setCompany(event.target.value as string);
  };

  const resolveShopLogoSrc = () => {
    if (!shop?.id || !shop?.logo_url) return undefined;
    return `/api/shops/${shop.id}/logo`;
  };

  return (
    <Select
      labelId="company-select"
      id="company-simple-select"
      value={company}
      onChange={handleChange}
      displayEmpty
      inputProps={{ 'aria-label': 'Select company' }}
      fullWidth
      sx={{
        maxHeight: 64,
        width: 236,
        bgcolor: 'var(--owner-glass-bg)',
        backdropFilter: 'blur(18px)',
        borderRadius: 3,
        boxShadow: 'var(--owner-glass-shadow)',
        '&.MuiList-root': {
          p: '8px',
        },
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
      {shop && (
        <MenuItem value={shop.id.toString()}>
          <ListItemAvatar>
            <Avatar alt={shop.name} src={resolveShopLogoSrc()} sx={{ width: 34, height: 34 }}>
              <DevicesRoundedIcon sx={{ fontSize: '1rem' }} />
            </Avatar>
          </ListItemAvatar>
          <ListItemText
            primary={shop.name}
            secondary="Shop Dashboard"
            primaryTypographyProps={{ variant: 'caption', fontWeight: 600, noWrap: true }}
            secondaryTypographyProps={{ variant: 'caption', fontSize: '0.7rem' }}
          />
        </MenuItem>
      )}
      {!shop && !loading && (
        <MenuItem value="">
          <ListItemText primary="No Shop Selected" />
        </MenuItem>
      )}

      <Divider sx={{ mx: -1 }} />
      <MenuItem value="add-new">
        <ListItemIcon>
          <AddRoundedIcon />
        </ListItemIcon>
        <ListItemText primary="Add new shop" secondary="Coming soon" />
      </MenuItem>
    </Select>
  );
}
