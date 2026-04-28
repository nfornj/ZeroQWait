import React from 'react';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CssBaseline from '@mui/material/CssBaseline';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { alpha, styled, useTheme } from '@mui/material/styles';
import AppTheme from './auth-shared-theme/AppTheme';
import Content from './auth-sign-in/components/Content';
import { gradientPresets, useThemeContext } from '../../../contexts/ThemeContext';

const AuthCard = styled(Card)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  width: '100%',
  maxWidth: 460,
  padding: theme.spacing(4),
  gap: theme.spacing(2),
  borderRadius: 24,
  border: `1px solid ${alpha(theme.palette.common.white, theme.palette.mode === 'dark' ? 0.14 : 0.45)}`,
  backgroundColor: alpha(theme.palette.background.paper, theme.palette.mode === 'dark' ? 0.9 : 0.82),
  backdropFilter: 'blur(18px)',
  boxShadow:
    theme.palette.mode === 'dark'
      ? '0 24px 60px rgba(2, 6, 23, 0.45)'
      : '0 24px 60px rgba(15, 23, 42, 0.16)',
}));

interface AuthPageShellProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  iconBgColor?: string;
  children: React.ReactNode;
}

function AuthPageShellContent({
  icon,
  title,
  description,
  iconBgColor = 'primary.main',
  children,
}: AuthPageShellProps) {
  const theme = useTheme();
  const { dashboardGradient, mode } = useThemeContext();
  const activeGradient = gradientPresets[dashboardGradient]?.[mode] || gradientPresets.violet[mode];

  return (
    <Box
      sx={{
        width: '100%',
        minHeight: '100vh',
        backgroundImage: activeGradient,
        backgroundRepeat: 'no-repeat',
        backgroundAttachment: 'fixed',
        transition: 'background 0.5s ease',
      }}
    >
      <Stack
        component="main"
        sx={{
          justifyContent: 'center',
          minHeight: '100vh',
          px: { xs: 2, sm: 4 },
          py: { xs: 3, sm: 4 },
        }}
      >
        <Stack
          direction={{ xs: 'column', md: 'row' }}
          sx={{
            justifyContent: 'center',
            alignItems: 'center',
            gap: { xs: 4, md: 10 },
            m: 'auto',
            width: '100%',
            maxWidth: 1180,
          }}
        >
          <Content />

          <AuthCard>
            <Stack spacing={1.5} alignItems="center" textAlign="center">
              <Avatar
                sx={{
                  width: 56,
                  height: 56,
                  bgcolor: iconBgColor,
                  boxShadow: `0 12px 28px ${alpha(theme.palette.common.black, theme.palette.mode === 'dark' ? 0.32 : 0.18)}`,
                }}
              >
                {icon}
              </Avatar>
              <Typography component="h1" variant="h4" fontWeight={700}>
                {title}
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ maxWidth: 360 }}>
                {description}
              </Typography>
            </Stack>

            {children}
          </AuthCard>
        </Stack>
      </Stack>
    </Box>
  );
}

export default function AuthPageShell(props: AuthPageShellProps) {
  return (
    <AppTheme>
      <CssBaseline enableColorScheme />
      <AuthPageShellContent {...props} />
    </AppTheme>
  );
}