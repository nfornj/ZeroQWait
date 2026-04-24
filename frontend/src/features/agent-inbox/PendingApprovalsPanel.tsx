import React, { useEffect, useMemo, useState } from "react";
import {
  alpha,
  Box,
  CardContent,
  Chip,
  Collapse,
  Divider,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";

import GlassCard from "../../components/GlassCard";
import useOwnerBrand from "../../hooks/useOwnerBrand";
import ApprovalCard from "./ApprovalCard";
import type { PendingApproval } from "./types";

interface PendingApprovalsPanelProps {
  approvals: PendingApproval[];
  isApproving: boolean;
  onDecision: (approval: PendingApproval, approved: boolean) => void;
}

const PendingApprovalsPanel: React.FC<PendingApprovalsPanelProps> = ({
  approvals,
  isApproving,
  onDecision,
}) => {
  const brand = useOwnerBrand();
  const [open, setOpen] = useState(true);
  const latestApprovals = useMemo(() => approvals.slice(0, 3), [approvals]);

  useEffect(() => {
    if (approvals.length > 0) {
      setOpen(true);
    }
  }, [approvals.length]);

  return (
    <GlassCard>
      <CardContent sx={{ py: 1.5 }}>
        <Stack spacing={1}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Pending Approvals</Typography>
            <Stack direction="row" spacing={0.75} alignItems="center">
              <Chip
                size="small"
                label={latestApprovals.length}
                sx={{
                  bgcolor: alpha(brand.primary, 0.14),
                  color: brand.primary,
                  border: `1px solid ${alpha(brand.primary, 0.22)}`,
                  fontWeight: 700,
                }}
              />
              <IconButton size="small" onClick={() => setOpen((prev) => !prev)} sx={{ color: brand.primary }}>
                <ExpandMoreRoundedIcon
                  sx={{
                    fontSize: 18,
                    transition: "transform 0.18s",
                    transform: open ? "rotate(180deg)" : "rotate(0deg)",
                  }}
                />
              </IconButton>
            </Stack>
          </Stack>
          <Divider sx={{ borderColor: alpha(brand.primary, 0.12) }} />
          <Collapse in={open} unmountOnExit>
            <Stack spacing={1.25}>
              {latestApprovals.length === 0 ? (
                <Box py={0.5}>
                  <Typography variant="body2" color="text.secondary">
                    No approvals are waiting right now.
                  </Typography>
                </Box>
              ) : (
                latestApprovals.map((approval) => (
                  <ApprovalCard
                    key={approval.action_id || `${approval.action}_${approval.shop_id}`}
                    approval={approval}
                    isSubmitting={isApproving}
                    onDecision={onDecision}
                  />
                ))
              )}
            </Stack>
          </Collapse>
        </Stack>
      </CardContent>
    </GlassCard>
  );
};

export default PendingApprovalsPanel;