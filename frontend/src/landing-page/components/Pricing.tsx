import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import Container from '@mui/material/Container';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { alpha } from '@mui/material/styles';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded';

const tiers = [
  {
    title: 'Starter',
    price: '0',
    eyebrow: 'Single location launch',
    description: [
      'Up to 1 shop',
      'AI Receptionist agent',
      'Live queue and appointment flows',
      'Public shop page',
      'Email support',
    ],
    summary: 'Get the public queue, appointment flow, and first AI receptionist live without setup friction.',
    buttonText: 'Launch one shop',
    buttonVariant: 'outlined',
    buttonColor: 'primary',
  },
  {
    title: 'Operations',
    subheader: 'Best for growing service teams',
    price: '29',
    eyebrow: 'Owner workspace included',
    description: [
      'Up to 5 shops',
      'Full AI agent team (Receptionist, Finance, HR)',
      'Human-in-the-Loop approvals',
      'Advanced analytics & revenue reports',
      'Priority support (24/7)',
      'Custom branding & colors',
    ],
    summary: 'The operating plan for shops that want approvals, reporting, staffing support, and customer AI in one place.',
    buttonText: 'Start operations plan',
    buttonVariant: 'contained',
    buttonColor: 'secondary',
  },
  {
    title: 'Scale',
    price: 'Contact',
    eyebrow: 'Multi-location rollout',
    description: [
      'Unlimited shops',
      'Dedicated onboarding',
      'Custom SLA & support',
      'Private deployment planning',
      'Multi-location rollout support',
      'Dedicated account manager',
    ],
    summary: 'For operators rolling out standardized workflows, governance, and reporting across several locations.',
    buttonText: 'Talk to sales',
    buttonVariant: 'outlined',
    buttonColor: 'primary',
  },
];


