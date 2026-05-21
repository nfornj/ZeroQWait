import React, { useState } from "react";
import { Loader2, LocateFixed, Search } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";

interface SearchFormProps {
  onSearch: (latitude: number, longitude: number, radius: number) => Promise<void>;
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
          await onSearch(position.coords.latitude, position.coords.longitude, radius);
          setLocation(`${position.coords.latitude}, ${position.coords.longitude}`);
        } catch {
          setError("Failed to search with current location");
        } finally {
          setLoading(false);
        }
      },
      () => {
        setError("Failed to get your location. Please enter it manually.");
        setLoading(false);
      },
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const coords = location.split(",").map((coord) => parseFloat(coord.trim()));
    if (coords.length !== 2 || Number.isNaN(coords[0]) || Number.isNaN(coords[1])) {
      setError("Please enter valid coordinates (latitude, longitude) or use current location");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await onSearch(coords[0], coords[1], radius);
    } catch {
      setError("Failed to search for haircut services");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-border/70 bg-gradient-to-br from-primary/5 to-secondary/30">
      <CardContent className="p-6 md:p-8">
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex flex-col gap-3">
            <Label htmlFor="location" className="text-base">
              Where do you want to find a haircut?
            </Label>
            <div className="flex flex-col gap-3 md:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="location"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  disabled={loading}
                  placeholder="Enter coordinates (latitude, longitude)"
                  className="pl-9"
                />
              </div>
              <Button type="button" variant="outline" onClick={handleUseCurrentLocation} disabled={loading}>
                <LocateFixed data-icon="inline-start" />
                Use My Location
              </Button>
            </div>
          </div>

          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="radius" className="text-base">
                Search radius
              </Label>
              <span className="text-sm font-medium text-muted-foreground">{radius} km</span>
            </div>
            <Slider
              id="radius"
              value={[radius]}
              min={1}
              max={50}
              step={1}
              onValueChange={(value) => setRadius(value[0] || 1)}
              disabled={loading}
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>1km</span>
              <span>10km</span>
              <span>25km</span>
              <span>50km</span>
            </div>
          </div>

          <Button type="submit" size="lg" disabled={loading || !location.trim()}>
            {loading && <Loader2 data-icon="inline-start" className="animate-spin" />}
            Search for Salons
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

export default SearchForm;
