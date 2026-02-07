import React, { useState, useEffect } from "react";
import {
  Container,
  Typography,
  Box,
  CircularProgress,
  Alert,
} from "@mui/material";
import { HaircutService, getFavorites } from "../../../services/api";
import HaircutCard from "../components/HaircutCard";

const FavoritesPage: React.FC = () => {
  const [favorites, setFavorites] = useState<HaircutService[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchFavorites = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getFavorites();
        setFavorites(data);
      } catch (err) {
        setError("Failed to load favorites. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchFavorites();
  }, []);

  const handleFavoriteRemoved = (removedId: number) => {
    setFavorites((prev) =>
      prev.filter((favorite) => favorite.id !== removedId)
    );
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        My Favorite Haircut Services
      </Typography>

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
        ) : favorites.length > 0 ? (
          <Box display="flex" flexWrap="wrap" gap={3}>
            {favorites.map((haircut) => (
              <Box sx={{ flex: 1, minWidth: '250px' }} key={haircut.id}>
                <HaircutCard
                  haircut={haircut}
                  onFavoriteRemoved={handleFavoriteRemoved}
                />
              </Box>
            ))}
          </Box>
        ) : (
          <Typography variant="body1" color="text.secondary" align="center">
            You haven't saved any favorites yet. Start by searching for haircut
            services!
          </Typography>
        )}
      </Box>
    </Container>
  );
};

export default FavoritesPage;
