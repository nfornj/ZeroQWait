import CssBaseline from '@mui/material/CssBaseline';
import Stack from '@mui/material/Stack';
import AppTheme from '../auth-shared-theme/AppTheme';
import SignInCard from './components/SignInCard';
import Content from './components/Content';

export default function SignInSide(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props} mode="dark">
      <CssBaseline enableColorScheme />
      <Stack
        direction="column"
        component="main"
        sx={[
          {
            justifyContent: 'center',
            height: '100vh',
            minHeight: '100%',
          },
          (theme) => ({
            backgroundImage:
              'radial-gradient(ellipse at 50% 50%, hsl(270, 50%, 25%), hsl(260, 60%, 8%))',
            backgroundRepeat: 'no-repeat',
            ...theme.applyStyles('light', {
              backgroundImage:
                'radial-gradient(ellipse at 50% 50%, hsl(210, 100%, 97%), hsl(0, 0%, 100%))',
            }),
          }),
        ]}
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
    </AppTheme>
  );
}
