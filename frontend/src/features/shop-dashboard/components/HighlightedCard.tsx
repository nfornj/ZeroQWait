import { ChevronRight, Lightbulb } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function HighlightedCard() {
  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <Lightbulb className="size-5 text-primary" />
        <CardTitle className="text-sm font-semibold">Explore your data</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground">
          Uncover performance and visitor insights with your operations data.
        </p>
        <Button type="button" size="sm" className="w-full sm:w-fit">
          Get insights
          <ChevronRight data-icon="inline-end" />
        </Button>
      </CardContent>
    </Card>
  );
}
