import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Box,
  Typography,
  TextField,
  Button,
  MenuItem,
  Card,
  CardContent,
  Alert,
  Grid
} from '@mui/material';
import axios from 'axios';


const ShopRegistrationPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    shop_type: 'barber',
    address: '',
    city: '',
    state: '',
    zip_code: '',
    country: 'United States',
    phone: '',
    email: '',
    website: '',
    average_service_time: 30,
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const shopTypes = [
    { value: 'barber', label: 'Barber Shop' },
    { value: 'salon', label: 'Hair Salon' },
    { value: 'doctor', label: 'Doctor/Medical' },
    { value: 'restaurant', label: 'Restaurant' },
    { value: 'spa', label: 'Spa' },
    { value: 'other', label: 'Other' },
  ];

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const token = localStorage.getItem('token');
      if (!token) {
        navigate('/login');
        return;
      }

      await axios.post(`/shops/`, formData, {
        headers: { Authorization: `Bearer ${token}` },
      });

      setSuccess(true);
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || 'Failed to create shop. Please try again.'
      );
    }
  };

  return (
    <Container maxWidth="md" sx={{ mt: 8, mb: 4 }}>
      <Card elevation={2}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h3" component="h1" gutterBottom align="center">
            Register Your Shop
          </Typography>
          <Typography variant="body1" color="textSecondary" align="center" sx={{ mb: 4 }}>
            Create your shop profile and start managing your queue
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}
          {success && (
            <Alert severity="success" sx={{ mb: 3 }}>
              Shop created successfully! Redirecting to dashboard...
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit}>
            <Grid container spacing={3}>
              <Grid xs={12}>
                <TextField
                  fullWidth
                  required
                  label="Shop Name"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                />
              </Grid>

              <Grid xs={12}>
                <TextField
                  fullWidth
                  select
                  required
                  label="Shop Type"
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
              </Grid>

              <Grid xs={12}>
                <TextField
                  fullWidth
                  multiline
                  rows={3}
                  label="Description"
                  name="description"
                  value={formData.description}
                  onChange={handleChange}
                />
              </Grid>

              <Grid xs={12}>
                <TextField
                  fullWidth
                  required
                  label="Address"
                  name="address"
                  value={formData.address}
                  onChange={handleChange}
                />
              </Grid>

              <Grid xs={12} sm={6}>
                <TextField
                  fullWidth
                  required
                  label="City"
                  name="city"
                  value={formData.city}
                  onChange={handleChange}
                />
              </Grid>

              <Grid xs={12} sm={4}>
                <TextField
                  fullWidth
                  required
                  label="State/Province/Region"
                  name="state"
                  value={formData.state}
                  onChange={handleChange}
                  helperText="e.g., ON, CA, TX, etc."
                />
              </Grid>

              <Grid xs={12} sm={4}>
                <TextField
                  fullWidth
                  required
                  label="ZIP/Postal Code"
                  name="zip_code"
                  value={formData.zip_code}
                  onChange={handleChange}
                />
              </Grid>

              <Grid xs={12} sm={4}>
                <TextField
                  fullWidth
                  select
                  required
                  label="Country"
                  name="country"
                  value={formData.country}
                  onChange={handleChange}
                >
                  <MenuItem value="United States">United States</MenuItem>
                  <MenuItem value="Canada">Canada</MenuItem>
                  <MenuItem value="United Kingdom">United Kingdom</MenuItem>
                  <MenuItem value="Australia">Australia</MenuItem>
                  <MenuItem value="India">India</MenuItem>
                  <MenuItem value="Germany">Germany</MenuItem>
                  <MenuItem value="France">France</MenuItem>
                  <MenuItem value="Spain">Spain</MenuItem>
                  <MenuItem value="Italy">Italy</MenuItem>
                  <MenuItem value="Mexico">Mexico</MenuItem>
                  <MenuItem value="Brazil">Brazil</MenuItem>
                  <MenuItem value="Japan">Japan</MenuItem>
                  <MenuItem value="China">China</MenuItem>
                  <MenuItem value="South Korea">South Korea</MenuItem>
                  <MenuItem value="Singapore">Singapore</MenuItem>
                  <MenuItem value="Other">Other</MenuItem>
                </TextField>
              </Grid>

              <Grid xs={12} sm={6}>
                <TextField
                  fullWidth
                  required
                  label="Phone"
                  name="phone"
                  value={formData.phone}
                  onChange={handleChange}
                />
              </Grid>

              <Grid xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                />
              </Grid>

              <Grid xs={12} sm={6}>
                <TextField
                  fullWidth
                  label="Website"
                  name="website"
                  value={formData.website}
                  onChange={handleChange}
                />
              </Grid>

              <Grid xs={12} sm={6}>
                <TextField
                  fullWidth
                  required
                  type="number"
                  label="Average Service Time (minutes)"
                  name="average_service_time"
                  value={formData.average_service_time}
                  onChange={handleChange}
                  inputProps={{ min: 5, max: 180 }}
                />
              </Grid>

              <Grid xs={12}>
                <Button
                  type="submit"
                  variant="contained"
                  color="primary"
                  fullWidth
                  size="large"
                  sx={{ mt: 2 }}
                >
                  Create Shop
                </Button>
              </Grid>
            </Grid>
          </Box>
        </CardContent>
      </Card>
    </Container>
  );
};

export default ShopRegistrationPage;
