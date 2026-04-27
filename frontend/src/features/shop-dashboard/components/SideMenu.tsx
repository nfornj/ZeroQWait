// RESTYLED: Perplexity-style
import { styled } from '@mui/material/styles';
import MuiDrawer, { drawerClasses } from '@mui/material/Drawer';
import Box from '@mui/material/Box';
import SelectContent from './SelectContent';
import MenuContent from './MenuContent';
import CardAlert from './CardAlert';
import OwnerAccountPanel from './OwnerAccountPanel';

const drawerWidth = 240;

const Drawer = styled(MuiDrawer)({
  width: drawerWidth,
  flexShrink: 0,
  boxSizing: 'border-box',
  mt: 10,
  [`& .${drawerClasses.paper}`]: {
    width: drawerWidth,
    boxSizing: 'border-box',
  },
});

export default function SideMenu() {
  return (
    <Drawer
      variant="permanent"
      sx={{
        display: { xs: 'none', md: 'block' },
        [`& .${drawerClasses.paper}`]: {
          backgroundColor: 'background.paper',
          backdropFilter: 'none',
          borderRight: '1px solid',
          borderColor: 'divider',
          boxShadow: 'none',
        },
      }}
    >
      <Box
        sx={{
          overflow: 'auto',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          mt: 'calc(var(--template-frame-height, 0px) + 4px)',
        }}
      >
        <Box sx={{ p: 1.25, pb: 0 }}>
          <SelectContent />
        </Box>
        <MenuContent />
        <CardAlert />
        <Box sx={{ p: 1.25, pt: 0, mt: 'auto' }}>
          <OwnerAccountPanel />
        </Box>
      </Box>
    </Drawer>
  );
}
