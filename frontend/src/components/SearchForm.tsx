import React, { useState } from "react";
import {
  Paper,
  TextField,
  Button,
  Box,
  Alert,
  CircularProgress,
  InputAdornment,
  Slider,
  Typography,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import MyLocationIcon from "@mui/icons-material/MyLocation";

interface SearchFormProps {
  onSearch: (
    latitude: number,
    longitude: number,
    radius: number
  ) => Promise<void>;
}

const SearchForm: React.FC<SearchFormProps> = ({ onSearch }) => {
  const [location, setLocation] = useState("");
  const [radius, setRadius] = useState(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUseCurrentLocation = () => {
    if (!navigator.geolocation) {
      setError("Geolocation is not supported by your browser");
      return;
    }

    setLoading(true);
    setError(null);

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          await onSearch(
            position.coords.latitude,
            position.coords.longitude,
            radius
          );
          setLocation(
            `${position.coords.latitude}, ${position.coords.longitude}`
          );
        } catch (err) {
          setError("Failed to search with current location");
          console.error("Search error:", err);
        } finally {
          setLoading(false);
        }
      },
      (error) => {
        setError("Failed to get your location. Please enter it manually.");
        setLoading(false);
        console.error("Geolocation error:", error);
      }
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Simple validation for coordinates format (latitude, longitude)
    const coords = location.split(",").map((coord) => parseFloat(coord.trim()));
    if (coords.length !== 2 || isNaN(coords[0]) || isNaN(coords[1])) {
      setError(
        "Please enter valid coordinates (latitude, longitude) or use current location"
      );
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await onSearch(coords[0], coords[1], radius);
    } catch (err) {
      setError("Failed to search for haircut services");
      console.error("Search error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper component="form" onSubmit={handleSubmit} sx={{ p: 3 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ display: "flex", gap: 2, mb: 3 }}>
        <TextField
          fullWidth
          label="Location (latitude, longitude)"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
          disabled={loading}
          placeholder="Enter coordinates or use current location"
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
        />
        <Button
          variant="contained"
          onClick={handleUseCurrentLocation}
          disabled={loading}
          startIcon={<MyLocationIcon />}
        >
          Use Current Location
        </Button>
      </Box>

      <Box sx={{ mb: 3 }}>
        <Typography gutterBottom>Search Radius (km)</Typography>
        <Slider
          value={radius}
          onChange={(_, newValue) => setRadius(newValue as number)}
          min={1}
          max={50}
          valueLabelDisplay="auto"
          marks={[
            { value: 1, label: "1km" },
            { value: 25, label: "25km" },
            { value: 50, label: "50km" },
          ]}
        />
      </Box>

      <Button
        type="submit"
        variant="contained"
        fullWidth
        disabled={loading || !location}
        sx={{ mt: 2 }}
      >
        {loading ? <CircularProgress size={24} /> : "Search"}
      </Button>
    </Paper>
  );
};

export default SearchForm;
