import * as React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import MuiCard from '@mui/material/Card';
import Checkbox from '@mui/material/Checkbox';
import Divider from '@mui/material/Divider';
import FormLabel from '@mui/material/FormLabel';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import Link from '@mui/material/Link';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import ForgotPassword from './ForgotPassword';
import { GoogleIcon, FacebookIcon, SitemarkIcon } from './CustomIcons';
import { useAuth } from '../../contexts/AuthContext';
import axios from 'axios';
import Alert from '@mui/material/Alert';

const Card = styled(MuiCard)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignSelf: 'center',
  width: '100%',
  padding: theme.spacing(4),
  gap: theme.spacing(2),
  boxShadow:
    'hsla(220, 30%, 5%, 0.05) 0px 5px 15px 0px, hsla(220, 25%, 10%, 0.05) 0px 15px 35px -5px',
  [theme.breakpoints.up('sm')]: {
    width: '450px',
  },
  ...theme.applyStyles('dark', {
    boxShadow:
      'hsla(220, 30%, 5%, 0.5) 0px 5px 15px 0px, hsla(220, 25%, 10%, 0.08) 0px 15px 35px -5px',
  }),
}));

export default function SignInCard() {
  const [emailError, setEmailError] = React.useState(false);
  const [emailErrorMessage, setEmailErrorMessage] = React.useState('');
  const [passwordError, setPasswordError] = React.useState(false);
  const [passwordErrorMessage, setPasswordErrorMessage] = React.useState('');
  const [open, setOpen] = React.useState(false);

  const { login, loading, error, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  const handleClickOpen = () => {
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
  };

  // Navigate based on user role after successful login
  React.useEffect(() => {
    if (isAuthenticated && !loading && !error && user) {
      // Function to redirect to shop-specific subdomain
      const redirectToShopDashboard = async () => {
        try {
          const token = localStorage.getItem("token");
          if (!token) {
            navigate("/dashboard");
            return;
          }

          // Fetch user's shops using axios (uses configured baseURL)
          const response = await axios.get("/shops/my-shops", {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });

          const shops = response.data;
          console.log("[LoginPage] Shops fetched:", shops);

          if (shops && shops.length > 0) {
            const shop = shops[0];
            // The shop should have a slug - use it or generate from name
            const shopSlug = shop.slug || shop.name.toLowerCase().replace(/\s+/g, "-");

            console.log("[LoginPage] Shop slug:", shopSlug);

            // Build the subdomain URL
            const currentHost = window.location.hostname;
            const protocol = window.location.protocol;
            let newUrl = "";

            if (currentHost.includes("nip.io") || currentHost.includes("np.io")) {
              // nip.io / np.io URLs logic
              const isBaseDomain = currentHost.match(/^\d+\.\d+\.\d+\.\d+\.(nip|np)\.io$/);

              if (isBaseDomain) {
                // We are on the base, prepend slug
                newUrl = `${protocol}//${shopSlug}.${currentHost}/dashboard`;
              } else {
                // We might be on www.192... or another subdomain.
                // We want to REPLACE the subdomain with the shop slug.
                const ipSuffixMatch = currentHost.match(/(\d+\.\d+\.\d+\.\d+\.(nip|np)\.io)$/);
                if (ipSuffixMatch) {
                  newUrl = `${protocol}//${shopSlug}.${ipSuffixMatch[1]}/dashboard`;
                } else {
                  // Fallback
                  newUrl = "/dashboard";
                }
              }
            } else if (currentHost === "localhost") {
              // For pure localhost (no subclomain support usually unless configured in hosts)
              newUrl = "/dashboard";
            } else {
              // Production domain logic (e.g. zeroqwait.com)
              const parts = currentHost.split('.');
              if (parts.length === 2) { // zeroqwait.com
                newUrl = `${protocol}//${shopSlug}.${currentHost}/dashboard`;
              } else { // www.zeroqwait.com or existing.zeroqwait.com
                // Replace subdomain or add it
                const domain = parts.slice(-2).join('.'); // zeroqwait.com
                newUrl = `${protocol}//${shopSlug}.${domain}/dashboard`;
              }
            }

            console.log(`[LoginPage] Redirecting to: ${newUrl}`);
            if (newUrl.startsWith("http")) {
              window.location.href = newUrl;
            } else {
              navigate(newUrl);
            }
          } else {
            console.log("[LoginPage] No shops found, redirecting to /dashboard");
            navigate("/dashboard");
          }
        } catch (err) {
          console.error("[LoginPage] Error fetching shop info:", err);
          navigate("/dashboard");
        }
      };

      console.log("[LoginPage] User role:", user.role);
      if (user.role === "shop_owner") {
        // Try to redirect to shop subdomain, but fallback to regular dashboard
        redirectToShopDashboard();
      } else if (user.role === "employee") {
        console.log("[LoginPage] Redirecting to /employee-dashboard");
        navigate("/employee-dashboard");
      } else {
        console.log("[LoginPage] Redirecting to home");
        navigate("/");
      }
    }
  }, [isAuthenticated, loading, error, user, navigate]);


  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault(); // Always prevent default first
    if (emailError || passwordError) {
      return;
    }
    const data = new FormData(event.currentTarget);
    const email = data.get('email') as string;
    const password = data.get('password') as string;

    // Call existing login function
    await login(email, password);
  };

  const validateInputs = () => {
    const email = document.getElementById('email') as HTMLInputElement;
    const password = document.getElementById('password') as HTMLInputElement;

    let isValid = true;

    if (!email.value || email.value.trim().length === 0) {
      setEmailError(true);
      setEmailErrorMessage('Please enter your email or username.');
      isValid = false;
    } else {
      setEmailError(false);
      setEmailErrorMessage('');
    }

    if (!password.value || password.value.length < 3) { // Changed to 3 as previously it was 6 but some dev passwords might be short
      setPasswordError(true);
      setPasswordErrorMessage('Password must be at least 3 characters long.');
      isValid = false;
    } else {
      setPasswordError(false);
      setPasswordErrorMessage('');
    }

    return isValid;
  };

  return (
    <Card variant="outlined">
      <Box sx={{ display: { xs: 'flex', md: 'none' } }}>
        <Typography variant="h4" component="div" sx={{ fontWeight: 'bold', color: 'primary.main' }}>
          ZeroQwait
        </Typography>
      </Box>
      <Typography
        component="h1"
        variant="h4"
        sx={{ width: '100%', fontSize: 'clamp(2rem, 10vw, 2.15rem)' }}
      >
        Sign in
      </Typography>
      {error && (
        <Alert severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      )}
      <Box
        component="form"
        onSubmit={handleSubmit}
        noValidate
        sx={{ display: 'flex', flexDirection: 'column', width: '100%', gap: 2 }}
      >
        <FormControl>
          <FormLabel htmlFor="email">Email or Username</FormLabel>
          <TextField
            error={emailError}
            helperText={emailErrorMessage}
            id="email"
            type="text"
            name="email"
            placeholder="username or email"
            autoComplete="username"
            autoFocus
            required
            fullWidth
            variant="outlined"
            color={emailError ? 'error' : 'primary'}
          />
        </FormControl>
        <FormControl>
          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <FormLabel htmlFor="password">Password</FormLabel>
            <Link
              component="button"
              type="button"
              onClick={handleClickOpen}
              variant="body2"
              sx={{ alignSelf: 'baseline' }}
            >
              Forgot your password?
            </Link>
          </Box>
          <TextField
            error={passwordError}
            helperText={passwordErrorMessage}
            name="password"
            placeholder="••••••"
            type="password"
            id="password"
            autoComplete="current-password"
            required
            fullWidth
            variant="outlined"
            color={passwordError ? 'error' : 'primary'}
          />
        </FormControl>
        <FormControlLabel
          control={<Checkbox value="remember" color="primary" />}
          label="Remember me"
        />
        <ForgotPassword open={open} handleClose={handleClose} />
        <Button type="submit" fullWidth variant="contained" onClick={validateInputs} disabled={loading}>
          {loading ? 'Signing in...' : 'Sign in'}
        </Button>
        <Typography sx={{ textAlign: 'center' }}>
          Don&apos;t have an account?{' '}
          <span>
            <Link
              href="/signup"
              variant="body2"
              sx={{ alignSelf: 'center' }}
            >
              Sign up
            </Link>
          </span>
        </Typography>
      </Box>
      <Divider>or</Divider>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Button
          fullWidth
          variant="outlined"
          onClick={() => alert('Sign in with Google')}
          startIcon={<GoogleIcon />}
        >
          Sign in with Google
        </Button>
      </Box>
    </Card>
  );
}
