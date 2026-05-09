import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { HaircutService, getFavorites } from "../../../services/api";
import { Alert, AlertDescription } from "@/components/ui/alert";
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
      } catch {
        setError("Failed to load favorites. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    void fetchFavorites();
  }, []);

  const handleFavoriteRemoved = (removedId: number) => {
    setFavorites((prev) => prev.filter((favorite) => favorite.id !== removedId));
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-10 md:px-6">
      <h1 className="text-3xl font-bold tracking-tight">My Favorite Haircut Services</h1>

      {error && (
        <Alert variant="destructive" className="mt-5">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="mt-8">
        {loading ? (
          <div className="flex justify-center py-16">
            <Loader2 className="size-8 animate-spin text-primary" />
          </div>
        ) : favorites.length > 0 ? (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {favorites.map((haircut) => (
              <HaircutCard key={haircut.id} haircut={haircut} onFavoriteRemoved={handleFavoriteRemoved} />
            ))}
          </div>
        ) : (
          <p className="py-16 text-center text-muted-foreground">
            You haven't saved any favorites yet. Start by searching for haircut services!
          </p>
        )}
      </div>
    </main>
  );
};

export default FavoritesPage;
