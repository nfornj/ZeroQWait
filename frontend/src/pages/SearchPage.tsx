import React, { useState } from "react";
import {
  Container,
  Typography,
  Box,
  Grid,
  CircularProgress,
  Alert,
} from "@mui/material";
import { HaircutService } from "../services/api";
import HaircutCard from "../components/HaircutCard";
import SearchForm from "../components/SearchForm";
import { searchHaircuts } from "../services/api";

const SearchPage: React.FC = () => {
  const [haircuts, setHaircuts] = useState<HaircutService[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (
    latitude: number,
    longitude: number,
    radius: number
  ) => {
    try {
      setLoading(true);
      setError(null);
      const results = await searchHaircuts({ latitude, longitude, radius });
      setHaircuts(results);
    } catch (err) {
      setError("Failed to search for haircut services. Please try again.");
      console.error("Search error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Find Haircut Services
      </Typography>

      <SearchForm onSearch={handleSearch} />

      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ mt: 4 }}>
        {loading ? (
          <Box display="flex" justifyContent="center">
            <CircularProgress />
          </Box>
        ) : haircuts.length > 0 ? (
          <Grid container spacing={3}>
            {haircuts.map((haircut) => (
              <Grid item xs={12} sm={6} md={4} key={haircut.id}>
                <HaircutCard haircut={haircut} />
              </Grid>
            ))}
          </Grid>
        ) : (
          <Typography variant="body1" color="text.secondary" align="center">
            {error ? null : "Search for haircut services near you"}
          </Typography>
        )}
      </Box>
    </Container>
  );
};

export default SearchPage;