export default function Pricing({ embedded = false }: { embedded?: boolean }) {
  return (
    <Container
      id="pricing"
      sx={{
        pt: embedded ? 2 : { xs: 4, sm: 12 },
        pb: embedded ? 2 : { xs: 8, sm: 16 },
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: embedded ? 2 : { xs: 3, sm: 6 },
      }}
    >
      <Box
        sx={{
          width: { sm: '100%', md: '60%' },
          textAlign: { sm: 'left', md: 'center' },
          display: embedded ? 'none' : 'block', // Hide header text in embedded mode
        }}
      >
        <Typography
          component="h2"
          variant="h4"
          gutterBottom
          sx={{ color: 'text.primary' }}
        >
          Pricing
        </Typography>
        <Typography variant="body1" sx={{ color: 'text.secondary' }}>
          Every plan includes your own AI agent team. Pick the scale that matches your business
          and upgrade any time as you grow.
        </Typography>
        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 2 }}>
          <Chip label="Receptionist included" sx={{ borderRadius: 999 }} />
          <Chip label="Owner approvals" sx={{ borderRadius: 999 }} />
          <Chip label="Voice + queue flows" sx={{ borderRadius: 999 }} />
        </Stack>
      </Box>

      {embedded ? (
        // EMBEDDED LAYOUT: Horizontal Scroll
        // EMBEDDED LAYOUT: Responsive Flex Grid
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            gap: 2,
            width: '100%',
            pb: 2,
            px: 1,
          }}
        >
          {tiers.map((tier) => (
            <Box
              key={tier.title}
              sx={{
                flex: '1 1 280px', // Flexible width with min-width basis
                maxWidth: '400px', // Prevent becoming too wide on huge screens
                display: 'flex',
              }}
            >
              <Card
                sx={[
                  {
                    p: 2,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2,
                    width: '100%', // Ensure card fills flex item
                    height: '100%',
                    borderRadius: 6,
                    border: tier.title === 'Operations' ? '1px solid' : undefined,
                    borderColor: tier.title === 'Operations' ? 'primary.main' : undefined,
                  },
                  tier.title === 'Operations' &&
                  ((theme) => ({
                    background: `radial-gradient(circle at 50% 0%, ${alpha('#1e88e5', 0.36)}, hsl(220, 30%, 6%))`,
                    ...theme.applyStyles('dark', {
                      background: `radial-gradient(circle at 50% 0%, ${alpha('#1e88e5', 0.28)}, hsl(220, 30%, 16%))`,
                    }),
                  })),
                ]}
              >
                <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                  <Box
                    sx={[
                      {
                        mb: 1,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 2,
                      },
                      tier.title === 'Operations'
                        ? { color: 'grey.100' }
                        : { color: '' },
                    ]}
                  >
                    <Box>
                      <Typography variant="caption" sx={{ opacity: 0.72, letterSpacing: '0.14em' }}>
                        {tier.eyebrow}
                      </Typography>
                      <Typography component="h3" variant="h6">
                        {tier.title}
                      </Typography>
                    </Box>
                    {tier.title === 'Operations' && (
                      <Chip icon={<AutoAwesomeIcon />} label={tier.subheader} size="small" />
                    )}
                  </Box>
                  <Box
                    sx={[
                      {
                        display: 'flex',
                        alignItems: 'baseline',
                      },
                      tier.title === 'Operations'
                        ? { color: 'grey.50' }
                        : { color: null },
                    ]}
                  >
                    <Typography component="h3" variant="h4">
                      ${tier.price}
                    </Typography>
                    <Typography component="h3" variant="body2">
                      &nbsp; {tier.price === 'Contact' ? '' : '/mo'}
                    </Typography>
                  </Box>
                  <Typography
                    variant="body2"
                    sx={[
                      { mt: 1, mb: 1.25 },
                      tier.title === 'Operations' ? { color: 'grey.100' } : { color: 'text.secondary' },
                    ]}
                  >
                    {tier.summary}
                  </Typography>
                  <Divider sx={{ my: 1.5, opacity: 0.8, borderColor: 'divider' }} />
                  {tier.description.map((line) => (
                    <Box
                      key={line}
                      sx={{ py: 0.5, display: 'flex', gap: 1, alignItems: 'center' }}
                    >
                      <CheckCircleRoundedIcon
                        sx={[
                          {
                            width: 16,
                          },
                          tier.title === 'Operations'
                            ? { color: 'primary.light' }
                            : { color: 'primary.main' },
                        ]}
                      />
                      <Typography
                        variant="caption" // Smaller font
                        component={'span'}
                        sx={[
                          tier.title === 'Operations'
                            ? { color: 'grey.50' }
                            : { color: null },
                        ]}
                      >
                        {line}
                      </Typography>
                    </Box>
                  ))}
                </CardContent>
                <CardActions sx={{ p: 1, mt: 'auto' }}>
                  <Button
                    fullWidth
                    size="small"
                    variant={tier.buttonVariant as 'outlined' | 'contained'}
                    color={tier.buttonColor as 'primary' | 'secondary'}
                    sx={{ borderRadius: 999 }}
                  >
                    {tier.buttonText}
                  </Button>
                </CardActions>
              </Card>
            </Box>
          ))}
        </Box>
      ) : (
        // DEFAULT LAYOUT: Grid
        <Grid
          container
          spacing={3}
          sx={{ alignItems: 'center', justifyContent: 'center', width: '100%' }}
        >
          {tiers.map((tier) => (
            <Grid
              size={{ xs: 12, sm: tier.title === 'Enterprise' ? 12 : 6, md: 4 }}
              key={tier.title}
            >
              <Card
                sx={[
                  {
                    p: 2,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 4,
                    borderRadius: 6,
                  },
                  tier.title === 'Operations' &&
                  ((theme) => ({
                    border: 'none',
                    background: `radial-gradient(circle at 50% 0%, ${alpha('#1e88e5', 0.36)}, hsl(220, 30%, 6%))`,
                    boxShadow: `0 8px 12px hsla(220, 20%, 42%, 0.2)`,
                    ...theme.applyStyles('dark', {
                      background: `radial-gradient(circle at 50% 0%, ${alpha('#1e88e5', 0.28)}, hsl(220, 30%, 16%))`,
                      boxShadow: `0 8px 12px hsla(0, 0%, 0%, 0.8)`,
                    }),
                  })),
                ]}
              >
                <CardContent>
                  <Box
                    sx={[
                      {
                        mb: 1,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 2,
                      },
                      tier.title === 'Operations'
                        ? { color: 'grey.100' }
                        : { color: '' },
                    ]}
                  >
                    <Box>
                      <Typography variant="caption" sx={{ opacity: 0.72, letterSpacing: '0.14em' }}>
                        {tier.eyebrow}
                      </Typography>
                      <Typography component="h3" variant="h6">
                        {tier.title}
                      </Typography>
                    </Box>
                    {tier.title === 'Operations' && (
                      <Chip icon={<AutoAwesomeIcon />} label={tier.subheader} />
                    )}
                  </Box>
                  <Box
                    sx={[
                      {
                        display: 'flex',
                        alignItems: 'baseline',
                      },
                      tier.title === 'Operations'
                        ? { color: 'grey.50' }
                        : { color: null },
                    ]}
                  >
                    <Typography component="h3" variant="h2">
                      ${tier.price}
                    </Typography>
                    <Typography component="h3" variant="h6">
                      &nbsp; {tier.price === 'Contact' ? '' : 'per month'}
                    </Typography>
                  </Box>
                  <Typography
                    variant="body2"
                    sx={[
                      { mt: 1.25, mb: 1.5 },
                      tier.title === 'Operations' ? { color: 'grey.100' } : { color: 'text.secondary' },
                    ]}
                  >
                    {tier.summary}
                  </Typography>
                  <Divider sx={{ my: 2, opacity: 0.8, borderColor: 'divider' }} />
                  {tier.description.map((line) => (
                    <Box
                      key={line}
                      sx={{ py: 1, display: 'flex', gap: 1.5, alignItems: 'center' }}
                    >
                      <CheckCircleRoundedIcon
                        sx={[
                          {
                            width: 20,
                          },
                          tier.title === 'Operations'
                            ? { color: 'primary.light' }
                            : { color: 'primary.main' },
                        ]}
                      />
                      <Typography
                        variant="subtitle2"
                        component={'span'}
                        sx={[
                          tier.title === 'Operations'
                            ? { color: 'grey.50' }
                            : { color: null },
                        ]}
                      >
                        {line}
                      </Typography>
                    </Box>
                  ))}
                </CardContent>
                <CardActions>
                  <Button
                    fullWidth
                    variant={tier.buttonVariant as 'outlined' | 'contained'}
                    color={tier.buttonColor as 'primary' | 'secondary'}
                    sx={{ borderRadius: 999 }}
                  >
                    {tier.buttonText}
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Container>
  );
}
