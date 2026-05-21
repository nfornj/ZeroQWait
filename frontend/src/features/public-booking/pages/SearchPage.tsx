import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Clock, List, Loader2, Map, MapPin, Phone } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import MapView from "../components/MapView";

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

const SearchPage: React.FC = () => {
  const [shops, setShops] = useState<Shop[]>([]);
  const [filteredShops, setFilteredShops] = useState<Shop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "map">("list");
  const [countries, setCountries] = useState<string[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<string>("all");
  const navigate = useNavigate();

  const fetchCountries = async () => {
    try {
      const response = await axios.get("/shops/countries");
      setCountries(response.data || []);
    } catch {
      // Country filter is optional.
    }
  };

  const fetchAllShops = React.useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const params = selectedCountry !== "all" ? { country: selectedCountry } : {};
      const response = await axios.get(`/shops/`, { params });
      setShops(response.data);
      setFilteredShops(response.data);
    } catch {
      setError("Failed to load businesses. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [selectedCountry]);

  useEffect(() => {
    void fetchCountries();
  }, []);

  useEffect(() => {
    void fetchAllShops();
  }, [fetchAllShops]);

  useEffect(() => {
    if (searchTerm.trim() === "") {
      setFilteredShops(shops);
      return;
    }

    const term = searchTerm.toLowerCase();
    setFilteredShops(
      shops.filter(
        (shop) =>
          shop.name.toLowerCase().includes(term) ||
          shop.shop_type.toLowerCase().includes(term) ||
          shop.city.toLowerCase().includes(term) ||
          shop.state.toLowerCase().includes(term) ||
          (shop.description && shop.description.toLowerCase().includes(term)),
      ),
    );
  }, [searchTerm, shops]);

  return (
    <main className="min-h-screen bg-background">
      <section className="border-b bg-gradient-to-br from-primary/5 to-secondary/30 py-10 md:py-14">
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-6 px-4 text-center md:px-6">
          <div>
            <h1 className="text-4xl font-bold tracking-tight md:text-5xl">Find Shops and Services</h1>
            <p className="mx-auto mt-4 max-w-2xl text-lg text-muted-foreground">
              Search barbershops, salons, clinics, and other businesses, then open their live queue or appointment flow in one place.
            </p>
          </div>
          <Input
            className="max-w-3xl bg-background"
            placeholder="Search by name, type, or location..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10 md:px-6">
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <div className="flex flex-col items-center gap-3 py-20 text-muted-foreground">
            <Loader2 className="size-10 animate-spin text-primary" />
            <p className="text-lg font-medium">Loading businesses...</p>
          </div>
        ) : filteredShops.length > 0 ? (
          <div className="flex flex-col gap-6">
            <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
              <h2 className="text-2xl font-semibold">
                Found {filteredShops.length} business{filteredShops.length !== 1 ? "es" : ""}
              </h2>

              <div className="flex flex-col gap-3 sm:flex-row">
                <Select value={selectedCountry} onValueChange={setSelectedCountry}>
                  <SelectTrigger className="sm:w-[220px]">
                    <SelectValue placeholder="Country" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="all">All Countries</SelectItem>
                      {countries.map((country) => (
                        <SelectItem key={country} value={country}>
                          {country}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>

                <ToggleGroup
                  type="single"
                  value={viewMode}
                  onValueChange={(value) => {
                    if (value === "list" || value === "map") setViewMode(value);
                  }}
                  aria-label="View mode"
                >
                  <ToggleGroupItem value="list" aria-label="List view">
                    <List className="size-4" />
                    List
                  </ToggleGroupItem>
                  <ToggleGroupItem value="map" aria-label="Map view">
                    <Map className="size-4" />
                    Map
                  </ToggleGroupItem>
                </ToggleGroup>
              </div>
            </div>

            {viewMode === "map" ? (
              <MapView shops={filteredShops} />
            ) : (
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {filteredShops.map((shop) => (
                  <Card key={shop.id} className="flex h-full flex-col">
                    <CardContent className="flex flex-1 flex-col gap-4 p-5">
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="text-lg font-semibold leading-tight">{shop.name}</h3>
                        <Badge>{shop.shop_type}</Badge>
                      </div>
                      {shop.description && <p className="text-sm text-muted-foreground">{shop.description}</p>}
                      <div className="flex flex-col gap-2 text-sm text-muted-foreground">
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
                    </CardContent>
                    <CardFooter className="p-5 pt-0">
                      <Button className="w-full" onClick={() => navigate(`/queue/${shop.id}`)}>
                        Join Queue
                      </Button>
                    </CardFooter>
                  </Card>
                ))}
              </div>
            )}
          </div>
        ) : (
          !loading &&
          !error && (
            <div className="py-20 text-center">
              <h2 className="text-2xl font-semibold text-muted-foreground">No businesses found</h2>
              <p className="mt-2 text-muted-foreground">
                {searchTerm ? "Try a different search term" : "No businesses are registered yet"}
              </p>
            </div>
          )
        )}
      </section>
    </main>
  );
};

export default SearchPage;
