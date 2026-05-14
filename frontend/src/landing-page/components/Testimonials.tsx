import Card from '@mui/material/Card';
import CardHeader from '@mui/material/CardHeader';
import CardContent from '@mui/material/CardContent';
import Avatar from '@mui/material/Avatar';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid';
import { alpha } from '@mui/material/styles';

const userTestimonials = [
  {
    name: 'Sarah Jenkins',
    occupation: 'Salon Owner',
    outcome: 'Saved Sunday reporting time',
    testimonial:
      "I just tell ZeroQ ‘what's the revenue this week’ and it answers instantly. I used to spend Sunday evenings doing this in spreadsheets. Now I spend that time with my family.",
  },
  {
    name: 'Mark Thompson',
    occupation: 'Barber',
    outcome: 'Walk-ins handled during chair time',
    testimonial:
      "The AI Receptionist handles walk-ins while I’m cutting hair. It tells customers their wait time and I get a notification when I need to approve anything important. It’s like having a front-desk person I never have to train.",
  },
  {
    name: 'Dr. Emily Chen',
    occupation: 'Clinic Manager',
    outcome: 'Faster staff schedule decisions',
    testimonial:
      "The approval flow is brilliant. The HR agent proposed a new shift schedule and I just clicked approve. Takes 10 seconds. Patient throughput is up 40% since we stopped managing queues manually.",
  },
  {
    name: 'Michael Ross',
    occupation: 'Repair Shop Owner',
    outcome: 'Technicians stay on repairs',
    testimonial:
      "My technicians focus on repairs. The AI Receptionist manages the front. When a customer asks how long the wait is, ZeroQ tells them. Simple, accurate, no fuss.",
  },
  {
    name: 'Lisa Wong',
    occupation: 'Retail Manager',
    outcome: 'Instant service performance answers',
    testimonial:
      "I asked the Finance agent for our top-performing service last month and it responded in seconds with a full breakdown. The kind of insight that used to require a report from our analytics team.",
  },
  {
    name: 'David Miller',
    occupation: 'Gov. Office Admin',
    outcome: 'Queue setup approved in minutes',
    testimonial:
      "We approved the queue setup in five minutes. The Supervisor routes citizen requests to the right service window automatically. Our staff no longer manage a ticketing desk — the agent does it.",
  },
];


export default function Testimonials({ embedded = false }: { embedded?: boolean }) {
  return (
    <Container
      id="testimonials"
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
          display: embedded ? 'none' : 'block',
        }}
      >
        <Typography
          component="h2"
          variant="h4"
          gutterBottom
          sx={{ color: 'text.primary' }}
        >
          Testimonials
        </Typography>
        <Typography variant="body1" sx={{ color: 'text.secondary' }}>
          Shop owners across Canada trust their ZeroQwait AI agent team to run smoother
          operations and keep customers happy. Here&apos;s what they have to say.
        </Typography>
      </Box>

      {embedded ? (
        // EMBEDDED LAYOUT: Horizontal Scroll
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            overflowX: 'auto',
            pb: 2, // Space for scrollbar
            scrollSnapType: 'x mandatory',
            '&::-webkit-scrollbar': { display: 'none' },
            px: 1,
            mx: -2,
            width: 'calc(100% + 32px)',
          }}
        >
          {userTestimonials.map((testimonial, index) => (
            <Box
              key={index}
              sx={{
                minWidth: '280px',
                maxWidth: '280px',
                scrollSnapAlign: 'center',
                flexShrink: 0,
                display: 'flex',
              }}
            >
              <Card
                variant="outlined"
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  flexGrow: 1,
                  p: 1.5,
                  height: '100%',
                }}
              >
                <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                  <Typography
                    variant="body2" // Smaller font
                    gutterBottom
                    sx={{ color: 'text.secondary', minHeight: '80px' }} // Fixed min height for alignment
                  >
                    "{testimonial.testimonial}"
                  </Typography>
                  <Chip label={testimonial.outcome} size="small" sx={{ borderRadius: 999, mt: 1 }} />
                </CardContent>
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'row',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    mt: 1,
                    px: 1,
                  }}
                >
                  <CardHeader
                    avatar={<Avatar sx={{ bgcolor: '#1e88e5', color: 'common.white' }}>{testimonial.name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</Avatar>}
                    title={testimonial.name}
                    subheader={testimonial.occupation}
                    titleTypographyProps={{ variant: 'subtitle2' }}
                    subheaderTypographyProps={{ variant: 'caption' }}
                    sx={{ p: 0 }}
                  />
                  {/* Hide logo in embedded mode to save space/reduce clutter if needed, or keep smaller */}
                </Box>
              </Card>
            </Box>
          ))}
        </Box>
      ) : (
        // DEFAULT LAYOUT: Grid
        <Grid container spacing={2}>
          {userTestimonials.map((testimonial, index) => (
            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={index} sx={{ display: 'flex' }}>
              <Card
                variant="outlined"
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  flexGrow: 1,
                  borderRadius: 6,
                  background: (theme) => `linear-gradient(180deg, ${alpha(theme.palette.background.paper, 0.96)} 0%, ${alpha(theme.palette.background.default, 0.92)} 100%)`,
                }}
              >
                <CardContent>
                  <Chip label={testimonial.outcome} size="small" sx={{ mb: 1.5, borderRadius: 999 }} />
                  <Typography
                    variant="body1"
                    gutterBottom
                    sx={{ color: 'text.secondary' }}
                  >
                    {testimonial.testimonial}
                  </Typography>
                </CardContent>
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'row',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    px: 2,
                    pb: 2,
                  }}
                >
                  <CardHeader
                    avatar={<Avatar sx={{ bgcolor: '#1e88e5', color: 'common.white' }}>{testimonial.name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</Avatar>}
                    title={testimonial.name}
                    subheader={testimonial.occupation}
                    sx={{ p: 0 }}
                  />
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 700 }}>
                    Verified operator quote
                  </Typography>
                </Box>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Container>
  );
}
