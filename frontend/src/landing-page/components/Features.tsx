import * as React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Divider from '@mui/material/Divider';
import MuiChip from '@mui/material/Chip';
import Container from '@mui/material/Container';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { alpha, styled } from '@mui/material/styles';

import DevicesRoundedIcon from '@mui/icons-material/DevicesRounded';
import EdgesensorHighRoundedIcon from '@mui/icons-material/EdgesensorHighRounded';
import ViewQuiltRoundedIcon from '@mui/icons-material/ViewQuiltRounded';

const items = [
  {
    icon: <ViewQuiltRoundedIcon />,
    title: 'AI Supervisor',
    description:
      'Your Supervisor agent interprets your instructions and routes tasks to the right specialist — Receptionist, Finance, or HR — then asks for your approval before any high-impact action.',
    accent: '#1e88e5',
    eyebrow: 'CONTROL LAYER',
    highlights: ['Classifies owner requests', 'Triggers approvals before impact', 'Keeps specialist agents aligned'],
    metrics: ['3 active specialists', '2 approvals pending', '24 actions resolved today'],
  },
  {
    icon: <EdgesensorHighRoundedIcon />,
    title: 'Customer Receptionist',
    description:
      'Your AI Receptionist greets walk-ins, manages your live queue, and handles bookings — via link, QR code, or voice. No app required.',
    accent: '#ff6b57',
    eyebrow: 'CUSTOMER DESK',
    highlights: ['Handles queue intake by voice or text', 'Explains services and current wait times', 'Collects appointment and contact details'],
    metrics: ['4 customers waiting', 'ETA 22 min', 'Voice + chat ready'],
  },
  {
    icon: <DevicesRoundedIcon />,
    title: 'Finance & HR Agents',
    description:
      'Ask your Finance agent for yesterday\'s revenue or this week\'s report. Tell your HR agent to update a shift. Get answers and take action in plain language.',
    accent: '#16a34a',
    eyebrow: 'BACK OFFICE',
    highlights: ['Summarizes revenue and service mix', 'Tracks staffing and shift changes', 'Keeps business actions in one conversation thread'],
    metrics: ['$4.8k revenue today', '6 staff on schedule', '1 payroll question resolved'],
  },
];

interface ChipProps {
  selected?: boolean;
}

const Chip = styled(MuiChip)<ChipProps>(({ theme }) => ({
  variants: [
    {
      props: ({ selected }) => !!selected,
      style: {
        background:
          'linear-gradient(to bottom right, hsl(210, 98%, 48%), hsl(210, 98%, 35%))',
        color: 'hsl(0, 0%, 100%)',
        borderColor: (theme.vars || theme).palette.primary.light,
        '& .MuiChip-label': {
          color: 'hsl(0, 0%, 100%)',
        },
        ...theme.applyStyles('dark', {
          borderColor: (theme.vars || theme).palette.primary.dark,
        }),
      },
    },
  ],
}));

interface MobileLayoutProps {
  selectedItemIndex: number;
  handleItemClick: (index: number) => void;
  selectedFeature: (typeof items)[0];
}

function FeaturePreview({ item }: { item: (typeof items)[0] }) {
  return (
    <Box
      sx={{
        height: '100%',
        p: { xs: 2, sm: 2.5, md: 3 },
        borderRadius: 6,
        background: (theme) => theme.palette.mode === 'dark'
          ? `linear-gradient(160deg, ${alpha(item.accent, 0.22)} 0%, rgba(15,23,42,0.92) 62%)`
          : `linear-gradient(160deg, ${alpha(item.accent, 0.12)} 0%, rgba(255,255,255,0.94) 62%)`,
      }}
    >
      <Stack spacing={2} sx={{ height: '100%' }}>
        <Box>
          <Typography sx={{ fontSize: '0.72rem', letterSpacing: '0.18em', color: 'text.secondary' }}>
            {item.eyebrow}
          </Typography>
          <Typography variant="h5" sx={{ mt: 1, fontWeight: 800, letterSpacing: '-0.03em' }}>
            {item.title}
          </Typography>
          <Typography variant="body2" sx={{ mt: 1.2, color: 'text.secondary', maxWidth: 420 }}>
            {item.description}
          </Typography>
        </Box>

        <Stack spacing={1.1}>
          {item.highlights.map((highlight) => (
            <Box key={highlight} sx={{ display: 'flex', gap: 1.2, alignItems: 'flex-start' }}>
              <Box sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: item.accent, mt: 0.7, flexShrink: 0 }} />
              <Typography variant="body2" color="text.secondary">
                {highlight}
              </Typography>
            </Box>
          ))}
        </Stack>

        <Divider />

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' }, gap: 1.5 }}>
          {item.metrics.map((metric) => (
            <Card key={metric} variant="outlined" sx={{ p: 1.5, borderRadius: 4, bgcolor: (theme) => alpha(theme.palette.background.paper, 0.72) }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{metric}</Typography>
            </Card>
          ))}
        </Box>
      </Stack>
    </Box>
  );
}

