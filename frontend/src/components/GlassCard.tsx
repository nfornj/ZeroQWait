import React from "react";
import { cn } from "../lib/utils";
import { useOwnerBrand } from "../hooks/useOwnerBrand";

interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(function GlassCard(
  { className, style, children, ...props },
  ref,
) {
  const brand = useOwnerBrand();

  return (
    <div
      ref={ref}
      className={cn("rounded-xl backdrop-blur-xl", className)}
      style={{
        border: `1px solid ${brand.glass.border}`,
        backgroundColor: brand.glass.bg,
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
});

export default GlassCard;
