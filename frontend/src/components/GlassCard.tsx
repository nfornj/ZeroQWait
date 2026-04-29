/**
 * Card wrapper that applies the shared owner-brand glass surface styling.
 */
import React from "react";
import Card from "@mui/material/Card";
import type { CardProps } from "@mui/material/Card";

import { useOwnerBrand } from "../hooks/useOwnerBrand";

const GlassCard = React.forwardRef<HTMLDivElement, CardProps>(function GlassCard(
  { sx, ...props },
  ref,
) {
  const brand = useOwnerBrand();

  return (
    <Card
      ref={ref}
      variant="outlined"
      sx={{
        borderRadius: 3,
        borderColor: brand.glass.border,
        bgcolor: brand.glass.bg,
        backdropFilter: "blur(20px)",
        ...sx,
      }}
      {...props}
    />
  );
});

export default GlassCard;