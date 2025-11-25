import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Container,
  Typography,
  Box,
  Grid,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  CardActions,
  Button,
  Chip,
  TextField,
} from "@mui/material";
import LocationOnIcon from "@mui/icons-material/LocationOn";
import PhoneIcon from "@mui/icons-material/Phone";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import axios from "axios";

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

interface Shop {
  id: number;
  name: string;
  description?: string;
  shop_type: string;
  address: string;
  city: string;
  state: string;
  phone: string;
  average_service_time: number;
}

const SearchPage: React.FC = () => {
  const [shops, setShops] = useState<Shop[]>([]);
  const [filteredShops, setFilteredShops] = useState<Shop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    fetchAllShops();
  }, []);

  useEffect(() => {
    if (searchTerm.trim() === '') {
      setFilteredShops(shops);
    } else {
      const term = searchTerm.toLowerCase();
      const filtered = shops.filter(shop =>
        shop.name.toLowerCase().includes(term) ||
        shop.shop_type.toLowerCase().includes(term) ||
        shop.city.toLowerCase().includes(term) ||
        shop.state.toLowerCase().includes(term) ||
        (shop.description && shop.description.toLowerCase().includes(term))
      );
      setFilteredShops(filtered);
    }
  }, [searchTerm, shops]);

  const fetchAllShops = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get(`${API_URL}/shops/`);
      setShops(response.data);
      setFilteredShops(response.data);
    } catch (err) {
      setError("Failed to load businesses. Please try again.");
      console.error("Fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ bgcolor: 'background.default', minHeight: '100vh' }}>
      {/* Hero Section */}
      <Box 
        sx={{ 
          background: 'linear-gradient(135deg, rgba(255, 90, 95, 0.05) 0%, rgba(0, 166, 153, 0.05) 100%)',
          py: { xs: 4, md: 6 }
        }}
      >
        <Container maxWidth="lg">
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            <Typography 
              variant="h3" 
              component="h1" 
              sx={{
                fontWeight: 700,
                mb: 2,
                fontSize: { xs: '2rem', md: '2.5rem' },
                color: 'text.primary'
              }}
            >
              Find Service Providers
            </Typography>
            <Typography 
              variant="h6" 
              sx={{
                color: 'text.secondary',
                maxWidth: '600px',
                mx: 'auto',
                fontSize: { xs: '1rem', md: '1.125rem' },
                fontWeight: 400
              }}
            >
              Search barbershops, salons, clinics, and other services with queue management
            </Typography>
          </Box>
          
          <Box sx={{ maxWidth: '800px', mx: 'auto', mt: 4 }}>
            <TextField
              fullWidth
              placeholder="Search by name, type, or location..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              sx={{
                '& .MuiOutlinedInput-root': {
                  bgcolor: 'background.paper',
                  borderRadius: 2,
                }
              }}
            />
          </Box>
        </Container>
      </Box>

      {/* Results Section */}
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
        {error && (
          <Alert 
            severity="error" 
            sx={{ 
              mb: 4,
              borderRadius: 2,
              border: '1px solid #FFEBEE'
            }}
          >
            {error}
          </Alert>
        )}

        {loading ? (
          <Box 
            sx={{ 
              display: 'flex', 
              flexDirection: 'column',
              alignItems: 'center',
              py: 8
            }}
          >
            <CircularProgress 
              size={48} 
              sx={{ 
                mb: 2,
                color: 'primary.main'
              }} 
            />
            <Typography variant="h6" color="text.secondary">
              Loading businesses...
            </Typography>
          </Box>
        ) : filteredShops.length > 0 ? (
          <Box>
            <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography 
                variant="h5" 
                sx={{ 
                  fontWeight: 600,
                  color: 'text.primary'
                }}
              >
                Found {filteredShops.length} business{filteredShops.length !== 1 ? 'es' : ''}
              </Typography>
            </Box>
            
            <Grid container spacing={3}>
              {filteredShops.map((shop) => (
                <Grid item xs={12} sm={6} lg={4} key={shop.id}>
                  <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                    <CardContent sx={{ flexGrow: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                          {shop.name}
                        </Typography>
                        <Chip label={shop.shop_type} size="small" color="primary" />
                      </Box>
                      {shop.description && (
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                          {shop.description}
                        </Typography>
                      )}
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <LocationOnIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                        <Typography variant="body2" color="text.secondary">
                          {shop.city}, {shop.state}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <PhoneIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                        <Typography variant="body2" color="text.secondary">
                          {shop.phone}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <AccessTimeIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                        <Typography variant="body2" color="text.secondary">
                          Avg. {shop.average_service_time} min service
                        </Typography>
                      </Box>
                    </CardContent>
                    <CardActions sx={{ p: 2, pt: 0 }}>
                      <Button fullWidth variant="contained" onClick={() => navigate(`/queue/${shop.id}`)}>
                        Join Queue
                      </Button>
                    </CardActions>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>
        ) : (
          !loading && !error && (
            <Box 
              sx={{ 
                textAlign: 'center',
                py: 8
              }}
            >
              <Typography 
                variant="h5" 
                sx={{ 
                  color: 'text.secondary',
                  mb: 2,
                fontWeight: 500
                }}
              >
                No businesses found
              </Typography>
              <Typography variant="body1" color="text.secondary">
                {searchTerm ? 'Try a different search term' : 'No businesses are registered yet'}
              </Typography>
            </Box>
          )
        )}
      </Container>
    </Box>
  );
};

export default SearchPage;
