import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import AddIcon from '@mui/icons-material/Add';
import TvIcon from '@mui/icons-material/Tv';
import QueueRoundedIcon from '@mui/icons-material/QueueRounded';
import PeopleRoundedIcon from '@mui/icons-material/PeopleRounded';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';
import api from '../../../services/api';
import { useNavigate } from 'react-router-dom';
import Header from '../components/Header';
import QueueDataGrid from '../components/QueueDataGrid';
import { useShop } from '../../../contexts/ShopContext';

const QueueManagementPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { shop: contextShop } = useShop();

  const [queues, setQueues] = useState<any[]>([]);
  const [shop, setShop] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const [newQueueName, setNewQueueName] = useState('');
  const [error, setError] = useState('');

  // Delete confirmation state
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);
  // Reset confirmation state
  const [resetConfirmId, setResetConfirmId] = useState<number | null>(null);

  useEffect(() => {
    fetchShopAndQueues();
  }, []);

  const fetchShopAndQueues = async () => {
    try {
      const shopRes = await api.get(`/shops/my-shops`);

      if (shopRes.data.length > 0) {
        const currentShop = shopRes.data[0];
        setShop(currentShop);

        const queueRes = await api.get(`/queues/shop/${currentShop.id}/all`);
        setQueues(queueRes.data);
      }
    } catch {
      // Keep UI usable even if initial fetch fails.
    }
  };

  const handleCreateQueue = async () => {
    try {
      setError('');
      await api.post(`/queues/shop/${shop.id}`, { name: newQueueName });
      setOpen(false);
      setNewQueueName('');
      fetchShopAndQueues();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create queue');
      setOpen(false);
    }
  };

  const handleDeleteQueue = async (id: number) => {
    try {
      await api.delete(`/queues/${id}`);
      setDeleteConfirmId(null);
      fetchShopAndQueues();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete queue');
      setDeleteConfirmId(null);
    }
  };

  const handleResetQueue = async (id: number) => {
    try {
      await api.post(`/queues/${id}/reset`, {});
      setResetConfirmId(null);
      fetchShopAndQueues();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset queue');
      setResetConfirmId(null);
    }
  };

  const activeQueues = queues.filter((q) => q.is_active).length;
  const brandPrimary = contextShop?.primary_color || shop?.primary_color || theme.palette.primary.main;
  const brandSecondary = contextShop?.secondary_color || shop?.secondary_color || brandPrimary;

  const queueNameForId = (id: number | null) => queues.find((q) => q.id === id)?.name ?? '';

  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      <Header />

      <Grid container spacing={2} sx={{ mb: 2 }}>
        <Grid size={{ xs: 12, lg: 8 }}>
          <Card variant="outlined" sx={{ borderRadius: 3 }}>
            <CardContent>
              <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} justifyContent="space-between">
                <Stack spacing={0.5}>
                  <Typography variant="h5" fontWeight={700}>Queue Operations</Typography>
                  <Typography color="text.secondary">
                    Manage your queues, launch public display modes, and monitor queue status in real time.
                  </Typography>
                </Stack>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => setOpen(true)}
                  sx={{ alignSelf: { xs: 'flex-start', md: 'center' } }}
                >
                  Create Queue
                </Button>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 4, lg: 1.33 }}>
          <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
            <CardContent>
              <Stack spacing={1}>
                <QueueRoundedIcon color="primary" />
                <Typography variant="h5" fontWeight={700}>{queues.length}</Typography>
                <Typography variant="body2" color="text.secondary">Total Queues</Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 4, lg: 1.33 }}>
          <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
            <CardContent>
              <Stack spacing={1}>
                <CheckCircleRoundedIcon color="success" />
                <Typography variant="h5" fontWeight={700}>{activeQueues}</Typography>
                <Typography variant="body2" color="text.secondary">Active Queues</Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, sm: 4, lg: 1.33 }}>
          <Card variant="outlined" sx={{ borderRadius: 3, height: '100%' }}>
            <CardContent>
              <Stack spacing={1}>
                <PeopleRoundedIcon color="secondary" />
                <Typography variant="h5" fontWeight={700}>{shop ? 1 : 0}</Typography>
                <Typography variant="body2" color="text.secondary">Connected Shops</Typography>
              </Stack>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {shop && (
        <Card
          variant="outlined"
          sx={{
            mb: 2,
            borderRadius: 3,
            borderColor: alpha(brandPrimary, 0.3),
            background: `linear-gradient(135deg, ${alpha(brandPrimary, 0.2)} 0%, ${alpha(brandSecondary, 0.15)} 100%)`,
            backdropFilter: 'blur(18px)',
          }}
        >
          <CardContent>
            <Stack spacing={1.5}>
              <Stack direction="row" spacing={1} alignItems="center">
                <TvIcon sx={{ color: brandPrimary }} />
                <Typography variant="subtitle1" fontWeight={700}>AI Public Shop Display</Typography>
              </Stack>
              <Typography variant="body2" sx={{ color: alpha(theme.palette.text.primary, 0.82) }}>
                Launch your public queue display or open the AI-powered customer experience surface.
              </Typography>
              <Divider />
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<TvIcon />}
                  onClick={() => window.open(`/display/${shop.id}`, '_blank')}
                  sx={{
                    color: brandPrimary,
                    borderColor: alpha(brandPrimary, 0.5),
                    bgcolor: alpha('#ffffff', theme.palette.mode === 'dark' ? 0.04 : 0.35),
                  }}
                >
                  Standard Display
                </Button>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<TvIcon />}
                  onClick={() => window.open(`/shop-ai/${shop.id}`, '_blank')}
                  sx={{
                    fontWeight: 700,
                    background: `linear-gradient(135deg, ${brandPrimary}, ${brandSecondary})`,
                    boxShadow: `0 10px 24px ${alpha(brandPrimary, 0.3)}`,
                    '&:hover': {
                      background: `linear-gradient(135deg, ${alpha(brandPrimary, 0.9)}, ${alpha(brandSecondary, 0.9)})`,
                    },
                  }}
                >
                  Launch AI Agent
                </Button>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      )}

      <Paper sx={{ width: '100%', overflow: 'hidden', borderRadius: 3 }} variant="outlined">
        <QueueDataGrid
          rows={queues}
          onEdit={(queue) => {
            console.log('Edit queue', queue);
          }}
          onDelete={(id) => setDeleteConfirmId(id)}
          onReset={(id) => setResetConfirmId(id)}
          onRowClick={(queue) => navigate(`/queues/${queue.id}`)}
        />
      </Paper>

      {/* Create queue dialog */}
      <Dialog open={open} onClose={() => setOpen(false)}>
        <DialogTitle>Create New Queue</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Queue Name"
            fullWidth
            value={newQueueName}
            onChange={(e) => setNewQueueName(e.target.value)}
            placeholder="e.g., Barber 2, Walk-ins"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateQueue} variant="contained">Create</Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog open={deleteConfirmId !== null} onClose={() => setDeleteConfirmId(null)}>
        <DialogTitle>Delete Queue</DialogTitle>
        <DialogContent>
          <Typography>
            Permanently delete <strong>{queueNameForId(deleteConfirmId)}</strong> and all its history? This cannot
            be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmId(null)}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={() => deleteConfirmId !== null && handleDeleteQueue(deleteConfirmId)}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Reset confirmation dialog */}
      <Dialog open={resetConfirmId !== null} onClose={() => setResetConfirmId(null)}>
        <DialogTitle>Reset Queue Data</DialogTitle>
        <DialogContent>
          <Typography>
            Remove all customers from <strong>{queueNameForId(resetConfirmId)}</strong>? The queue itself will
            remain, but all queue items (waiting, served, history) will be deleted.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setResetConfirmId(null)}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            onClick={() => resetConfirmId !== null && handleResetQueue(resetConfirmId)}
          >
            Reset
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default QueueManagementPage;
