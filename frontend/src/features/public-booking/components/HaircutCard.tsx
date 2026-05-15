import React, { useState } from "react";
import { ChevronDown, Globe, Phone, Star } from "lucide-react";
import { HaircutService } from "../../../services/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface HaircutCardProps {
  haircut: HaircutService;
  onFavoriteRemoved?: (id: number) => void;
}

const HaircutCard: React.FC<HaircutCardProps> = ({ haircut }) => {
  const [expanded, setExpanded] = useState(false);
  const rating = Number(haircut.rating || 0);
  const filledStars = Math.max(0, Math.min(5, Math.round(rating)));

  return (
    <Card className="flex h-full flex-col overflow-hidden transition hover:-translate-y-1 hover:shadow-lg">
      <CardHeader className="bg-gradient-to-br from-primary/10 to-secondary/40">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="text-xl leading-tight">{haircut.name}</CardTitle>
          {haircut.price_range && (
            <Badge variant="outline" className="shrink-0 bg-background">
              {haircut.price_range}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <div className="flex items-center gap-0.5" aria-label={`Rating ${rating}`}>
            {Array.from({ length: 5 }).map((_, index) => (
              <Star
                key={index}
                className={cn(
                  "size-4",
                  index < filledStars ? "fill-primary text-primary" : "text-muted-foreground/40",
                )}
              />
            ))}
          </div>
          <span className="font-medium">{rating || "New"}</span>
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-4 pt-5">
        <div>
          <p className="font-medium">{haircut.address}</p>
          <p className="text-sm text-muted-foreground">
            {haircut.city}, {haircut.state} {haircut.zip_code}
          </p>
        </div>

        <div className="flex flex-wrap gap-3 text-sm font-medium">
          {haircut.phone && (
            <a className="inline-flex items-center gap-1.5 text-primary hover:underline" href={`tel:${haircut.phone}`}>
              <Phone className="size-4" />
              {haircut.phone}
            </a>
          )}
          {haircut.website && (
            <a
              className="inline-flex items-center gap-1.5 text-primary hover:underline"
              href={haircut.website}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Globe className="size-4" />
              Visit Website
            </a>
          )}
        </div>

        {expanded && haircut.hours && (
          <div className="rounded-lg border bg-muted/40 p-3">
            <p className="text-sm font-semibold">Hours of Operation</p>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{haircut.hours}</p>
          </div>
        )}
      </CardContent>

      {haircut.hours && (
        <CardFooter className="border-t p-3">
          <Button
            type="button"
            variant="ghost"
            className="w-full justify-between"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
          >
            Hours & Details
            <ChevronDown data-icon="inline-end" className={cn("transition-transform", expanded && "rotate-180")} />
          </Button>
        </CardFooter>
      )}
    </Card>
  );
};

export default HaircutCard;
