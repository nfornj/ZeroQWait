import React, { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import {
    Box,
    Drawer,
    AppBar,
    Toolbar,
    List,
    Typography,
    Divider,
    IconButton,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Avatar,
    Menu,
    MenuItem,
    useTheme,
    useMediaQuery,
    CircularProgress,
    Alert
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import DashboardIcon from '@mui/icons-material/Dashboard';
import QueueIcon from '@mui/icons-material/Queue';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import SettingsIcon from '@mui/icons-material/Settings';
import PeopleIcon from '@mui/icons-material/People';
import LogoutIcon from '@mui/icons-material/Logout';
import StoreIcon from '@mui/icons-material/Store';
import LaunchIcon from '@mui/icons-material/Launch';
import { useAuth } from '../contexts/AuthContext';
import { useShop } from '../contexts/ShopContext';

const drawerWidth = 240;
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

interface Shop {
    id: number;
    name: string;
    logo_url?: string;
    primary_color?: string;
    secondary_color?: string;
    city?: string;
    state?: string;
    shop_type?: string;
}

const ShopLayout: React.FC = () => {
    const { user, logout } = useAuth();
    const { shop, loading, error } = useShop();
    const navigate = useNavigate();
    const location = useLocation();
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));
    const [mobileOpen, setMobileOpen] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const collapsedWidth = 72;
    const expandedWidth = 240;

    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    const menuItems = [
        { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
        { text: 'Queues', icon: <QueueIcon />, path: '/queues' },
        { text: 'Team', icon: <PeopleIcon />, path: '/employees' },
        { text: 'Analytics', icon: <AnalyticsIcon />, path: '/analytics' },
        { text: 'Settings', icon: <SettingsIcon />, path: '/settings' },
    ];

    const currentDrawerWidth = sidebarCollapsed ? collapsedWidth : expandedWidth;

    const drawer = (
        <div>
            <Toolbar sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', px: sidebarCollapsed ? 1 : 2, py: 2, minHeight: 64 }}>
                {shop?.logo_url ? (
                    <Avatar 
                        src={shop.logo_url} 
                        alt={shop.name} 
                        sx={{ 
                            width: sidebarCollapsed ? 36 : 48, 
                            height: sidebarCollapsed ? 36 : 48, 
                            transition: 'all 0.3s ease'
                        }} 
                    />
                ) : (
                    <Avatar sx={{ 
                        width: sidebarCollapsed ? 36 : 48, 
                        height: sidebarCollapsed ? 36 : 48, 
                        bgcolor: shop?.primary_color || 'primary.main', 
                        fontSize: '1.2rem',
                        transition: 'all 0.3s ease'
                    }}>
                        {shop?.name?.charAt(0).toUpperCase() || <StoreIcon />}
                    </Avatar>
                )}
            </Toolbar>
            <Divider />
            <List sx={{ px: sidebarCollapsed ? 0.5 : 1 }}>
                {menuItems.map((item) => (
                    <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
                        <ListItemButton
                            selected={location.pathname.includes(item.path)}
                            onClick={() => {
                                if (item.path === '/dashboard') navigate('/dashboard');
                                else navigate(item.path);
                            }}
                            sx={{
                                borderRadius: 2,
                                justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                                px: sidebarCollapsed ? 1 : 2,
                                minHeight: 48
                            }}
                        >
                            <ListItemIcon sx={{ 
                                color: location.pathname.includes(item.path) ? (shop?.primary_color || 'primary.main') : 'inherit',
                                minWidth: sidebarCollapsed ? 'auto' : 40,
                                justifyContent: 'center'
                            }}>
                                {item.icon}
                            </ListItemIcon>
                            {!sidebarCollapsed && <ListItemText primary={item.text} />}
                        </ListItemButton>
                    </ListItem>
                ))}
            </List>
            <Divider />
            <List sx={{ px: sidebarCollapsed ? 0.5 : 1 }}>
                <ListItem disablePadding>
                    <ListItemButton 
                        onClick={() => window.open('/s/my-shop', '_blank')}
                        sx={{
                            borderRadius: 2,
                            justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                            px: sidebarCollapsed ? 1 : 2,
                            minHeight: 48
                        }}
                    >
                        <ListItemIcon sx={{ minWidth: sidebarCollapsed ? 'auto' : 40, justifyContent: 'center' }}>
                            <LaunchIcon />
                        </ListItemIcon>
                        {!sidebarCollapsed && <ListItemText primary="View Public Site" />}
                    </ListItemButton>
                </ListItem>
                {!isMobile && (
                    <ListItem disablePadding>
                        <ListItemButton 
                            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                            sx={{
                                borderRadius: 2,
                                justifyContent: 'center',
                                px: 1,
                                minHeight: 48,
                                mt: 1
                            }}
                        >
                            <ListItemIcon sx={{ minWidth: 'auto', justifyContent: 'center' }}>
                                {sidebarCollapsed ? <MenuIcon /> : <MenuIcon sx={{ transform: 'rotate(180deg)' }} />}
                            </ListItemIcon>
                        </ListItemButton>
                    </ListItem>
                )}
            </List>
        </div>
    );

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
            <AppBar
                position="fixed"
                sx={{
                    width: '100%',
                    bgcolor: shop?.primary_color || '#1976d2',
                    color: 'white',
                    boxShadow: 2,
                    zIndex: (theme) => theme.zIndex.drawer + 1
                }}
            >
                <Toolbar>
                    <IconButton
                        color="inherit"
                        aria-label="open drawer"
                        edge="start"
                        onClick={handleDrawerToggle}
                        sx={{ mr: 2, display: { md: 'none' } }}
                    >
                        <MenuIcon />
                    </IconButton>
                    
                    {/* Shop Logo and Name */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                        {shop?.logo_url ? (
                            <Avatar 
                                src={shop.logo_url} 
                                alt={shop.name}
                                sx={{ width: 40, height: 40 }}
                            />
                        ) : (
                            <Avatar 
                                sx={{ 
                                    width: 40, 
                                    height: 40, 
                                    bgcolor: 'rgba(255,255,255,0.2)',
                                    fontWeight: 700
                                }}
                            >
                                <StoreIcon />
                            </Avatar>
                        )}
                        <Box sx={{ display: { xs: 'none', sm: 'block' } }}>
                            <Typography variant="h6" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
                                {shop?.name || 'Shop Portal'}
                            </Typography>
                            <Typography variant="caption" sx={{ opacity: 0.9, fontSize: '0.7rem' }}>
                                {shop?.city && shop?.state ? `${shop.city}, ${shop.state}` : 'Business Dashboard'}
                            </Typography>
                        </Box>
                    </Box>
                    
                    <Box sx={{ flexGrow: 1 }} />
                    
                    {/* User Menu */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Box sx={{ display: { xs: 'none', md: 'block' }, textAlign: 'right' }}>
                            <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.875rem' }}>
                                {user?.username}
                            </Typography>
                            <Typography variant="caption" sx={{ opacity: 0.8, fontSize: '0.7rem' }}>
                                {user?.email}
                            </Typography>
                        </Box>
                        <IconButton
                            size="large"
                            aria-label="account of current user"
                            aria-controls="menu-appbar"
                            aria-haspopup="true"
                            onClick={handleMenu}
                            color="inherit"
                        >
                            <Avatar sx={{ width: 36, height: 36, bgcolor: 'rgba(255,255,255,0.2)', fontWeight: 600 }}>
                                {user?.username?.charAt(0).toUpperCase()}
                            </Avatar>
                        </IconButton>
                        <Menu
                            id="menu-appbar"
                            anchorEl={anchorEl}
                            anchorOrigin={{
                                vertical: 'bottom',
                                horizontal: 'right',
                            }}
                            keepMounted
                            transformOrigin={{
                                vertical: 'top',
                                horizontal: 'right',
                            }}
                            open={Boolean(anchorEl)}
                            onClose={handleClose}
                        >
                            <MenuItem onClick={handleLogout}>
                                <ListItemIcon>
                                    <LogoutIcon fontSize="small" />
                                </ListItemIcon>
                                Logout
                            </MenuItem>
                        </Menu>
                    </Box>
                </Toolbar>
            </AppBar>
            <Box sx={{ display: 'flex', flexGrow: 1, mt: 8 }}>
                <Box
                    component="nav"
                    sx={{ width: { md: currentDrawerWidth }, flexShrink: { md: 0 } }}
                    aria-label="mailbox folders"
                >
                    <Drawer
                        variant="temporary"
                        open={mobileOpen}
                        onClose={handleDrawerToggle}
                        ModalProps={{
                            keepMounted: true,
                        }}
                        sx={{
                            display: { xs: 'block', md: 'none' },
                            '& .MuiDrawer-paper': { boxSizing: 'border-box', width: expandedWidth, mt: 8 },
                        }}
                    >
                        {drawer}
                    </Drawer>
                    <Drawer
                        variant="permanent"
                        sx={{
                            display: { xs: 'none', md: 'block' },
                            '& .MuiDrawer-paper': { 
                                boxSizing: 'border-box', 
                                width: currentDrawerWidth,
                                transition: 'width 0.3s ease',
                                overflowX: 'hidden',
                                mt: 8,
                                height: 'calc(100vh - 64px)'
                            },
                        }}
                        open
                    >
                        {drawer}
                    </Drawer>
                </Box>
                <Box
                    component="main"
                    sx={{ 
                        flexGrow: 1, 
                        p: 3,
                        width: { md: `calc(100% - ${currentDrawerWidth}px)` },
                        transition: 'all 0.3s ease',
                        overflow: 'auto'
                    }}
                >
                    <Outlet />
                </Box>
            </Box>
        </Box>
    );
};

export default ShopLayout;
