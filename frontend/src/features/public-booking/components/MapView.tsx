import React, { useEffect, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import { Clock, Loader2, MapPin, Phone } from "lucide-react";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require("leaflet/dist/images/marker-icon-2x.png"),
  iconUrl: require("leaflet/dist/images/marker-icon.png"),
  shadowUrl: require("leaflet/dist/images/marker-shadow.png"),
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

const MapBoundsController: React.FC<{ shops: Shop[] }> = ({ shops }) => {
  const map = useMap();

  useEffect(() => {
    const shopsWithCoords = shops.filter((shop) => shop.latitude && shop.longitude);

    if (shopsWithCoords.length > 0) {
      const bounds = L.latLngBounds(shopsWithCoords.map((shop) => [shop.latitude!, shop.longitude!]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  }, [shops, map]);

  return null;
};

const geocodeAddress = async (
  address: string,
  city: string,
  state: string,
  country: string,
): Promise<{ lat: number; lng: number } | null> => {
  try {
    const query = `${address}, ${city}, ${state}, ${country}`;
    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`,
    );
    const data = await response.json();

    if (data && data.length > 0) {
      return {
        lat: parseFloat(data[0].lat),
        lng: parseFloat(data[0].lon),
      };
    }
    return null;
  } catch {
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
          processed.push(shop);
        } else {
          const coords = await geocodeAddress(shop.address, shop.city, shop.state, shop.country);
          if (coords) {
            processed.push({ ...shop, latitude: coords.lat, longitude: coords.lng });
          }
        }
      }

      setShopsWithCoords(processed);
      setLoading(false);
    };

    void processShops();
  }, [shops]);

  if (loading) {
    return (
      <div className="flex h-[600px] items-center justify-center rounded-lg border bg-card">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 className="size-8 animate-spin text-primary" />
          <p>Loading map...</p>
        </div>
      </div>
    );
  }

  if (shopsWithCoords.length === 0) {
    return (
      <div className="flex h-[600px] items-center justify-center rounded-lg border bg-card text-center text-lg font-medium text-muted-foreground">
        No locations available to display on map
      </div>
    );
  }

  return (
    <div className="h-[600px] overflow-hidden rounded-lg border">
      <MapContainer center={[37.7749, -122.4194]} zoom={13} style={{ height: "100%", width: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapBoundsController shops={shopsWithCoords} />
        {shopsWithCoords.map((shop) => (
          <Marker key={shop.id} position={[shop.latitude!, shop.longitude!]}>
            <Popup maxWidth={300}>
              <div className="flex min-w-[240px] flex-col gap-3 p-1">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-base font-semibold leading-tight">{shop.name}</h3>
                  <Badge>{shop.shop_type}</Badge>
                </div>
                {shop.description && <p className="text-sm text-muted-foreground">{shop.description}</p>}
                <div className="flex flex-col gap-1.5 text-sm text-muted-foreground">
                  <span className="inline-flex items-center gap-2">
                    <MapPin className="size-4" />
                    {shop.city}, {shop.state}
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <Phone className="size-4" />
                    {shop.phone}
                  </span>
                  <span className="inline-flex items-center gap-2">
                    <Clock className="size-4" />
                    Avg. {shop.average_service_time} min service
                  </span>
                </div>
                <Button size="sm" className="w-full" onClick={() => navigate(`/queue/${shop.id}`)}>
                  Join Queue
                </Button>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
};

export default MapView;