export function MobileLayout({
  selectedItemIndex,
  handleItemClick,
  selectedFeature,
}: MobileLayoutProps) {
  if (!items[selectedItemIndex]) {
    return null;
  }

  return (
    <Box
      sx={{
        display: { xs: 'flex', sm: 'none' },
        flexDirection: 'column',
        gap: 2,
      }}
    >
      <Box sx={{ display: 'flex', gap: 2, overflow: 'auto' }}>
        {items.map(({ title }, index) => (
          <Chip
            size="medium"
            key={index}
            label={title}
            onClick={() => handleItemClick(index)}
            selected={selectedItemIndex === index}
          />
        ))}
      </Box>
      <Card variant="outlined">
        <FeaturePreview item={selectedFeature} />
      </Card>
    </Box>
  );
}

export default function Features({ embedded = false }: { embedded?: boolean }) {
  const [selectedItemIndex, setSelectedItemIndex] = React.useState(0);

  const handleItemClick = (index: number) => {
    setSelectedItemIndex(index);
  };

  const selectedFeature = items[selectedItemIndex];

  return (
    <Container id="features" sx={{ py: embedded ? 2 : { xs: 8, sm: 16 } }}>
      <Box sx={{ width: { sm: '100%', md: '60%' } }}>
        <Typography
          component="h2"
          variant="h4"
          gutterBottom
          sx={{ color: 'text.primary' }}
        >
          Your Dedicated AI Agent Team
        </Typography>
        <Typography
          variant="body1"
          sx={{ color: 'text.secondary', mb: { xs: 2, sm: 4 } }}
        >
          Stop juggling apps and spreadsheets. ZeroQwait gives every shop a team of specialized
          AI agents that handle queues, analytics, and staff — all operated through natural
          conversation.
        </Typography>
      </Box>
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', md: 'row-reverse' },
          gap: 2,
        }}
      >
        <div>
          <Box
            sx={{
              display: { xs: 'none', sm: 'flex' },
              flexDirection: 'column',
              gap: 2,
              height: '100%',
            }}
          >
            {items.map(({ icon, title, description }, index) => (
              <Box
                key={index}
                component={Button}
                onClick={() => handleItemClick(index)}
                sx={[
                  (theme) => ({
                    p: 2,
                    height: '100%',
                    width: '100%',
                    borderRadius: 5,
                    '&:hover': {
                      backgroundColor: (theme.vars || theme).palette.action.hover,
                    },
                  }),
                  selectedItemIndex === index && {
                    backgroundColor: 'action.selected',
                  },
                ]}
              >
                <Box
                  sx={[
                    {
                      width: '100%',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'left',
                      gap: 1,
                      textAlign: 'left',
                      textTransform: 'none',
                      color: 'text.secondary',
                    },
                    selectedItemIndex === index && {
                      color: 'text.primary',
                    },
                  ]}
                >
                  {icon}

                  <Typography variant="h6">{title}</Typography>
                  <Typography variant="body2">{description}</Typography>
                </Box>
              </Box>
            ))}
          </Box>
          <MobileLayout
            selectedItemIndex={selectedItemIndex}
            handleItemClick={handleItemClick}
            selectedFeature={selectedFeature}
          />
        </div>
        <Box
          sx={{
            display: { xs: 'none', sm: 'flex' },
            width: { xs: '100%', md: '70%' },
            minHeight: 500,
          }}
        >
          <Card
            variant="outlined"
            sx={{
              height: '100%',
              width: '100%',
              display: { xs: 'none', sm: 'flex' },
              pointerEvents: 'none',
              borderRadius: 6,
            }}
          >
            <FeaturePreview item={selectedFeature} />
          </Card>
        </Box>
      </Box>
    </Container>
  );
}
