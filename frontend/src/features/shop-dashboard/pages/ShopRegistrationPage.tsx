import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import api from "../../../services/api";

const shopTypes = [
  { value: "barber", label: "Barber Shop" },
  { value: "salon", label: "Hair Salon" },
  { value: "doctor", label: "Doctor/Medical" },
  { value: "restaurant", label: "Restaurant" },
  { value: "spa", label: "Spa" },
  { value: "other", label: "Other" },
];

const countries = [
  "United States",
  "Canada",
  "United Kingdom",
  "Australia",
  "India",
  "Germany",
  "France",
  "Spain",
  "Italy",
  "Mexico",
  "Brazil",
  "Japan",
  "China",
  "South Korea",
  "Singapore",
  "Other",
];

const ShopRegistrationPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    shop_type: "barber",
    address: "",
    city: "",
    state: "",
    zip_code: "",
    country: "United States",
    phone: "",
    email: "",
    website: "",
    average_service_time: 30,
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const updateField = (name: string, value: string | number) => {
    setFormData((current) => ({ ...current, [name]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");

    try {
      const token = localStorage.getItem("token");
      if (!token) {
        navigate("/login");
        return;
      }

      await api.post(`/shops/`, formData);
      setSuccess(true);
      setTimeout(() => navigate("/dashboard"), 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create shop. Please try again.");
    }
  };

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10">
      <Card>
        <CardHeader className="text-center">
          <CardTitle className="text-3xl">Register Your Shop</CardTitle>
          <CardDescription>Create your shop profile and start managing your queue</CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {success && (
            <Alert className="mb-4">
              <AlertDescription>Shop created successfully! Redirecting to dashboard...</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="shop-name">Shop Name</Label>
              <Input id="shop-name" required value={formData.name} onChange={(event) => updateField("name", event.target.value)} />
            </div>

            <div className="flex flex-col gap-2">
              <Label>Shop Type</Label>
              <Select value={formData.shop_type} onValueChange={(value) => updateField("shop_type", value)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {shopTypes.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-2 md:col-span-2">
              <Label htmlFor="shop-description">Description</Label>
              <Textarea id="shop-description" rows={3} value={formData.description} onChange={(event) => updateField("description", event.target.value)} />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="shop-address">Address</Label>
              <Input id="shop-address" required value={formData.address} onChange={(event) => updateField("address", event.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="shop-city">City</Label>
              <Input id="shop-city" required value={formData.city} onChange={(event) => updateField("city", event.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="shop-state">State/Province/Region</Label>
              <Input id="shop-state" required value={formData.state} onChange={(event) => updateField("state", event.target.value)} />
              <p className="text-xs text-muted-foreground">e.g., ON, CA, TX</p>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="shop-zip">ZIP/Postal Code</Label>
              <Input id="shop-zip" required value={formData.zip_code} onChange={(event) => updateField("zip_code", event.target.value)} />
            </div>

            <div className="flex flex-col gap-2">
              <Label>Country</Label>
              <Select value={formData.country} onValueChange={(value) => updateField("country", value)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {countries.map((country) => (
                      <SelectItem key={country} value={country}>
                        {country}
                      </SelectItem>
                    ))}
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="shop-phone">Phone</Label>
              <Input id="shop-phone" required value={formData.phone} onChange={(event) => updateField("phone", event.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="shop-email">Email</Label>
              <Input id="shop-email" type="email" value={formData.email} onChange={(event) => updateField("email", event.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="shop-website">Website</Label>
              <Input id="shop-website" value={formData.website} onChange={(event) => updateField("website", event.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="service-time">Average Service Time (minutes)</Label>
              <Input
                id="service-time"
                required
                type="number"
                min={5}
                max={180}
                value={formData.average_service_time}
                onChange={(event) => updateField("average_service_time", Number(event.target.value))}
              />
            </div>

            <Button type="submit" size="lg" className="md:col-span-2">
              Create Shop
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

export default ShopRegistrationPage;
