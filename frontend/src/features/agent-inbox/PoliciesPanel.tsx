import React, { useState } from "react";
import {
  alpha,
  Box,
  Button,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";

import GlassCard from "../../components/GlassCard";
import useOwnerBrand from "../../hooks/useOwnerBrand";
import { labelForPolicyMode } from "./agentInboxShared";
import type { ShopPolicy } from "./types";

interface PoliciesPanelProps {
  policies: ShopPolicy[];
  savingPolicyKey: string | null;
  onModeChange: (policy: ShopPolicy, nextMode: string) => void;
  onRetry?: () => void;
}

const PoliciesPanel: React.FC<PoliciesPanelProps> = ({
  policies,
  savingPolicyKey,
  onModeChange,
  onRetry,
}) => {
  const brand = useOwnerBrand();
  const [open, setOpen] = useState(false);

  return (
    <GlassCard>
      <CardContent sx={{ py: 1.5 }}>
        <Stack spacing={1.25}>
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1}>
            <Box>
              <Typography variant="h6">Approval Policies</Typography>
              <Typography variant="body2" color="text.secondary">
                Choose what the agent team can run automatically for this shop.
              </Typography>
            </Box>
            <Stack direction="row" spacing={0.5} alignItems="center">
              {savingPolicyKey ? (
                <CircularProgress size={18} />
              ) : (
                <Chip
                  size="small"
                  label={`${policies.length} actions`}
                  sx={{
                    bgcolor: alpha(brand.primary, 0.14),
                    color: brand.primary,
                    border: `1px solid ${alpha(brand.primary, 0.22)}`,
                    fontWeight: 700,
                  }}
                />
              )}
              <IconButton size="small" onClick={() => setOpen((prev) => !prev)} sx={{ color: brand.primary }}>
                <ExpandMoreRoundedIcon
                  sx={{
                    transition: "transform 0.18s",
                    transform: open ? "rotate(180deg)" : "rotate(0deg)",
                  }}
                />
              </IconButton>
            </Stack>
          </Stack>
          <Collapse in={open} unmountOnExit>
            <Stack spacing={1.25}>
              <Divider sx={{ borderColor: alpha(brand.primary, 0.12) }} />
              {policies.length === 0 ? (
                <Stack spacing={1}>
                  <Typography variant="body2" color="text.secondary">
                    No approval policies are available for this shop yet.
                  </Typography>
                  {onRetry && (
                    <Button size="small" onClick={onRetry} sx={{ alignSelf: "flex-start" }}>
                      Retry
                    </Button>
                  )}
                </Stack>
              ) : (
                policies.map((policy) => {
                  const isSaving = savingPolicyKey === policy.policy_key;
                  return (
                    <Box
                      key={policy.policy_key}
                      sx={{
                        p: 1.25,
                        borderRadius: 2.5,
                        border: `1px solid ${alpha(brand.primary, 0.12)}`,
                        bgcolor: alpha(brand.primary, 0.04),
                      }}
                    >
                      <Stack spacing={1}>
                        <Stack direction={{ xs: "column", lg: "row" }} justifyContent="space-between" spacing={1}>
                          <Box sx={{ minWidth: 0 }}>
                            <Typography variant="subtitle2" sx={{ color: brand.primary }}>
                              {policy.title}
                            </Typography>
                            <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap" mt={0.5}>
                              <Chip size="small" variant="outlined" label={policy.category} />
                              <Chip size="small" variant="outlined" label={`${policy.risk_level || "medium"} risk`} />
                              <Chip
                                size="small"
                                variant="outlined"
                                label={
                                  policy.explicit
                                    ? "Custom mode"
                                    : `Default: ${labelForPolicyMode(policy.default_mode)}`
                                }
                              />
                            </Stack>
                          </Box>
                          <TextField
                            select
                            size="small"
                            label="Mode"
                            value={policy.mode}
                            disabled={isSaving}
                            onChange={(event) => onModeChange(policy, event.target.value)}
                            sx={{ minWidth: { xs: "100%", lg: 220 } }}
                          >
                            {(policy.supported_modes || []).map((mode) => (
                              <MenuItem key={mode} value={mode}>
                                {labelForPolicyMode(mode)}
                              </MenuItem>
                            ))}
                          </TextField>
                        </Stack>
                        <Typography variant="caption" color="text.secondary">
                          Current mode: {labelForPolicyMode(policy.mode)}
                          {isSaving ? " · Saving..." : ""}
                        </Typography>
                      </Stack>
                    </Box>
                  );
                })
              )}
            </Stack>
          </Collapse>
        </Stack>
      </CardContent>
    </GlassCard>
  );
};

export default PoliciesPanel;