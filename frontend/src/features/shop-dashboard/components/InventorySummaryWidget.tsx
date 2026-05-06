import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Stack,
  Typography,
} from '@mui/material';
import InventoryRoundedIcon from '@mui/icons-material/InventoryRounded';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import CheckCircleOutlineRoundedIcon from '@mui/icons-material/CheckCircleOutlineRounded';
import ArrowForwardRoundedIcon from '@mui/icons-material/ArrowForwardRounded';
import { Link as RouterLink } from 'react-router-dom';
import { useShop } from '../../../contexts/ShopContext';
import { getInventoryItems, getLowStockAlerts, InventoryItem } from '../../../services/api';

export default function InventorySummaryWidget() {
  const { shop } = useShop();
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [alerts, setAlerts] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!shop?.id) return;
    setLoading(true);
    setError(false);
    Promise.all([
      getInventoryItems(shop.id),
      getLowStockAlerts(shop.id),
    ])
      .then(([itemsRes, alertsRes]) => {
        setItems(itemsRes.data.items);
        setAlerts(alertsRes.data.alerts);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [shop?.id]);

  const totalItems = items.length;
  const outCount = alerts.filter((i) => i.current_stock <= 0).length;
  const lowCount = alerts.filter((i) => i.current_stock > 0).length;
  const totalValue = items.reduce(
    (sum, i) => sum + i.current_stock * (i.cost_per_unit ?? 0),
    0,
  );

  const statusColor =
    outCount > 0 ? 'error' : lowCount > 0 ? 'warning' : 'success';
  const statusLabel =
    outCount > 0
      ? `${outCount} out of stock`
      : lowCount > 0
      ? `${lowCount} low stock`
      : 'All stocked';

  return (
    <Card
      variant="outlined"
      sx={{ borderRadius: 3, height: '100%', display: 'flex', flexDirection: 'column' }}
    >
      <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {/* Header */}
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          <Stack direction="row" alignItems="center" spacing={1}>
            <InventoryRoundedIcon color="primary" fontSize="small" />
            <Typography variant="subtitle1" fontWeight={700}>
              Inventory
            </Typography>
          </Stack>
          <Chip
            size="small"
            color={statusColor}
            icon={
              statusColor === 'success' ? (
                <CheckCircleOutlineRoundedIcon fontSize="small" />
              ) : (
                <WarningAmberRoundedIcon fontSize="small" />
              )
            }
            label={loading ? '…' : statusLabel}
            sx={{ fontWeight: 600 }}
          />
        </Stack>

        <Divider />

        {/* Stats row */}
        {loading ? (
          <Box display="flex" justifyContent="center" py={2}>
            <CircularProgress size={28} />
          </Box>
        ) : error ? (
          <Typography variant="body2" color="error">
            Failed to load inventory data.
          </Typography>
        ) : (
          <>
            <Stack direction="row" spacing={2}>
              <Box flex={1} textAlign="center">
                <Typography variant="h4" fontWeight={700}>
                  {totalItems}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Total items
                </Typography>
              </Box>
              <Box flex={1} textAlign="center">
                <Typography
                  variant="h4"
                  fontWeight={700}
                  color={alerts.length > 0 ? 'warning.main' : 'success.main'}
                >
                  {alerts.length}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Need restocking
                </Typography>
              </Box>
              <Box flex={1} textAlign="center">
                <Typography variant="h4" fontWeight={700}>
                  ${totalValue.toFixed(0)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Est. value
                </Typography>
              </Box>
            </Stack>

            {/* Low/out stock list */}
            {alerts.length > 0 && (
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                  Items needing attention
                </Typography>
                <Stack spacing={0.5}>
                  {alerts.slice(0, 4).map((item) => (
                    <Stack
                      key={item.id}
                      direction="row"
                      justifyContent="space-between"
                      alignItems="center"
                      sx={{
                        px: 1,
                        py: 0.4,
                        borderRadius: 1.5,
                        bgcolor: item.current_stock <= 0 ? 'error.light' : 'warning.light',
                        opacity: 0.9,
                      }}
                    >
                      <Typography variant="caption" fontWeight={600} noWrap sx={{ maxWidth: 160 }}>
                        {item.name}
                      </Typography>
                      <Chip
                        size="small"
                        label={
                          item.current_stock <= 0
                            ? 'Out'
                            : `${item.current_stock} ${item.unit}`
                        }
                        color={item.current_stock <= 0 ? 'error' : 'warning'}
                        sx={{ height: 18, fontSize: '0.68rem', fontWeight: 700 }}
                      />
                    </Stack>
                  ))}
                  {alerts.length > 4 && (
                    <Typography variant="caption" color="text.secondary" sx={{ pl: 1 }}>
                      +{alerts.length - 4} more…
                    </Typography>
                  )}
                </Stack>
              </Box>
            )}
          </>
        )}

        {/* Footer link */}
        <Box mt="auto" pt={1}>
          <Button
            component={RouterLink}
            to="/inventory"
            size="small"
            endIcon={<ArrowForwardRoundedIcon fontSize="small" />}
            sx={{ borderRadius: 2, fontWeight: 600, textTransform: 'none' }}
          >
            Manage inventory
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}
