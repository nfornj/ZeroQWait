import * as React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CssBaseline from '@mui/material/CssBaseline';
import FormLabel from '@mui/material/FormLabel';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import MuiCard from '@mui/material/Card';
import { styled } from '@mui/material/styles';
import MenuItem from '@mui/material/MenuItem';
import Alert from '@mui/material/Alert';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AppTheme from '../auth-shared-theme/AppTheme';

const Card = styled(MuiCard)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignSelf: 'center',
  width: '100%',
  padding: theme.spacing(4),
  gap: theme.spacing(2),
  margin: 'auto',
  maxWidth: '900px',
  boxShadow:
    'hsla(220, 30%, 5%, 0.05) 0px 5px 15px 0px, hsla(220, 25%, 10%, 0.05) 0px 15px 35px -5px',
  ...theme.applyStyles('dark', {
    boxShadow:
      'hsla(220, 30%, 5%, 0.5) 0px 5px 15px 0px, hsla(220, 25%, 10%, 0.08) 0px 15px 35px -5px',
  }),
}));

const SignUpContainer = styled(Stack)(({ theme }) => ({
  minHeight: '100vh',
  padding: theme.spacing(2),
  paddingTop: theme.spacing(4),
  paddingBottom: theme.spacing(4),
  backgroundImage:
    'radial-gradient(ellipse at 50% 50%, hsl(270, 50%, 25%), hsl(260, 60%, 8%))',
  backgroundRepeat: 'no-repeat',
  backgroundSize: 'cover',
  position: 'relative',
}));

const shopTypes = [
  { value: 'barber', label: 'Barber Shop' },
  { value: 'salon', label: 'Hair Salon' },
  { value: 'doctor', label: 'Doctor/Medical' },
  { value: 'restaurant', label: 'Restaurant' },
  { value: 'spa', label: 'Spa' },
  { value: 'other', label: 'Other' },
];

