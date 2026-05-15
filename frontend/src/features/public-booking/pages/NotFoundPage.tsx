import React from "react";
import { Link as RouterLink } from "react-router-dom";
import { Scissors } from "lucide-react";
import { Button } from "@/components/ui/button";

const NotFoundPage: React.FC = () => {
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center px-4 text-center">
      <Scissors className="mb-4 size-14 text-muted-foreground" />
      <h1 className="text-5xl font-bold tracking-tight">404</h1>
      <h2 className="mt-3 text-2xl font-semibold">Page Not Found</h2>
      <p className="mt-2 text-muted-foreground">The page you're looking for doesn't exist or has been moved.</p>
      <Button asChild className="mt-6">
        <RouterLink to="/">Go to Homepage</RouterLink>
      </Button>
    </main>
  );
};

export default NotFoundPage;
