import React, { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
  AppBar,
  Box,
  Toolbar,
  IconButton,
  Typography,
  Menu,
  Container,
  Avatar,
  Button,
  Tooltip,
  MenuItem,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import ContentCutIcon from "@mui/icons-material/ContentCut";
import SearchIcon from "@mui/icons-material/Search";
import FavoriteIcon from "@mui/icons-material/Favorite";
import PersonIcon from "@mui/icons-material/Person";
import { useAuth } from "../contexts/AuthContext";

const pages = [
  { title: "Home", path: "/" },
  { title: "Search", path: "/search" },
];

const Navbar = () => {
  const [anchorElNav, setAnchorElNav] = useState<null | HTMLElement>(null);
  const [anchorElUser, setAnchorElUser] = useState<null | HTMLElement>(null);
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const handleOpenNavMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorElNav(event.currentTarget);
  };

  const handleOpenUserMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorElUser(event.currentTarget);
  };

  const handleCloseNavMenu = () => {
    setAnchorElNav(null);
  };

  const handleCloseUserMenu = () => {
    setAnchorElUser(null);
  };

  const handleLogout = () => {
    logout();
    handleCloseUserMenu();
    navigate("/");
  };

  return (
    <AppBar position="static" elevation={0} sx={{ borderBottom: '1px solid #EBEBEB' }}>
      <Container maxWidth="xl">
        <Toolbar
          disableGutters
          sx={{
            minHeight: { xs: 64, md: 80 },
            py: { xs: 1, md: 1.5 }
          }}
        >
          {/* Logo */}
          <Box
            component={RouterLink}
            to="/"
            sx={{
              display: 'flex',
              alignItems: 'center',
              textDecoration: 'none',
              color: 'inherit',
              '&:hover': { opacity: 0.8 }
            }}
          >
            <ContentCutIcon
              sx={{
                fontSize: { xs: 28, md: 32 },
                color: 'primary.main',
                mr: 1.5
              }}
            />
            <Typography
              variant="h5"
              sx={{
                fontWeight: 700,
                fontSize: { xs: '1.5rem', md: '1.75rem' },
                color: 'text.primary',
                letterSpacing: '-0.02em'
              }}
            >
              Nowait
            </Typography>
          </Box>

          <Box sx={{ flexGrow: 1 }} />

          {/* Desktop Navigation */}
          {!isMobile && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {/* Only show customer-facing features for non-employees */}
              {user?.role !== 'employee' && (
                <>
                  <Button
                    component={RouterLink}
                    to="/search"
                    startIcon={<SearchIcon />}
                    sx={{
                      color: 'text.primary',
                      fontWeight: 500,
                      px: 2,
                      py: 1.5,
                      borderRadius: '50px',
                      '&:hover': {
                        backgroundColor: 'rgba(0, 0, 0, 0.04)'
                      }
                    }}
                  >
                    Search
                  </Button>
                  <Button
                    component={RouterLink}
                    to="/pricing"
                    sx={{
                      color: 'text.primary',
                      fontWeight: 500,
                      px: 2,
                      py: 1.5,
                      borderRadius: '50px',
                      '&:hover': {
                        backgroundColor: 'rgba(0, 0, 0, 0.04)'
                      }
                    }}
                  >
                    Pricing
                  </Button>

                  {isAuthenticated && (
                    <Button
                      component={RouterLink}
                      to="/favorites"
                      startIcon={<FavoriteIcon />}
                      sx={{
                        color: 'text.primary',
                        fontWeight: 500,
                        px: 2,
                        py: 1.5,
                        borderRadius: '50px',
                        '&:hover': {
                          backgroundColor: 'rgba(0, 0, 0, 0.04)'
                        }
                      }}
                    >
                      Favorites
                    </Button>
                  )}
                </>
              )}

              {/* User Menu */}
              <Box sx={{ ml: 2 }}>
                {isAuthenticated ? (
                  <>
                    <Tooltip title="Account menu">
                      <IconButton
                        onClick={handleOpenUserMenu}
                        sx={{
                          p: 0.5,
                          border: '1px solid #DDDDDD',
                          borderRadius: '50px',
                          px: 1.5,
                          '&:hover': {
                            boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.18)',
                          }
                        }}
                      >
                        <PersonIcon sx={{ fontSize: 18, mr: 1 }} />
                        <Avatar
                          alt={user?.username || "User"}
                          sx={{
                            width: 24,
                            height: 24,
                            fontSize: '0.75rem',
                            bgcolor: 'primary.main'
                          }}
                        >
                          {user?.username?.charAt(0).toUpperCase() || 'U'}
                        </Avatar>
                      </IconButton>
                    </Tooltip>
                    <Menu
                      anchorEl={anchorElUser}
                      open={Boolean(anchorElUser)}
                      onClose={handleCloseUserMenu}
                      sx={{ mt: 1 }}
                      PaperProps={{
                        sx: {
                          borderRadius: 2,
                          boxShadow: '0px 4px 16px rgba(0, 0, 0, 0.1)',
                          border: '1px solid #EBEBEB'
                        }
                      }}
                    >
                      <MenuItem
                        onClick={handleLogout}
                        sx={{
                          px: 3,
                          py: 1.5,
                          fontSize: '0.875rem'
                        }}
                      >
                        Logout
                      </MenuItem>
                    </Menu>
                  </>
                ) : (
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      component={RouterLink}
                      to="/login"
                      sx={{
                        color: 'text.primary',
                        fontWeight: 500,
                        px: 2,
                        py: 1.5,
                        borderRadius: '50px',
                        '&:hover': {
                          backgroundColor: 'rgba(0, 0, 0, 0.04)'
                        }
                      }}
                    >
                      Log in
                    </Button>
                    <Button
                      component={RouterLink}
                      to="/pricing"
                      variant="contained"
                      sx={{
                        fontWeight: 600,
                        px: 3,
                        py: 1.5,
                        borderRadius: '50px',
                        background: 'linear-gradient(135deg, #FF5A5F 0%, #FF385C 100%)',
                        '&:hover': {
                          background: 'linear-gradient(135deg, #FF385C 0%, #E00007 100%)',
                        }
                      }}
                    >
                      Sign up
                    </Button>
                  </Box>
                )}
              </Box>
            </Box>
          )}

          {/* Mobile Menu */}
          {isMobile && (
            <IconButton
              onClick={handleOpenNavMenu}
              sx={{
                ml: 2,
                p: 1,
                border: '1px solid #DDDDDD',
                borderRadius: 1
              }}
            >
              <MenuIcon />
            </IconButton>
          )}

          <Menu
            anchorEl={anchorElNav}
            open={Boolean(anchorElNav)}
            onClose={handleCloseNavMenu}
            sx={{ display: { xs: 'block', md: 'none' } }}
            PaperProps={{
              sx: {
                borderRadius: 2,
                boxShadow: '0px 4px 16px rgba(0, 0, 0, 0.1)',
                border: '1px solid #EBEBEB',
                minWidth: 200
              }
            }}
          >
            {/* Only show customer-facing features for non-employees */}
            {user?.role !== 'employee' && (
              <>
                <MenuItem
                  component={RouterLink}
                  to="/search"
                  onClick={handleCloseNavMenu}
                  sx={{ px: 3, py: 1.5 }}
                >
                  <SearchIcon sx={{ mr: 2, fontSize: 18 }} />
                  Search
                </MenuItem>
                <MenuItem
                  component={RouterLink}
                  to="/pricing"
                  onClick={handleCloseNavMenu}
                  sx={{ px: 3, py: 1.5 }}
                >
                  Pricing
                </MenuItem>
                {isAuthenticated && (
                  <MenuItem
                    component={RouterLink}
                    to="/favorites"
                    onClick={handleCloseNavMenu}
                    sx={{ px: 3, py: 1.5 }}
                  >
                    <FavoriteIcon sx={{ mr: 2, fontSize: 18 }} />
                    Favorites
                  </MenuItem>
                )}
              </>
            )}
            {!isAuthenticated && (
              <>
                <MenuItem
                  component={RouterLink}
                  to="/login"
                  onClick={handleCloseNavMenu}
                  sx={{ px: 3, py: 1.5 }}
                >
                  Log in
                </MenuItem>
                <MenuItem
                  component={RouterLink}
                  to="/pricing"
                  onClick={handleCloseNavMenu}
                  sx={{ px: 3, py: 1.5 }}
                >
                  Sign up
                </MenuItem>
              </>
            )}
            {isAuthenticated && (
              <MenuItem
                onClick={handleLogout}
                sx={{ px: 3, py: 1.5, borderTop: '1px solid #EBEBEB' }}
              >
                Logout
              </MenuItem>
            )}
          </Menu>
        </Toolbar>
      </Container>
    </AppBar>
  );
};

export default Navbar;
