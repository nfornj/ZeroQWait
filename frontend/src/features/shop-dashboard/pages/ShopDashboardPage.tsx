import React from "react";
import { Link as RouterLink } from "react-router-dom";
import { ExternalLink, Sparkles } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import Header from "../components/Header";
import MainGrid from "../components/MainGrid";

const ShopDashboardPage: React.FC = () => {
  return (
    <div className="flex w-full flex-col gap-4 px-3 pb-4">
      <Header />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-8">
          <CardContent className="p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">Operations Dashboard</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Live business metrics, queue trends, and performance widgets are active.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="gap-1.5">
                  <Sparkles className="size-3.5" />
                  Analytics workspace
                </Badge>
                <Button asChild>
                  <RouterLink to="/dashboard">
                    Open Live Dashboard
                    <ExternalLink data-icon="inline-end" />
                  </RouterLink>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Alert className="flex h-full items-center lg:col-span-4">
          <AlertDescription>
            Use the live dashboard for today view, operations summaries, and agent orchestration. This page remains
            the historical analytics workspace.
          </AlertDescription>
        </Alert>
      </div>

      <MainGrid />
    </div>
  );
};

export default ShopDashboardPage;
