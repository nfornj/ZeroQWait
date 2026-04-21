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
    title: 'AI Receptionist',
    description:
      'Your shop gets a browser-based AI receptionist for customer questions, queue joins, and appointment requests.',
  },
  {
    icon: <NotificationsActiveIcon sx={{ color: 'primary.main' }} />,
    title: 'Owner Agent Workspace',
    description:
      'Owners can monitor approvals, queue activity, team updates, and day-to-day operations from one workspace.',
  },
  {
    icon: <PhoneAndroidIcon sx={{ color: 'primary.main' }} />,
    title: 'Mobile-First Experience',
    description:
      'Customers can join queues, view live progress, and book appointments directly from their phone browser.',
  },
  {
    icon: <QueueIcon sx={{ color: 'primary.main' }} />,
    title: 'Live Queue and Booking',
    description:
      'ZeroQwait supports live queue management, appointment booking flows, and service discovery across your shop pages.',
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
