import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import { styled, alpha } from '@mui/material/styles';
import FloatingAIOrb from './FloatingAIOrb';

const HeroShell = styled(Box)(({ theme }) => ({
  position: 'relative',
  overflow: 'hidden',
  borderRadius: 40,
  padding: theme.spacing(3),
  background: theme.palette.mode === 'dark'
    ? 'linear-gradient(145deg, rgba(7,18,32,0.94) 0%, rgba(15,23,42,0.9) 48%, rgba(17,94,89,0.82) 100%)'
    : 'linear-gradient(145deg, rgba(255,248,241,0.98) 0%, rgba(238,247,255,0.95) 52%, rgba(226,244,238,0.98) 100%)',
  border: `1px solid ${alpha(theme.palette.divider, 0.6)}`,
  boxShadow: theme.palette.mode === 'dark'
    ? '0 28px 80px rgba(2, 8, 23, 0.45)'
    : '0 28px 80px rgba(148, 163, 184, 0.18)',
  [theme.breakpoints.up('md')]: {
    padding: theme.spacing(4),
  },
  '&::before': {
    content: '""',
    position: 'absolute',
    inset: 'auto auto -120px -100px',
    width: 320,
    height: 320,
    borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(255,107,87,0.24) 0%, rgba(255,107,87,0) 72%)',
  },
  '&::after': {
    content: '""',
    position: 'absolute',
    inset: '-120px -100px auto auto',
    width: 360,
    height: 360,
    borderRadius: '50%',
    background: 'radial-gradient(circle, rgba(30,136,229,0.18) 0%, rgba(30,136,229,0) 72%)',
  },
}));

const ShowcasePanel = styled(Box)(({ theme }) => ({
  position: 'relative',
  minHeight: 520,
  borderRadius: 32,
  padding: theme.spacing(2),
  background: theme.palette.mode === 'dark'
    ? 'linear-gradient(160deg, rgba(15,23,42,0.85) 0%, rgba(30,41,59,0.88) 100%)'
    : 'linear-gradient(160deg, rgba(255,255,255,0.88) 0%, rgba(241,245,249,0.92) 100%)',
  border: `1px solid ${alpha(theme.palette.divider, 0.45)}`,
  boxShadow: theme.palette.mode === 'dark'
    ? 'inset 0 1px 0 rgba(255,255,255,0.04)'
    : 'inset 0 1px 0 rgba(255,255,255,0.8)',
  [theme.breakpoints.up('md')]: {
    padding: theme.spacing(2.5),
  },
}));

