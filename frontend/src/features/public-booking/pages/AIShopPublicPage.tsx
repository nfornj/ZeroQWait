import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Alert,
  Avatar,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  Divider,
  Grid,
  Paper,
  Stack,
  Typography,
  alpha,
} from '@mui/material';
import axios from 'axios';
import MasterAIAgent from '../../../landing-page/components/MasterAIAgent';

interface AIShopPublicPageProps {
  shopSlug?: string;
}

interface QueueItem {
  id: number;
  customer_name: string;
  position: number;
  status: string;
  checked_in_at: string;
}

interface WaitEstimate {
  position: number;
  people_ahead: number;
  estimated_wait_minutes: number;
  status: string;
}

interface LiveMetrics {
  estimated_wait_minutes: number;
  queue_length: number;
  people_waiting: number;
  people_being_served: number;
  active_employees: number;
  parallel_queues: number;
  effective_service_time_minutes: number;
  efficiency_factor: number;
  confidence: 'low' | 'medium' | 'high';
}

const AIShopPublicPage: React.FC<AIShopPublicPageProps> = ({ shopSlug }) => {
  const { shopId } = useParams<{ shopId: string }>();
  const effectiveId = shopSlug || shopId;

  const [shop, setShop] = useState<any>(null);
  const [queueItems, setQueueItems] = useState<QueueItem[]>([]);
  const [myQueueItem, setMyQueueItem] = useState<QueueItem | null>(null);
  const [waitEstimate, setWaitEstimate] = useState<WaitEstimate | null>(null);
  const [liveMetrics, setLiveMetrics] = useState<LiveMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const waitingCustomers = useMemo(
    () =>
      queueItems
        .filter((item) => item.status === 'waiting' || item.status === 'being_served')
        .sort((a, b) => (a.position || 0) - (b.position || 0)),
    [queueItems],
  );

  useEffect(() => {
    const fetchShopData = async () => {
      if (!effectiveId) {
        setError('Shop not found');
        setLoading(false);
        return;
      }

      try {
        const isSlug = isNaN(Number(effectiveId));
        const endpoint = isSlug ? `/shops/s/${effectiveId}` : `/shops/${effectiveId}`;
        const response = await axios.get(endpoint);
        setShop(response.data);
      } catch (_err) {
        setError('Could not load shop details');
      } finally {
        setLoading(false);
      }
    };

    void fetchShopData();
  }, [effectiveId]);

  useEffect(() => {
    if (!shop?.id) return;

    const fetchQueue = async () => {
      try {
        const response = await axios.get(`/queues/shop/${shop.id}/active`);
        const items: QueueItem[] = response.data?.queue_items || [];
        setQueueItems(items);

        try {
          const metricsRes = await axios.get(`/queues/shop/${shop.id}/live-metrics`);
          setLiveMetrics(metricsRes.data as LiveMetrics);
        } catch {
          // keep previous metrics if temporary failure
        }

        const savedItemId =
          localStorage.getItem(`queue_item_${shop.id}`) ||
          (shopId ? localStorage.getItem(`queue_item_${shopId}`) : null);

        if (!savedItemId) {
          setMyQueueItem(null);
          return;
        }

        const numericId = parseInt(savedItemId, 10);
        const found = items.find((i) => i.id === numericId);

        if (found) {
          setMyQueueItem(found);
          localStorage.setItem(`queue_item_${shop.id}`, String(numericId));
          return;
        }

        try {
          const checkRes = await axios.get(`/queues/items/${numericId}/estimate`);
          if (checkRes.data && checkRes.data.status !== 'completed' && checkRes.data.status !== 'cancelled') {
            setMyQueueItem({
              id: numericId,
              customer_name: 'You',
              position: checkRes.data.position,
              status: checkRes.data.status,
              checked_in_at: new Date().toISOString(),
            });
          } else {
            setMyQueueItem(null);
          }
        } catch {
          setMyQueueItem(null);
        }
      } catch {
        // keep previous state; polling will retry
      }
    };

    void fetchQueue();
    const interval = setInterval(fetchQueue, 5000);
    return () => clearInterval(interval);
  }, [shop?.id, shopId]);

  useEffect(() => {
    if (!myQueueItem?.id) {
      setWaitEstimate(null);
      return;
    }

    const fetchEstimate = async () => {
      try {
        const response = await axios.get(`/queues/items/${myQueueItem.id}/estimate`);
        setWaitEstimate(response.data);
      } catch {
        // retry on next poll
      }
    };

    void fetchEstimate();
    const interval = setInterval(fetchEstimate, 10000);
    return () => clearInterval(interval);
  }, [myQueueItem?.id]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !shop) {
    return (
      <Container maxWidth="sm" sx={{ mt: 10 }}>
        <Alert severity="error">{error || 'Shop not found'}</Alert>
      </Container>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: '#f6f7fb', py: { xs: 1.5, md: 2.5 } }}>
      <Container maxWidth="xl">
        <Paper
          elevation={0}
          sx={{
            mb: 2,
            px: { xs: 2, md: 3 },
            py: 1.5,
            borderRadius: '16px',
            border: '1px solid',
            borderColor: 'divider',
            bgcolor: 'background.paper',
          }}
        >
          <Stack direction="row" spacing={1.5} alignItems="center" divider={<Divider orientation="vertical" flexItem />}>
            <Typography sx={{ color: 'primary.main', fontWeight: 800 }}>ZeroQwait</Typography>
            <Typography sx={{ fontWeight: 700 }}>{shop.name}</Typography>
            <Typography variant="body2" color="text.secondary">
              {[shop.city, shop.shop_type].filter(Boolean).join(' • ')}
            </Typography>
          </Stack>
        </Paper>

        <Grid container spacing={2}>
          <Grid size={{ xs: 12, lg: 5 }}>
            <Stack spacing={2}>
              <Card sx={{ borderRadius: '18px' }}>
                <CardContent>
                  <Typography variant="overline" sx={{ color: 'text.secondary', fontWeight: 700 }}>
                    LIVE QUEUE STATUS
                  </Typography>
                  {myQueueItem ? (
                    <Box sx={{ mt: 1 }}>
                      <Typography variant="h4" sx={{ fontWeight: 900, lineHeight: 1 }}>
                        #{waitEstimate?.position ?? myQueueItem.position}
                      </Typography>
                      <Typography variant="body1" sx={{ fontWeight: 700, mt: 0.5 }}>
                        You are in the queue
                      </Typography>
                      <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                        <Chip
                          color="warning"
                          variant="outlined"
                          label={`Ahead: ${waitEstimate?.people_ahead ?? '-'}`}
                        />
                        <Chip
                          color="success"
                          label={`ETA: ${waitEstimate?.estimated_wait_minutes ?? liveMetrics?.estimated_wait_minutes ?? '-'} min`}
                        />
                      </Stack>
                      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                        <Chip
                          size="small"
                          variant="outlined"
                          label={`Employees: ${liveMetrics?.active_employees ?? '-'}`}
                        />
                        <Chip
                          size="small"
                          variant="outlined"
                          label={`Queues: ${liveMetrics?.parallel_queues ?? '-'}`}
                        />
                        <Chip
                          size="small"
                          color={liveMetrics?.confidence === 'high' ? 'success' : liveMetrics?.confidence === 'medium' ? 'warning' : 'default'}
                          label={`Confidence: ${liveMetrics?.confidence ?? '-'}`}
                        />
                      </Stack>
                    </Box>
                  ) : (
                    <Box sx={{ mt: 1.5 }}>
                      <Typography variant="h6" sx={{ fontWeight: 800 }}>
                        Not Enrolled Yet
                      </Typography>
                      <Typography color="text.secondary">
                        Use the AI panel to the right to join the queue instantly.
                      </Typography>
                      <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                        <Chip color="primary" label={`Live ETA: ${liveMetrics?.estimated_wait_minutes ?? '-'} min`} />
                        <Chip variant="outlined" label={`Waiting: ${liveMetrics?.people_waiting ?? waitingCustomers.length}`} />
                      </Stack>
                      <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                        AI model factors: active staff, parallel queues, historical service analytics, and real-time throughput.
                      </Typography>
                    </Box>
                  )}
                </CardContent>
              </Card>

              <Card sx={{ borderRadius: '18px' }}>
                <CardContent>
                  <Typography variant="h6" sx={{ fontWeight: 800, mb: 1.5 }}>
                    Active Queue
                  </Typography>
                  {waitingCustomers.length === 0 ? (
                    <Typography color="text.secondary">Queue is currently empty.</Typography>
                  ) : (
                    <Stack spacing={1}>
                      {waitingCustomers.slice(0, 8).map((item) => {
                        const isMe = myQueueItem?.id === item.id;
                        return (
                          <Box
                            key={item.id}
                            sx={{
                              p: 1.25,
                              borderRadius: '12px',
                              border: '1px solid',
                              borderColor: isMe ? 'primary.main' : 'divider',
                              bgcolor: isMe ? alpha('#1976d2', 0.06) : 'background.paper',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                            }}
                          >
                            <Stack direction="row" spacing={1.25} alignItems="center">
                              <Avatar sx={{ width: 30, height: 30, fontSize: '0.75rem' }}>
                                {isMe ? 'Y' : '?'}
                              </Avatar>
                              <Box>
                                <Typography sx={{ fontWeight: 700 }}>#{item.position}</Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {isMe ? 'You' : 'Customer'}
                                </Typography>
                              </Box>
                            </Stack>
                            <Chip
                              size="small"
                              label={item.status === 'being_served' ? 'SERVING' : 'WAITING'}
                              color={item.status === 'being_served' ? 'success' : 'warning'}
                              variant={item.status === 'being_served' ? 'filled' : 'outlined'}
                            />
                          </Box>
                        );
                      })}
                    </Stack>
                  )}
                </CardContent>
              </Card>
            </Stack>
          </Grid>

          <Grid size={{ xs: 12, lg: 7 }}>
            <Box sx={{ height: { xs: '78vh', lg: '86vh' } }}>
              <MasterAIAgent
                forceOpen={true}
                hideCloseButton={true}
                initialInteractionMode="voice"
                embedded={true}
                shopContext={{
                  id: shop.id,
                  slug: shop.slug,
                  name: shop.name,
                  city: shop.city,
                  shopType: shop.shop_type,
                }}
              />
            </Box>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default AIShopPublicPage;
