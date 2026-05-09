import { Check, Palette } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useThemeContext, GradientPreset, gradientPresets } from "../../../contexts/ThemeContext";

const presets: { id: GradientPreset; label: string }[] = [
  { id: "violet", label: "Violet Dream" },
  { id: "ocean", label: "Ocean Breeze" },
  { id: "sunset", label: "Golden Hour" },
  { id: "minimal", label: "Minimal White" },
];

const ThemeCustomizer: React.FC = () => {
  const { dashboardGradient, setDashboardGradient } = useThemeContext();

  return (
    <TooltipProvider>
      <DropdownMenu>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <Button type="button" variant="ghost" size="icon" aria-label="Customize theme">
                <Palette />
              </Button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent>Customize theme</TooltipContent>
        </Tooltip>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>Background Theme</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            {presets.map((preset) => (
              <DropdownMenuItem
                key={preset.id}
                onClick={() => setDashboardGradient(preset.id)}
                className="gap-3"
              >
                <span
                  className="size-5 rounded-full border"
                  style={{
                    background:
                      gradientPresets[preset.id].light === "none"
                        ? "hsl(var(--muted))"
                        : gradientPresets[preset.id].light,
                  }}
                />
                <span className="flex-1">{preset.label}</span>
                <Check className={cn("opacity-0", dashboardGradient === preset.id && "opacity-100")} />
              </DropdownMenuItem>
            ))}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </TooltipProvider>
  );
};

export default ThemeCustomizer;