export default function Hero() {
  const launchAssistant = () => {
    window.dispatchEvent(new CustomEvent('trigger-zeroq-assistant'));
  };

  const scrollToSection = (sectionId: string) => {
    const sectionElement = document.getElementById(sectionId);
    if (sectionElement) {
      const offset = 120;
      window.scrollTo({
        top: sectionElement.offsetTop - offset,
        behavior: 'smooth',
      });
    }
  };

  return (
    <Box
      id="hero"
      sx={(theme) => ({
        width: '100%',
        backgroundRepeat: 'no-repeat',
        backgroundImage: theme.palette.mode === 'dark'
          ? 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(30,136,229,0.24), transparent), linear-gradient(180deg, #020617 0%, #07111f 100%)'
          : 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(255,107,87,0.18), transparent), linear-gradient(180deg, #fffaf7 0%, #f6fbff 100%)',
      })}
    >
      <Container
        sx={{
          pt: { xs: 14, sm: 18 },
          pb: { xs: 8, sm: 10 },
        }}
      >
        <HeroShell>
          <Box
            sx={{
              position: 'relative',
              zIndex: 1,
              display: 'grid',
              gap: { xs: 4, md: 3 },
              alignItems: 'center',
              gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1.05fr) minmax(360px, 0.95fr)' },
            }}
          >
            <Stack spacing={{ xs: 2.5, md: 3 }}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25} alignItems={{ xs: 'flex-start', sm: 'center' }} flexWrap="wrap">
                <FloatingAIOrb />
                <Chip
                  icon={<SmartToyIcon sx={{ fontSize: 18 }} />}
                  label="AI agent team for service businesses"
                  sx={{
                    borderRadius: 999,
                    height: 34,
                    fontWeight: 700,
                    maxWidth: { xs: '100%', sm: 'none' },
                    bgcolor: (theme) => alpha(theme.palette.background.paper, 0.78),
                    backdropFilter: 'blur(12px)',
                  }}
                />
              </Stack>

              <Box>
                <Typography
                  variant="h1"
                  sx={{
                    fontSize: 'clamp(3rem, 8vw, 5.4rem)',
                    lineHeight: 0.94,
                    letterSpacing: '-0.06em',
                    fontWeight: 900,
                    maxWidth: 720,
                  }}
                >
                  Run the front desk, queue, and approvals from one AI operating layer.
                </Typography>
                <Typography
                  sx={{
                    mt: 2,
                    color: 'text.secondary',
                    maxWidth: 620,
                    fontSize: { xs: '1rem', md: '1.1rem' },
                    lineHeight: 1.7,
                  }}
                >
                  ZeroQwait gives every shop a receptionist, finance lead, and HR assistant that coordinate through conversation. Customers get instant answers. Owners keep approval control. Staff stop bouncing between tools.
                </Typography>
              </Box>

              <Stack direction="row" flexWrap="wrap" gap={1}>
                {['Receptionist', 'Finance', 'HR', 'Owner approvals'].map((label) => (
                  <Chip
                    key={label}
                    label={label}
                    sx={{
                      borderRadius: 999,
                      fontWeight: 700,
                      bgcolor: (theme) => alpha(theme.palette.background.paper, 0.72),
                    }}
                  />
                ))}
              </Stack>

              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} useFlexGap>
                <Button
                  variant="contained"
                  size="large"
                  href="/signup"
                  sx={{ borderRadius: 999, px: 3.25, py: 1.5, fontWeight: 800 }}
                >
                  Start free
                </Button>
                <Button
                  variant="outlined"
                  size="large"
                  onClick={launchAssistant}
                  sx={{ borderRadius: 999, px: 3.25, py: 1.5, fontWeight: 800 }}
                >
                  Talk to ZeroQ
                </Button>
                <Button
                  variant="text"
                  size="large"
                  onClick={() => scrollToSection('pricing')}
                  sx={{ borderRadius: 999, px: 1.5, py: 1.5, fontWeight: 700 }}
                >
                  View plans
                </Button>
              </Stack>

              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={{ xs: 1.5, sm: 3.5 }} useFlexGap>
                <Box>
                  <Typography variant="h4" sx={{ fontWeight: 900, letterSpacing: '-0.05em' }}>24/7</Typography>
                  <Typography color="text.secondary">customer-facing concierge</Typography>
                </Box>
                <Box>
                  <Typography variant="h4" sx={{ fontWeight: 900, letterSpacing: '-0.05em' }}>10 sec</Typography>
                  <Typography color="text.secondary">owner approval cycle</Typography>
                </Box>
                <Box>
                  <Typography variant="h4" sx={{ fontWeight: 900, letterSpacing: '-0.05em' }}>1 link</Typography>
                  <Typography color="text.secondary">for queue, bookings, and voice</Typography>
                </Box>
              </Stack>
            </Stack>

            <ShowcasePanel>
              <Stack spacing={2} sx={{ height: '100%' }}>
                <Card
                  elevation={0}
                  sx={{
                    borderRadius: 6,
                    p: 2.25,
                    color: 'common.white',
                    background: 'linear-gradient(145deg, #132238 0%, #0f5a7a 100%)',
                    boxShadow: '0 20px 40px rgba(15, 90, 122, 0.24)',
                  }}
                >
                  <Stack direction="row" justifyContent="space-between" spacing={2}>
                    <Box>
                      <Typography sx={{ fontSize: '0.72rem', letterSpacing: '0.16em', opacity: 0.72 }}>
                        LIVE OPS SNAPSHOT
                      </Typography>
                      <Typography variant="h4" sx={{ fontWeight: 800, mt: 1, letterSpacing: '-0.04em' }}>
                        148 customer requests handled today
                      </Typography>
                    </Box>
                    <Chip label="Owners approve high-impact actions" sx={{ bgcolor: alpha('#ffffff', 0.12), color: 'common.white' }} />
                  </Stack>
                </Card>

                <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1.1fr 0.9fr' } }}>
                  <Card elevation={0} sx={{ borderRadius: 6, p: 2.25, bgcolor: alpha('#ffffff', 0.82), backdropFilter: 'blur(12px)' }}>
                    <Typography sx={{ fontSize: '0.72rem', letterSpacing: '0.15em', color: 'text.secondary' }}>
                      RECEPTIONIST
                    </Typography>
                    <Typography variant="h6" sx={{ mt: 1, fontWeight: 800 }}>
                      Queue depth dropped from 11 to 4 after live slot routing.
                    </Typography>
                    <Stack spacing={1.2} sx={{ mt: 2 }}>
                      {[
                        'Queue wait updated in real time',
                        'Two walk-ins moved into free appointment slots',
                        'Customers notified automatically',
                      ].map((item) => (
                        <Box key={item} sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                          <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#ff6b57', mt: 0.8 }} />
                          <Typography color="text.secondary">{item}</Typography>
                        </Box>
                      ))}
                    </Stack>
                  </Card>

                  <Stack spacing={2}>
                    <Card elevation={0} sx={{ borderRadius: 6, p: 2.25, bgcolor: alpha('#0f172a', 0.92), color: 'common.white' }}>
                      <Typography sx={{ fontSize: '0.72rem', letterSpacing: '0.15em', opacity: 0.72 }}>
                        OWNER APPROVAL
                      </Typography>
                      <Typography variant="body1" sx={{ mt: 1.2, fontWeight: 700 }}>
                        “Close queue at 7:15 PM if active wait exceeds 45 minutes?”
                      </Typography>
                      <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                        <Chip label="Approve" sx={{ bgcolor: '#22c55e', color: '#052e16', fontWeight: 800 }} />
                        <Chip label="Ask follow-up" sx={{ bgcolor: alpha('#ffffff', 0.12), color: 'common.white' }} />
                      </Stack>
                    </Card>

                    <Card elevation={0} sx={{ borderRadius: 6, p: 2.25, bgcolor: alpha('#ffffff', 0.88) }}>
                      <Typography sx={{ fontSize: '0.72rem', letterSpacing: '0.15em', color: 'text.secondary' }}>
                        FINANCE + HR
                      </Typography>
                      <Typography variant="body2" sx={{ mt: 1, color: 'text.secondary', lineHeight: 1.7 }}>
                        Revenue summaries, payroll questions, staffing updates, and queue policy changes all happen in the same conversational workspace.
                      </Typography>
                    </Card>
                  </Stack>
                </Box>
              </Stack>
            </ShowcasePanel>
          </Box>
        </HeroShell>
      </Container>
    </Box >
  );
}
