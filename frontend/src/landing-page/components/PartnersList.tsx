import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Grid from '@mui/material/Grid';
import { alpha } from '@mui/material/styles';

const sectors = [
  { name: 'Barbershops', detail: 'Walk-ins, fades, chair turnover', metric: 'Queue + appointments' },
  { name: 'Salons', detail: 'Longer sessions, multi-service visits', metric: 'Staff + booking coordination' },
  { name: 'Clinics', detail: 'Approval-sensitive front desk flow', metric: 'Patient wait visibility' },
  { name: 'Repair Shops', detail: 'Drop-offs, diagnostics, pickup updates', metric: 'Status and follow-ups' },
  { name: 'Auto Service', detail: 'Bay scheduling and service windows', metric: 'Ops inbox + approvals' },
  { name: 'Multi-location Groups', detail: 'Shared policy with local autonomy', metric: 'Finance and HR oversight' },
];

export default function PartnersList() {
  return (
    <Container id="logoCollection" sx={{ py: { xs: 5, md: 7 } }}>
      <Stack spacing={1.5} sx={{ mb: 3.5, textAlign: { xs: 'left', md: 'center' } }}>
        <Typography component="p" variant="overline" sx={{ color: 'text.secondary', letterSpacing: '0.18em' }}>
          BUILT FOR THE FRONT DESK
        </Typography>
        <Typography variant="h4" sx={{ fontWeight: 800, letterSpacing: '-0.04em' }}>
          One product, tuned for the service businesses that live on queue flow.
        </Typography>
        <Typography sx={{ color: 'text.secondary', maxWidth: 760, mx: { md: 'auto' } }}>
          ZeroQwait is designed for operators who need customer-facing AI, owner approvals, and live operational visibility in the same system.
        </Typography>
      </Stack>

      <Grid container spacing={2}>
        {sectors.map((sector) => (
          <Grid key={sector.name} size={{ xs: 12, sm: 6, md: 4 }}>
            <Card
              variant="outlined"
              sx={{
                height: '100%',
                p: 2.25,
                borderRadius: 5,
                background: (theme) => `linear-gradient(180deg, ${alpha(theme.palette.background.paper, 0.96)} 0%, ${alpha(theme.palette.background.default, 0.92)} 100%)`,
              }}
            >
              <Stack spacing={1.5}>
                <Chip label={sector.metric} sx={{ alignSelf: 'flex-start', borderRadius: 999, fontWeight: 700 }} />
                <Typography variant="h6" sx={{ fontWeight: 800 }}>
                  {sector.name}
                </Typography>
                <Typography color="text.secondary">
                  {sector.detail}
                </Typography>
              </Stack>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Container>
  );
}
