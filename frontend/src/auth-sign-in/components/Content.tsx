import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import QueueIcon from '@mui/icons-material/Queue';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import PhoneAndroidIcon from '@mui/icons-material/PhoneAndroid';

const items = [
  {
    icon: <AccessTimeIcon sx={{ color: 'primary.main' }} />,
    title: 'Real-time Queue Management',
    description:
      'Monitor your queue in real-time. Customers can check wait times instantly and join remotely.',
  },
  {
    icon: <NotificationsActiveIcon sx={{ color: 'primary.main' }} />,
    title: 'Smart Notifications',
    description:
      'Automated SMS and email alerts keep your customers informed about their queue position.',
  },
  {
    icon: <PhoneAndroidIcon sx={{ color: 'primary.main' }} />,
    title: 'Mobile-First Experience',
    description:
      'Your customers can join queues, track wait times, and receive updates from anywhere.',
  },
  {
    icon: <QueueIcon sx={{ color: 'primary.main' }} />,
    title: 'Multi-Location Support',
    description:
      'Manage queues across multiple shop locations with a unified dashboard and analytics.',
  },
];

export default function Content() {
  return (
    <Stack
      sx={{ flexDirection: 'column', alignSelf: 'center', gap: 4, maxWidth: 450 }}
    >
      <Box sx={{ display: { xs: 'none', md: 'flex' }, alignItems: 'center', gap: 1 }}>
        <Typography variant="h3" component="div" sx={{ fontWeight: 'bold', color: 'primary.main', fontSize: '2.5rem' }}>
          ZeroQwait
        </Typography>
      </Box>
      {items.map((item, index) => (
        <Stack key={index} direction="row" sx={{ gap: 2 }}>
          {item.icon}
          <div>
            <Typography gutterBottom sx={{ fontWeight: 'medium' }}>
              {item.title}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {item.description}
            </Typography>
          </div>
        </Stack>
      ))}
    </Stack>
  );
}
