import React, { useEffect } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
  Container,
  Typography,
  Box,
  Button,
  Card,
  CardContent,
  alpha,
  useTheme,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import LocationOnIcon from "@mui/icons-material/LocationOn";
import StarIcon from "@mui/icons-material/Star";
import ScheduleIcon from "@mui/icons-material/Schedule";
import VideocamIcon from "@mui/icons-material/Videocam";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import { useAuth } from "../../../contexts/AuthContext";

const HomePage: React.FC = () => {
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();

  // Redirect authenticated users based on their role
  useEffect(() => {
    console.log("[HomePage] Auth check", { isAuthenticated, user });
    if (isAuthenticated && user) {
      console.log("[HomePage] User role is", user.role);
      if (user.role === "shop_owner") {
        console.log("[HomePage] Redirecting shop_owner to /dashboard");
        navigate("/dashboard");
      } else if (user.role === "employee") {
        console.log("[HomePage] Redirecting employee to /employee-dashboard");
        navigate("/employee-dashboard");
      }
    }
  }, [isAuthenticated, user, navigate]);

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* Hero Section */}
      <Box
        sx={{
          background: 'linear-gradient(135deg, rgba(255, 90, 95, 0.1) 0%, rgba(0, 166, 153, 0.05) 100%)',
          pt: { xs: 6, md: 10 },
          pb: { xs: 8, md: 12 },
        }}
      >
        <Container maxWidth="lg">
          <Box sx={{ textAlign: 'center', maxWidth: '800px', mx: 'auto' }}>
            <Typography
              variant="h1"
              sx={{
                fontSize: { xs: '2.5rem', md: '3.5rem', lg: '4rem' },
                fontWeight: 700,
                mb: 3,
                background: 'linear-gradient(135deg, #FF5A5F 0%, #00A699 100%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                lineHeight: 1.1
              }}
            >
              Give your shop
              <br />an AI team
            </Typography>

            <Typography
              variant="h5"
              sx={{
                fontSize: { xs: '1.125rem', md: '1.25rem' },
                color: 'text.secondary',
                mb: 5,
                maxWidth: '600px',
                mx: 'auto',
                lineHeight: 1.5
              }}
            >
              ZeroQwait gives service businesses an AI Receptionist for customers and an
              owner-facing AI workspace for queue, booking, staffing, and daily operations.
            </Typography>

            <Box sx={{ mb: 6 }}>
              <Button
                variant="contained"
                size="large"
                component={RouterLink}
                to="/search"
                startIcon={<SearchIcon />}
                sx={{
                  fontSize: '1.125rem',
                  fontWeight: 600,
                  px: 4,
                  py: 2,
                  borderRadius: '50px',
                  background: 'linear-gradient(135deg, #FF5A5F 0%, #FF385C 100%)',
                  boxShadow: '0 8px 32px rgba(255, 90, 95, 0.3)',
                  '&:hover': {
                    background: 'linear-gradient(135deg, #FF385C 0%, #E00007 100%)',
                    boxShadow: '0 12px 40px rgba(255, 90, 95, 0.4)',
                    transform: 'translateY(-2px)'
                  },
                  transition: 'all 0.3s ease-in-out'
                }}
              >
                Explore Shops
              </Button>
            </Box>

            {/* Stats */}
            <Box display="flex" flexWrap="wrap" gap={4} sx={{ mt: 4 }}>
              <Box sx={{ flex: 1, minWidth: '250px' }}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h3" sx={{ fontWeight: 700, color: 'primary.main' }}>
                    AI
                  </Typography>
                  <Typography variant="body1" color="text.secondary">
                    Receptionist for customers
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ flex: 1, minWidth: '250px' }}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h3" sx={{ fontWeight: 700, color: 'secondary.main' }}>
                    Live
                  </Typography>
                  <Typography variant="body1" color="text.secondary">
                    Queue and appointment flows
                  </Typography>
                </Box>
              </Box>
              <Box sx={{ flex: 1, minWidth: '250px' }}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h3" sx={{ fontWeight: 700, color: 'primary.main' }}>
                    Owner
                  </Typography>
                  <Typography variant="body1" color="text.secondary">
                    Inbox, approvals, and analytics
                  </Typography>
                </Box>
              </Box>
            </Box>
          </Box>
        </Container>
      </Box>

      {/* Features Section */}
      <Box sx={{ py: { xs: 8, md: 12 } }}>
        <Container maxWidth="lg">
          <Box sx={{ textAlign: 'center', mb: 8 }}>
            <Typography
              variant="h2"
              sx={{
                fontSize: { xs: '2rem', md: '2.5rem' },
                fontWeight: 600,
                mb: 2,
                color: 'text.primary'
              }}
            >
              What ZeroQwait Does Today
            </Typography>
            <Typography
              variant="h6"
              sx={{
                color: 'text.secondary',
                maxWidth: '600px',
                mx: 'auto',
                fontWeight: 400
              }}
            >
              The current product already supports an AI receptionist experience for customers and an
              AI operating workspace for owners.
            </Typography>
          </Box>

          <Box display="flex" flexWrap="wrap" gap={4}>
            <Box sx={{ flex: 1, minWidth: '250px' }}>
              <Card
                elevation={0}
                sx={{
                  height: '100%',
                  textAlign: 'center',
                  p: 4,
                  border: '1px solid',
                  borderColor: 'divider',
                  transition: 'all 0.3s ease-in-out',
                  '&:hover': {
                    transform: 'translateY(-8px)',
                    boxShadow: theme.shadows[8]
                  }
                }}
              >
                <Box
                  sx={{
                    width: 80,
                    height: 80,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #FF5A5F 0%, #FF8A80 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mx: 'auto',
                    mb: 3
                  }}
                >
                  <LocationOnIcon sx={{ fontSize: 40, color: 'white' }} />
                </Box>
                <Typography variant="h5" sx={{ fontWeight: 600, mb: 2 }}>
                  Launch Your Shop Presence
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  Create your shop profile, publish a public page, and let customers find you,
                  ask questions, join the queue, or book appointments online.
                </Typography>
              </Card>
            </Box>

            <Box sx={{ flex: 1, minWidth: '250px' }}>
              <Card
                elevation={0}
                sx={{
                  height: '100%',
                  textAlign: 'center',
                  p: 4,
                  border: '1px solid',
                  borderColor: 'divider',
                  transition: 'all 0.3s ease-in-out',
                  '&:hover': {
                    transform: 'translateY(-8px)',
                    boxShadow: theme.shadows[8]
                  }
                }}
              >
                <Box
                  sx={{
                    width: 80,
                    height: 80,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #00A699 0%, #4DB6AC 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mx: 'auto',
                    mb: 3
                  }}
                >
                  <StarIcon sx={{ fontSize: 40, color: 'white' }} />
                </Box>
                <Typography variant="h5" sx={{ fontWeight: 600, mb: 2 }}>
                  Run Daily Operations
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  Owners can review queue status, analytics, approvals, appointments, and team updates
                  from one AI-powered workspace instead of jumping between tools.
                </Typography>
              </Card>
            </Box>

            <Box sx={{ flex: 1, minWidth: '250px' }}>
              <Card
                elevation={0}
                sx={{
                  height: '100%',
                  textAlign: 'center',
                  p: 4,
                  border: '1px solid',
                  borderColor: 'divider',
                  transition: 'all 0.3s ease-in-out',
                  '&:hover': {
                    transform: 'translateY(-8px)',
                    boxShadow: theme.shadows[8]
                  }
                }}
              >
                <Box
                  sx={{
                    width: 80,
                    height: 80,
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, #9C27B0 0%, #E1BEE7 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mx: 'auto',
                    mb: 3
                  }}
                >
                  <ScheduleIcon sx={{ fontSize: 40, color: 'white' }} />
                </Box>
                <Typography variant="h5" sx={{ fontWeight: 600, mb: 2 }}>
                  Let Customers Self-Serve
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  {isAuthenticated
                    ? "Customers can join queues, view live progress, and complete appointment booking flows from the browser."
                    : "Customers can discover shops, join queues, and book appointments online without downloading an app."
                  }
                </Typography>
              </Card>
            </Box>
          </Box>
        </Container>
      </Box>

      {/* AI Demo Section */}
      <Box sx={{ py: { xs: 8, md: 12 }, bgcolor: 'background.paper' }}>
        <Container maxWidth="lg">
          <Box display="flex" flexWrap="wrap" gap={6} alignItems="center">
            <Box sx={{ flex: 1, minWidth: '250px' }}>
              <Box
                sx={{
                  background: 'linear-gradient(135deg, #FF5A5F 0%, #00A699 100%)',
                  p: 4,
                  color: 'white',
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center'
                }}
              >
                <SmartToyIcon sx={{ fontSize: 60, mb: 2 }} />
                <Typography variant="h3" sx={{ fontWeight: 700, mb: 2 }}>
                  Experimental AI Camera Demo
                </Typography>
                <Typography variant="h6" sx={{ mb: 3, opacity: 0.9 }}>
                  This is an optional demo showing how ZeroQwait experiments with computer vision for
                  real-world queue sensing. It is separate from the core receptionist and owner-agent flows.
                </Typography>
                <Box sx={{ mb: 2 }}>
                  <Typography variant="body1" sx={{ mb: 1 }}>
                    ✓ Real-time person detection demo
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 1 }}>
                    ✓ Automatic people counting experiment
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 1 }}>
                    ✓ Works with a phone camera
                  </Typography>
                  <Typography variant="body1">
                    ✓ Useful for testing AI-assisted queue sensing
                  </Typography>
                </Box>
              </Box>
            </Box>

            <Box sx={{ flex: 1, minWidth: '250px' }}>
              <Box sx={{ textAlign: 'center' }}>
                <Box
                  sx={{
                    width: { xs: 200, md: 250 },
                    height: { xs: 200, md: 250 },
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, rgba(255, 90, 95, 0.1) 0%, rgba(0, 166, 153, 0.1) 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    mx: 'auto',
                    mb: 4,
                    border: '4px solid',
                    borderColor: 'primary.main'
                  }}
                >
                  <VideocamIcon sx={{ fontSize: { xs: 80, md: 100 }, color: 'primary.main' }} />
                </Box>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 3 }}>
                  Try the Experiment
                </Typography>
                <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
                  Explore one of the AI experiments behind the platform. The main ZeroQwait product today
                  is the AI receptionist plus owner operations workspace.
                </Typography>
                <Button
                  variant="contained"
                  size="large"
                  component={RouterLink}
                  to="/queue-counter"
                  startIcon={<SmartToyIcon />}
                  sx={{
                    fontSize: '1.25rem',
                    fontWeight: 600,
                    px: 5,
                    py: 2,
                    borderRadius: '50px',
                    background: 'linear-gradient(135deg, #00A699 0%, #4DB6AC 100%)',
                    boxShadow: '0 8px 32px rgba(0, 166, 153, 0.3)',
                    '&:hover': {
                      background: 'linear-gradient(135deg, #00897B 0%, #00A699 100%)',
                      boxShadow: '0 12px 40px rgba(0, 166, 153, 0.4)',
                      transform: 'translateY(-2px)'
                    },
                    transition: 'all 0.3s ease-in-out'
                  }}
                >
                  Launch Camera Demo
                </Button>
              </Box>
            </Box>
          </Box>
        </Container>
      </Box>

      {/* CTA Section */}
      <Box
        sx={{
          py: { xs: 8, md: 12 },
          background: 'linear-gradient(135deg, rgba(255, 90, 95, 0.05) 0%, rgba(0, 166, 153, 0.05) 100%)',
        }}
      >
        <Container maxWidth="md">
          <Box sx={{ textAlign: 'center' }}>
            <Typography
              variant="h2"
              sx={{
                fontSize: { xs: '1.75rem', md: '2.25rem' },
                fontWeight: 600,
                mb: 2
              }}
            >
              Ready to give your shop an AI team?
            </Typography>
            <Typography
              variant="h6"
              sx={{
                color: 'text.secondary',
                mb: 4,
                fontWeight: 400
              }}
            >
              Use ZeroQwait to handle customer flow, appointments, and owner oversight from one AI-powered system.
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                size="large"
                component={RouterLink}
                to="/search"
                sx={{
                  fontSize: '1.125rem',
                  fontWeight: 600,
                  px: 4,
                  py: 1.5,
                  borderRadius: '50px',
                }}
              >
                Get Started
              </Button>
              {!isAuthenticated && (
                <Button
                  variant="outlined"
                  size="large"
                  component={RouterLink}
                  to="/register"
                  sx={{
                    fontSize: '1.125rem',
                    fontWeight: 600,
                    px: 4,
                    py: 1.5,
                    borderRadius: '50px',
                    borderWidth: 2,
                    '&:hover': {
                      borderWidth: 2
                    }
                  }}
                >
                  Sign Up Your Business
                </Button>
              )}
            </Box>
          </Box>
        </Container>
      </Box>
    </Box>
  );
};

export default HomePage;
