import CssBaseline from '@mui/material/CssBaseline';
import Stack from '@mui/material/Stack';
import Box from '@mui/material/Box';
import AppTheme from '../auth-shared-theme/AppTheme';
import SignInCard from './components/SignInCard';
import Content from './components/Content';
import { useThemeContext, gradientPresets } from '../../../../contexts/ThemeContext';
import { useTheme } from '@mui/material/styles';

export default function SignInSide(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props}>
      <CssBaseline enableColorScheme />
      <SignInSideContent />
    </AppTheme>
  );
}

function SignInSideContent() {
  const { dashboardGradient } = useThemeContext();
  const theme = useTheme();

  // Use the same gradient logic as the marketing page (Hero.tsx)
  const currentMode = theme.palette.mode === 'dark' ? 'dark' : 'light';
  const activeGradient = gradientPresets[dashboardGradient]?.[currentMode] || gradientPresets.violet[currentMode];

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
        direction="column"
        component="main"
        sx={{
          justifyContent: 'center',
          minHeight: '100vh',
        }}
      >
        <Stack
          direction={{ xs: 'column-reverse', md: 'row' }}
          sx={{
            justifyContent: 'center',
            gap: { xs: 6, sm: 12 },
            p: { xs: 2, sm: 4 },
            m: 'auto',
            maxWidth: 1200,
          }}
        >
          <Content />
          <SignInCard />
        </Stack>
      </Stack>
    </Box>
  );
}
