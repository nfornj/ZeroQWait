import Card from '@mui/material/Card';
import CardHeader from '@mui/material/CardHeader';
import CardContent from '@mui/material/CardContent';
import Avatar from '@mui/material/Avatar';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid';
import { useColorScheme } from '@mui/material/styles';

const userTestimonials = [
  {
    avatar: <Avatar alt="Sarah Jenkins" src="/static/images/avatar/1.jpg" />,
    name: 'Sarah Jenkins',
    occupation: 'Salon Owner',
    testimonial:
      "I just tell ZeroQ ‘what's the revenue this week’ and it answers instantly. I used to spend Sunday evenings doing this in spreadsheets. Now I spend that time with my family.",
  },
  {
    avatar: <Avatar alt="Mark Thompson" src="/static/images/avatar/2.jpg" />,
    name: 'Mark Thompson',
    occupation: 'Barber',
    testimonial:
      "The AI Receptionist handles walk-ins while I’m cutting hair. It tells customers their wait time and I get a notification when I need to approve anything important. It’s like having a front-desk person I never have to train.",
  },
  {
    avatar: <Avatar alt="Dr. Emily Chen" src="/static/images/avatar/3.jpg" />,
    name: 'Dr. Emily Chen',
    occupation: 'Clinic Manager',
    testimonial:
      "The approval flow is brilliant. The HR agent proposed a new shift schedule and I just clicked approve. Takes 10 seconds. Patient throughput is up 40% since we stopped managing queues manually.",
  },
  {
    avatar: <Avatar alt="Michael Ross" src="/static/images/avatar/4.jpg" />,
    name: 'Michael Ross',
    occupation: 'Repair Shop Owner',
    testimonial:
      "My technicians focus on repairs. The AI Receptionist manages the front. When a customer asks how long the wait is, ZeroQ tells them. Simple, accurate, no fuss.",
  },
  {
    avatar: <Avatar alt="Lisa Wong" src="/static/images/avatar/5.jpg" />,
    name: 'Lisa Wong',
    occupation: 'Retail Manager',
    testimonial:
      "I asked the Finance agent for our top-performing service last month and it responded in seconds with a full breakdown. The kind of insight that used to require a report from our analytics team.",
  },
  {
    avatar: <Avatar alt="David Miller" src="/static/images/avatar/6.jpg" />,
    name: 'David Miller',
    occupation: 'Gov. Office Admin',
    testimonial:
      "We approved the queue setup in five minutes. The Supervisor routes citizen requests to the right service window automatically. Our staff no longer manage a ticketing desk — the agent does it.",
  },
];

const darkModeLogos = [
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/6560628e8573c43893fe0ace_Sydney-white.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/655f4d520d0517ae8e8ddf13_Bern-white.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/655f46794c159024c1af6d44_Montreal-white.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/61f12e891fa22f89efd7477a_TerraLight.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/6560a09d1f6337b1dfed14ab_colorado-white.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/655f5caa77bf7d69fb78792e_Ankara-white.svg',
];

const lightModeLogos = [
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/6560628889c3bdf1129952dc_Sydney-black.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/655f4d4d8b829a89976a419c_Bern-black.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/655f467502f091ccb929529d_Montreal-black.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/61f12e911fa22f2203d7514c_TerraDark.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/6560a0990f3717787fd49245_colorado-black.svg',
  'https://assets-global.website-files.com/61ed56ae9da9fd7e0ef0a967/655f5ca4e548b0deb1041c33_Ankara-black.svg',
];

const logoStyle = {
  width: '64px',
  opacity: 0.3,
};


export default function Testimonials({ embedded = false }: { embedded?: boolean }) {
  const { mode, systemMode } = useColorScheme();

  let logos: string[] = darkModeLogos;
  if (mode === 'system') {
    if (systemMode === 'light') {
      logos = lightModeLogos;
    } else {
      logos = darkModeLogos;
    }
  } else if (mode === 'light') {
    logos = lightModeLogos;
  } else {
    logos = darkModeLogos;
  }

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
                    avatar={testimonial.avatar}
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
                }}
              >
                <CardContent>
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
                  }}
                >
                  <CardHeader
                    avatar={testimonial.avatar}
                    title={testimonial.name}
                    subheader={testimonial.occupation}
                  />
                  <img
                    src={logos[index]}
                    alt={`Logo ${index + 1}`}
                    style={logoStyle}
                  />
                </Box>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Container>
  );
}