export default function ShopOwnerSignUp() {
  const navigate = useNavigate();
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');

  const [formData, setFormData] = React.useState({
    // User fields
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    // Shop fields
    shopName: '',
    shop_type: 'barber',
    description: '',
    address: '',
    city: '',
    state: '',
    zip_code: '',
    country: 'United States',
    phone: '',
    shopEmail: '',
    website: '',
    average_service_time: 30,
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    // Validation
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);

    try {
      // Step 1: Create user account
      const userResponse = await axios.post('users', {
        username: formData.username,
        email: formData.email,
        password: formData.password,
        role: 'shop_owner',
      });

      // Step 2: Login to get token
      const loginFormData = new URLSearchParams();
      loginFormData.append('username', formData.username);
      loginFormData.append('password', formData.password);

      const tokenResponse = await axios.post('auth/token', loginFormData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      const token = tokenResponse.data.access_token;
      localStorage.setItem('token', token);

      // Step 3: Create shop
      await axios.post('shops/', {
        name: formData.shopName,
        shop_type: formData.shop_type,
        description: formData.description,
        address: formData.address,
        city: formData.city,
        state: formData.state,
        zip_code: formData.zip_code,
        country: formData.country,
        phone: formData.phone,
        email: formData.shopEmail || formData.email,
        website: formData.website,
        average_service_time: parseInt(formData.average_service_time.toString()),
      }, {
        headers: { Authorization: `Bearer ${token}` },
      });

      // Success! Redirect to dashboard
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppTheme mode="dark">
      <CssBaseline enableColorScheme />
      <SignUpContainer direction="column" alignItems="center">
        <Card variant="outlined">
          <Typography variant="h3" sx={{ fontWeight: 'bold', color: 'primary.main', fontSize: '2.5rem', mb: 1 }}>
            ZeroQwait
          </Typography>
          <Typography component="h1" variant="h4" sx={{ width: '100%', fontSize: 'clamp(1.5rem, 8vw, 2rem)' }}>
            Create Your Shop Account
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Register your business and start managing queues
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Account Section */}
            <Typography variant="h6" sx={{ mt: 2, color: 'primary.main' }}>Account Information</Typography>

            <Box display="flex" gap={2} flexWrap="wrap">
              <FormControl sx={{ flex: 1, minWidth: '200px' }}>
                <FormLabel htmlFor="username">Username *</FormLabel>
                <TextField
                  required
                  fullWidth
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  autoComplete="username"
                />
              </FormControl>

              <FormControl sx={{ flex: 1, minWidth: '200px' }}>
                <FormLabel htmlFor="email">Email *</FormLabel>
                <TextField
                  required
                  fullWidth
                  id="email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                  autoComplete="email"
                />
              </FormControl>
            </Box>

            <Box display="flex" gap={2} flexWrap="wrap">
              <FormControl sx={{ flex: 1, minWidth: '200px' }}>
                <FormLabel htmlFor="password">Password *</FormLabel>
                <TextField
                  required
                  fullWidth
                  id="password"
                  name="password"
                  type="password"
                  value={formData.password}
                  onChange={handleChange}
                  autoComplete="new-password"
                />
              </FormControl>

              <FormControl sx={{ flex: 1, minWidth: '200px' }}>
                <FormLabel htmlFor="confirmPassword">Confirm Password *</FormLabel>
                <TextField
                  required
                  fullWidth
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  autoComplete="new-password"
                />
              </FormControl>
            </Box>

            {/* Shop Section */}
            <Typography variant="h6" sx={{ mt: 3, color: 'primary.main' }}>Business Information</Typography>

            <Box display="flex" gap={2} flexWrap="wrap">
              <FormControl sx={{ flex: 1, minWidth: '200px' }}>
                <FormLabel htmlFor="shopName">Shop Name *</FormLabel>
                <TextField
                  required
                  fullWidth
                  id="shopName"
                  name="shopName"
                  value={formData.shopName}
                  onChange={handleChange}
                />
              </FormControl>

              <FormControl sx={{ flex: 1, minWidth: '200px' }}>
                <FormLabel htmlFor="shop_type">Business Type *</FormLabel>
                <TextField
                  required
                  fullWidth
                  select
                  id="shop_type"
                  name="shop_type"
                  value={formData.shop_type}
                  onChange={handleChange}
                >
                  {shopTypes.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </TextField>
              </FormControl>
            </Box>

            <FormControl>
              <FormLabel htmlFor="description">Description</FormLabel>
              <TextField
                fullWidth
                multiline
                rows={2}
                id="description"
                name="description"
                value={formData.description}
                onChange={handleChange}
              />
            </FormControl>

            {/* Location Section */}
            <Typography variant="h6" sx={{ mt: 3, color: 'primary.main' }}>Location</Typography>

            <FormControl>
              <FormLabel htmlFor="address">Street Address *</FormLabel>
              <TextField
                required
                fullWidth
                id="address"
                name="address"
                value={formData.address}
                onChange={handleChange}
              />
            </FormControl>

            <Box display="flex" gap={2} flexWrap="wrap">
              <FormControl sx={{ flex: 1, minWidth: '150px' }}>
                <FormLabel htmlFor="city">City *</FormLabel>
                <TextField
                  required
                  fullWidth
                  id="city"
                  name="city"
                  value={formData.city}
                  onChange={handleChange}
                />
              </FormControl>

              <FormControl sx={{ flex: 1, minWidth: '100px' }}>
                <FormLabel htmlFor="state">State/Region *</FormLabel>
                <TextField
                  required
                  fullWidth
                  id="state"
                  name="state"
                  value={formData.state}
                  onChange={handleChange}
                />
              </FormControl>

              <FormControl sx={{ flex: 1, minWidth: '100px' }}>
                <FormLabel htmlFor="zip_code">ZIP Code *</FormLabel>
                <TextField
                  required
                  fullWidth
                  id="zip_code"
                  name="zip_code"
                  value={formData.zip_code}
                  onChange={handleChange}
                />
              </FormControl>
            </Box>

            {/* Contact Section */}
            <Typography variant="h6" sx={{ mt: 3, color: 'primary.main' }}>Contact Information</Typography>

            <Box display="flex" gap={2} flexWrap="wrap">
              <FormControl sx={{ flex: 1, minWidth: '200px' }}>
                <FormLabel htmlFor="phone">Phone *</FormLabel>
                <TextField
                  required
                  fullWidth
                  id="phone"
                  name="phone"
                  value={formData.phone}
                  onChange={handleChange}
                />
              </FormControl>

              <FormControl sx={{ flex: 1, minWidth: '200px' }}>
                <FormLabel htmlFor="shopEmail">Business Email (optional)</FormLabel>
                <TextField
                  fullWidth
                  id="shopEmail"
                  name="shopEmail"
                  type="email"
                  value={formData.shopEmail}
                  onChange={handleChange}
                />
              </FormControl>
            </Box>

            <Box display="flex" gap={2} flexWrap="wrap">
              <FormControl sx={{ flex: 2, minWidth: '200px' }}>
                <FormLabel htmlFor="website">Website (optional)</FormLabel>
                <TextField
                  fullWidth
                  id="website"
                  name="website"
                  value={formData.website}
                  onChange={handleChange}
                />
              </FormControl>

              <FormControl sx={{ flex: 1, minWidth: '150px' }}>
                <FormLabel htmlFor="average_service_time">Avg. Service Time (min)</FormLabel>
                <TextField
                  fullWidth
                  type="number"
                  id="average_service_time"
                  name="average_service_time"
                  value={formData.average_service_time}
                  onChange={handleChange}
                  inputProps={{ min: 5, max: 180 }}
                />
              </FormControl>
            </Box>

            <Button
              type="submit"
              fullWidth
              variant="contained"
              disabled={loading}
              sx={{ mt: 3 }}
            >
              {loading ? 'Creating Account...' : 'Create Shop Account'}
            </Button>

            <Typography sx={{ textAlign: 'center', mt: 2 }}>
              Already have an account?{' '}
              <Box component="a" href="/login" sx={{ color: 'primary.main', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } }}>
                Sign in
              </Box>
            </Typography>
          </Box>
        </Card>
      </SignUpContainer>
    </AppTheme>
  );
}
