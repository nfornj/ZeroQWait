import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import { Box, Typography, Button, Chip, CircularProgress } from "@mui/material";
import LocationOnIcon from "@mui/icons-material/LocationOn";
import PhoneIcon from "@mui/icons-material/Phone";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix for default marker icons in Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require('leaflet/dist/images/marker-icon-2x.png'),
  iconUrl: require('leaflet/dist/images/marker-icon.png'),
  shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
});

interface Shop {
  id: number;
  name: string;
  description?: string;
  shop_type: string;
  address: string;
  city: string;
  state: string;
  country: string;
  phone: string;
  average_service_time: number;
  latitude?: number;
  longitude?: number;
}

interface MapViewProps {
  shops: Shop[];
}

// Component to adjust map bounds based on markers
const MapBoundsController: React.FC<{ shops: Shop[] }> = ({ shops }) => {
  const map = useMap();

  useEffect(() => {
    const shopsWithCoords = shops.filter(
      (shop) => shop.latitude && shop.longitude
    );

    if (shopsWithCoords.length > 0) {
      const bounds = L.latLngBounds(
        shopsWithCoords.map((shop) => [shop.latitude!, shop.longitude!])
      );
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  }, [shops, map]);

  return null;
};

// Simple geocoding function using Nominatim (OpenStreetMap)
const geocodeAddress = async (
  address: string,
  city: string,
  state: string,
  country: string
): Promise<{ lat: number; lng: number } | null> => {
  try {
    const query = `${address}, ${city}, ${state}, ${country}`;
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
        query
      )}&limit=1`
    );
    const data = await response.json();

    if (data && data.length > 0) {
      return {
        lat: parseFloat(data[0].lat),
        lng: parseFloat(data[0].lon),
      };
    }
    return null;
  } catch (error) {
    return null;
  }
};

const MapView: React.FC<MapViewProps> = ({ shops }) => {
  const navigate = useNavigate();
  const [shopsWithCoords, setShopsWithCoords] = useState<Shop[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const processShops = async () => {
      setLoading(true);
      const processed: Shop[] = [];

      for (const shop of shops) {
        if (shop.latitude && shop.longitude) {
          // Shop already has coordinates
          processed.push(shop);
        } else {
          // Try to geocode the address
          const coords = await geocodeAddress(
            shop.address,
            shop.city,
            shop.state,
            shop.country
          );
          if (coords) {
            processed.push({
              ...shop,
              latitude: coords.lat,
              longitude: coords.lng,
            });
          }
        }
      }

      setShopsWithCoords(processed);
      setLoading(false);
    };

    processShops();
  }, [shops]);

  if (loading) {
    return (
      <Box
        sx={{
          height: "600px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: "background.paper",
          borderRadius: 2,
        }}
      >
        <Box sx={{ textAlign: "center" }}>
          <CircularProgress sx={{ mb: 2 }} />
          <Typography variant="body1" color="text.secondary">
            Loading map...
          </Typography>
        </Box>
      </Box>
    );
  }

  if (shopsWithCoords.length === 0) {
    return (
      <Box
        sx={{
          height: "600px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: "background.paper",
          borderRadius: 2,
          border: "1px solid #EBEBEB",
        }}
      >
        <Typography variant="h6" color="text.secondary">
          No locations available to display on map
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: "600px", borderRadius: 2, overflow: "hidden" }}>
      <MapContainer
        center={[37.7749, -122.4194]} // Default to San Francisco
        zoom={13}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapBoundsController shops={shopsWithCoords} />
        {shopsWithCoords.map((shop) => (
          <Marker
            key={shop.id}
            position={[shop.latitude!, shop.longitude!]}
          >
            <Popup maxWidth={300}>
              <Box sx={{ p: 1 }}>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "start",
                    mb: 1,
                  }}
                >
                  <Typography
                    variant="h6"
                    sx={{ fontWeight: 600, fontSize: "1rem" }}
                  >
                    {shop.name}
                  </Typography>
                  <Chip label={shop.shop_type} size="small" color="primary" />
                </Box>
                {shop.description && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mb: 1 }}
                  >
                    {shop.description}
                  </Typography>
                )}
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                  <LocationOnIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                  <Typography variant="body2" color="text.secondary">
                    {shop.city}, {shop.state}
                  </Typography>
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                  <PhoneIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                  <Typography variant="body2" color="text.secondary">
                    {shop.phone}
                  </Typography>
                </Box>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
                  <AccessTimeIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                  <Typography variant="body2" color="text.secondary">
                    Avg. {shop.average_service_time} min service
                  </Typography>
                </Box>
                <Button
                  fullWidth
                  variant="contained"
                  size="small"
                  onClick={() => navigate(`/queue/${shop.id}`)}
                >
                  Join Queue
                </Button>
              </Box>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </Box>
  );
};

export default MapView;
