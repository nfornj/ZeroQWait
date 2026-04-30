import React, { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { alpha, Box, Chip, Stack, Typography, useTheme } from "@mui/material";
import { keyframes } from "@mui/material/styles";

const pulse = keyframes`
  0%   { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.45); }
  70%  { box-shadow: 0 0 0 14px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
`;

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
  const theme = useTheme();
  const d = data as unknown as BrainNodeData;
  const isDark = theme.palette.mode === "dark";

  return (
    <Box
      sx={{
        width: 188,
        borderRadius: 2.5,
        p: 1.25,
        border: "1px solid",
        borderColor: d.active ? alpha(d.color, 0.85) : alpha(d.color, 0.28),
        bgcolor: isDark
          ? alpha(d.color, d.active ? 0.22 : 0.1)
          : alpha("#ffffff", 0.96),
        boxShadow: d.active
          ? `0 6px 24px ${alpha(d.color, 0.35)}`
          : `0 2px 10px ${alpha("#000000", 0.06)}`,
        transition: "all 200ms ease",
        animation: d.active ? `${pulse} 1.8s ease-out infinite` : undefined,
        backdropFilter: "blur(6px)",
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
            border: `2px solid ${isDark ? "#0f172a" : "#ffffff"}`,
          }}
        />
      )}

      <Stack direction="row" spacing={1} alignItems="center" mb={0.75}>
        <Box
          sx={{
            width: 32,
            height: 32,
            borderRadius: 2,
            display: "grid",
            placeItems: "center",
            color: d.color,
            bgcolor: alpha(d.color, 0.16),
            flexShrink: 0,
          }}
        >
          {d.icon}
        </Box>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography variant="subtitle2" fontWeight={800} noWrap sx={{ lineHeight: 1.2 }}>
            {d.label}
          </Typography>
          <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block", lineHeight: 1.2 }}>
            {d.subtitle}
          </Typography>
        </Box>
      </Stack>

      <Chip
        size="small"
        label={d.status}
        sx={{
          height: 22,
          maxWidth: "100%",
          fontWeight: 600,
          color: d.active ? d.color : theme.palette.text.secondary,
          bgcolor: alpha(d.color, d.active ? 0.2 : 0.08),
          border: `1px solid ${alpha(d.color, d.active ? 0.4 : 0.15)}`,
          "& .MuiChip-label": { px: 1 },
        }}
      />

      {d.hasSource !== false && (
        <Handle
          type="source"
          position={Position.Right}
          style={{
            background: d.color,
            width: 8,
            height: 8,
            border: `2px solid ${isDark ? "#0f172a" : "#ffffff"}`,
          }}
        />
      )}
    </Box>
  );
};

export default memo(BrainNodeComponent);
