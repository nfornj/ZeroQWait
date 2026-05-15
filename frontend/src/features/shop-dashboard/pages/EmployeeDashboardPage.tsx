import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ListOrdered, MapPin, Phone, Store } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import api from "../../../services/api";
import { useAuth } from "../../../contexts/AuthContext";

interface Shop {
  id: number;
  name: string;
  description?: string;
  shop_type: string;
  address: string;
  city: string;
  state: string;
  phone: string;
}

const EmployeeDashboardPage: React.FC = () => {
  const [shops, setShops] = useState<Shop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetchMyShops();
  }, []);

  const fetchMyShops = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/employees/my-shops`);
      setShops(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load shops");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto flex min-h-[80vh] w-full max-w-6xl flex-col justify-center gap-4 p-6">
        <Skeleton className="h-12 w-72" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Welcome, {user?.username}!</h1>
        <p className="mt-1 text-sm text-muted-foreground">Manage queues for your assigned shops</p>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {shops.length === 0 ? (
        <Alert>
          <AlertDescription>
            You are not assigned to any shops yet. Contact your shop owner to get access.
          </AlertDescription>
        </Alert>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {shops.map((shop) => (
            <Card key={shop.id} className="h-full">
              <CardContent className="flex h-full flex-col gap-4 p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Store className="size-5 text-primary" />
                    <h2 className="font-semibold">{shop.name}</h2>
                  </div>
                  <Badge>{shop.shop_type}</Badge>
                </div>

                {shop.description && (
                  <p className="text-sm text-muted-foreground">{shop.description}</p>
                )}

                <div className="flex flex-col gap-2 text-sm text-muted-foreground">
                  <span className="flex items-center gap-2">
                    <MapPin className="size-4" />
                    {shop.address}, {shop.city}, {shop.state}
                  </span>
                  <span className="flex items-center gap-2">
                    <Phone className="size-4" />
                    {shop.phone}
                  </span>
                </div>

                <Button className="mt-auto w-full" onClick={() => navigate(`/dashboard?shop=${shop.id}`)}>
                  <ListOrdered data-icon="inline-start" />
                  Manage Queue
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default EmployeeDashboardPage;
