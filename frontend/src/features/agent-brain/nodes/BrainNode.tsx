import React, { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";

import { Badge } from "@/components/ui/badge";

export interface BrainNodeData {
  label: string;
  subtitle: string;
  status: string;
  color: string;
  icon: React.ReactNode;
  active: boolean;
  hasTarget?: boolean;
  hasSource?: boolean;
  [key: string]: unknown;
}

const BrainNodeComponent: React.FC<NodeProps> = ({ data }) => {
  const d = data as unknown as BrainNodeData;

  return (
    <div
      className={d.active ? "brain-node-pulse w-[188px] rounded-xl border p-3 backdrop-blur transition-all" : "w-[188px] rounded-xl border p-3 backdrop-blur transition-all"}
      style={{
        borderColor: d.active ? d.color : `color-mix(in srgb, ${d.color} 28%, transparent)`,
        background: d.active
          ? `color-mix(in srgb, ${d.color} 18%, hsl(var(--card)))`
          : `color-mix(in srgb, ${d.color} 8%, hsl(var(--card)))`,
        boxShadow: d.active
          ? `0 6px 24px color-mix(in srgb, ${d.color} 35%, transparent)`
          : "0 2px 10px rgb(0 0 0 / 0.06)",
        ["--brain-node-color" as string]: d.color,
      }}
    >
      {d.hasTarget !== false && (
        <Handle
          type="target"
          position={Position.Left}
          style={{
            background: d.color,
            width: 8,
            height: 8,
            border: "2px solid hsl(var(--background))",
          }}
        />
      )}

      <div className="mb-2 flex items-center gap-2">
        <div
          className="grid size-8 shrink-0 place-items-center rounded-lg"
          style={{ color: d.color, background: `color-mix(in srgb, ${d.color} 16%, transparent)` }}
        >
          {d.icon}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold leading-tight">{d.label}</p>
          <p className="truncate text-xs leading-tight text-muted-foreground">{d.subtitle}</p>
        </div>
      </div>

      <Badge
        variant="outline"
        className="max-w-full truncate"
        style={{
          color: d.active ? d.color : undefined,
          background: `color-mix(in srgb, ${d.color} ${d.active ? 20 : 8}%, transparent)`,
          borderColor: `color-mix(in srgb, ${d.color} ${d.active ? 40 : 15}%, transparent)`,
        }}
      >
        {d.status}
      </Badge>

      {d.hasSource !== false && (
        <Handle
          type="source"
          position={Position.Right}
          style={{
            background: d.color,
            width: 8,
            height: 8,
            border: "2px solid hsl(var(--background))",
          }}
        />
      )}
    </div>
  );
};

export default memo(BrainNodeComponent);
