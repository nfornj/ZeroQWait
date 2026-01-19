import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
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
    Tooltip
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
import DarkModeIcon from '@mui/icons-material/DarkMode';
import LightModeIcon from '@mui/icons-material/LightMode';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

import { useAuth } from '../contexts/AuthContext';
import { useShop } from '../contexts/ShopContext';
import { useThemeContext } from '../contexts/ThemeContext';

const collapsedWidth = 72;
const expandedWidth = 260; // Wider for better aesthetics

const ShopLayout: React.FC = () => {
    const { user, logout } = useAuth();
    const { shop } = useShop();
    const navigate = useNavigate();
    const location = useLocation();
    const theme = useTheme();
    const { mode, toggleMode } = useThemeContext();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));

    const [mobileOpen, setMobileOpen] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

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

    const drawerContent = (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            {/* Sidebar Header / Branding */}
            <Box sx={{
                p: 2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: sidebarCollapsed ? 'center' : 'space-between',
                minHeight: 64
            }}>
                {(!sidebarCollapsed) && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, overflow: 'hidden' }}>
                        {shop?.logo_url ? (
                            <Avatar src={shop.logo_url} alt={shop.name} variant="rounded" sx={{ width: 32, height: 32 }} />
                        ) : (
                            <Avatar variant="rounded" sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: '1rem' }}>
                                {shop?.name?.charAt(0).toUpperCase() || <StoreIcon fontSize="small" />}
                            </Avatar>
                        )}
                        <Typography variant="subtitle1" fontWeight="bold" noWrap>
                            {shop?.name || 'ZeroQwait'}
                        </Typography>
                    </Box>
                )}
                {/* Logo only when collapsed */}
                {(sidebarCollapsed) && (
                    <Avatar variant="rounded" sx={{ width: 32, height: 32, bgcolor: 'primary.main' }}>
                        {shop?.name?.charAt(0).toUpperCase() || <StoreIcon fontSize="small" />}
                    </Avatar>
                )}

                {/* Collapse Toggle (Desktop only) */}
                {!isMobile && !sidebarCollapsed && (
                    <IconButton size="small" onClick={() => setSidebarCollapsed(true)}>
                        <ChevronLeftIcon />
                    </IconButton>
                )}
            </Box>

            <Divider sx={{ mb: 2 }} />

            {/* Navigation Links */}
            <List sx={{ px: 1.5, flexGrow: 1 }}>
                {menuItems.map((item) => (
                    <Tooltip key={item.text} title={sidebarCollapsed ? item.text : ''} placement="right">
                        <ListItem disablePadding sx={{ mb: 1 }}>
                            <ListItemButton
                                selected={location.pathname.includes(item.path)}
                                onClick={() => {
                                    navigate(item.path === '/dashboard' ? '/dashboard' : item.path);
                                    if (isMobile) setMobileOpen(false);
                                }}
                                sx={{
                                    justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                                    px: sidebarCollapsed ? 1 : 2,
                                    minHeight: 48,
                                    bgcolor: location.pathname.includes(item.path)
                                        ? (theme.palette.mode === 'light' ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.1)')
                                        : 'transparent',
                                    color: location.pathname.includes(item.path) ? 'primary.main' : 'text.secondary',
                                    '&.Mui-selected': {
                                        bgcolor: 'primary.main',
                                        color: 'primary.contrastText',
                                        '&:hover': {
                                            bgcolor: 'primary.dark',
                                        },
                                        '& .MuiListItemIcon-root': {
                                            color: 'inherit',
                                        }
                                    },
                                    '&:hover': {
                                        bgcolor: theme.palette.mode === 'light' ? 'rgba(0,0,0,0.03)' : 'rgba(255,255,255,0.03)',
                                    }
                                }}
                            >
                                <ListItemIcon sx={{
                                    minWidth: sidebarCollapsed ? 'auto' : 40,
                                    justifyContent: 'center',
                                    color: 'inherit'
                                }}>
                                    {item.icon}
                                </ListItemIcon>
                                {!sidebarCollapsed && (
                                    <ListItemText
                                        primary={item.text}
                                        primaryTypographyProps={{ fontWeight: 500 }}
                                    />
                                )}
                            </ListItemButton>
                        </ListItem>
                    </Tooltip>
                ))}
            </List>

            <Divider />

            {/* Bottom Actions */}
            <Box sx={{ p: 1.5 }}>
                {/* Public Site Link */}
                <Tooltip title={sidebarCollapsed ? "View Public Site" : ""} placement="right">
                    <ListItemButton
                        onClick={() => window.open('/s/my-shop', '_blank')}
                        sx={{
                            justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                            px: sidebarCollapsed ? 1 : 2,
                            minHeight: 48,
                            mb: 1,
                            color: 'text.secondary'
                        }}
                    >
                        <ListItemIcon sx={{ minWidth: sidebarCollapsed ? 'auto' : 40, justifyContent: 'center', color: 'inherit' }}>
                            <LaunchIcon />
                        </ListItemIcon>
                        {!sidebarCollapsed && <ListItemText primary="Public Site" />}
                    </ListItemButton>
                </Tooltip>

                {/* Theme Toggle */}
                <Tooltip title={sidebarCollapsed ? `Switch to ${mode === 'light' ? 'Dark' : 'Light'} Mode` : ""} placement="right">
                    <ListItemButton
                        onClick={toggleMode}
                        sx={{
                            justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                            px: sidebarCollapsed ? 1 : 2,
                            minHeight: 48,
                            color: 'text.secondary'
                        }}
                    >
                        <ListItemIcon sx={{ minWidth: sidebarCollapsed ? 'auto' : 40, justifyContent: 'center', color: 'inherit' }}>
                            {mode === 'light' ? <DarkModeIcon /> : <LightModeIcon />}
                        </ListItemIcon>
                        {!sidebarCollapsed && <ListItemText primary={`${mode === 'light' ? 'Dark' : 'Light'} Mode`} />}
                    </ListItemButton>
                </Tooltip>

                {/* Footer / Copyright */}
                {!sidebarCollapsed && (
                    <Box sx={{ mt: 2, textAlign: 'center', opacity: 0.5 }}>
                        <Typography variant="caption" display="block">
                            Built by ZeroQwait
                        </Typography>
                    </Box>
                )}
                {/* Expand Button for collapsed state */}
                {!isMobile && sidebarCollapsed && (
                    <IconButton onClick={() => setSidebarCollapsed(false)} sx={{ mt: 1, mx: 'auto', display: 'flex' }}>
                        <ChevronRightIcon />
                    </IconButton>
                )}
            </Box>
        </Box>
    );

    return (
        <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
            {/* Top Bar for Mobile */}
            <AppBar
                position="fixed"
                color="inherit"
                elevation={0}
                sx={{
                    width: { md: `calc(100% - ${currentDrawerWidth}px)` },
                    ml: { md: `${currentDrawerWidth}px` },
                    bgcolor: 'background.paper',
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                    display: { md: 'none' } // Hide on desktop if we want a clean look, or keep it for the title
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
                    <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
                        {shop?.name || 'Dashboard'}
                    </Typography>

                    <Avatar
                        src={user?.profile_photo_url}
                        alt={user?.username}
                        onClick={handleMenu}
                        sx={{ cursor: 'pointer', width: 32, height: 32 }}
                    />
                </Toolbar>
            </AppBar>

            {/* User Menu (Absolute positioned for Desktop) */}
            <Box
                sx={{
                    position: 'fixed',
                    top: 16,
                    right: 24,
                    zIndex: 1200,
                    display: { xs: 'none', md: 'flex' },
                    alignItems: 'center',
                    gap: 2
                }}
            >
                {/* We could put global search or notifications here */}

                {/* User Profile */}
                <Box
                    onClick={handleMenu}
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1.5,
                        cursor: 'pointer',
                        bgcolor: 'background.paper',
                        py: 0.5,
                        px: 1.5,
                        borderRadius: '50px', // Explicit pill for profile
                        boxShadow: '0px 2px 8px rgba(0,0,0,0.05)',
                        border: '1px solid',
                        borderColor: 'divider',
                        transition: 'all 0.2s',
                        '&:hover': {
                            bgcolor: 'action.hover',
                            boxShadow: '0px 4px 12px rgba(0,0,0,0.1)',
                        }
                    }}
                >
                    <Avatar
                        src={user?.profile_photo_url}
                        sx={{ width: 32, height: 32, bgcolor: 'secondary.main', fontSize: '0.875rem' }}
                    >
                        {user?.username?.charAt(0).toUpperCase()}
                    </Avatar>
                    <Typography variant="body2" fontWeight={600} color="text.primary">
                        {user?.username}
                    </Typography>
                </Box>

                <Menu
                    id="menu-appbar"
                    anchorEl={anchorEl}
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                    keepMounted
                    transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                    open={Boolean(anchorEl)}
                    onClose={handleClose}
                    PaperProps={{
                        elevation: 0,
                        sx: {
                            overflow: 'visible',
                            filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
                            mt: 1.5,
                            '&:before': {
                                content: '""',
                                display: 'block',
                                position: 'absolute',
                                top: 0,
                                right: 14,
                                width: 10,
                                height: 10,
                                bgcolor: 'background.paper',
                                transform: 'translateY(-50%) rotate(45deg)',
                                zIndex: 0,
                            },
                        },
                    }}
                >
                    <MenuItem onClick={handleLogout}>
                        <ListItemIcon>
                            <LogoutIcon fontSize="small" />
                        </ListItemIcon>
                        Logout
                    </MenuItem>
                </Menu>
            </Box>


            <Box
                component="nav"
                sx={{ width: { md: currentDrawerWidth }, flexShrink: { md: 0 } }}
            >
                {/* Mobile Drawer */}
                <Drawer
                    variant="temporary"
                    open={mobileOpen}
                    onClose={handleDrawerToggle}
                    ModalProps={{ keepMounted: true }}
                    sx={{
                        display: { xs: 'block', md: 'none' },
                        '& .MuiDrawer-paper': { boxSizing: 'border-box', width: expandedWidth },
                    }}
                >
                    {drawerContent}
                </Drawer>

                {/* Desktop Sidebar */}
                <Drawer
                    variant="permanent"
                    sx={{
                        display: { xs: 'none', md: 'block' },
                        '& .MuiDrawer-paper': {
                            boxSizing: 'border-box',
                            width: currentDrawerWidth,
                            borderRight: '1px solid',
                            borderColor: 'divider',
                            bgcolor: 'background.paper',
                            transition: 'width 0.3s ease',
                            overflowX: 'hidden'
                        },
                    }}
                    open
                >
                    {drawerContent}
                </Drawer>
            </Box>

            {/* Main Content Area */}
            <Box
                component="main"
                sx={{
                    flexGrow: 1,
                    p: 3,
                    mt: { xs: 8, md: 0 },
                    width: { md: `calc(100% - ${currentDrawerWidth}px)` },
                    transition: 'all 0.3s ease',
                    overflow: 'auto'
                }}
            >
                {/* Add top padding on desktop to account for the absolute User Menu */}
                <Box sx={{ height: { xs: 0, md: 60 } }} />
                <Outlet />
            </Box>
        </Box>
    );
};

export default ShopLayout;
