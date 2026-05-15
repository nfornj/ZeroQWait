import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../../../../../components/ui/button';
import { Input } from '../../../../../components/ui/input';
import { Label } from '../../../../../components/ui/label';
import { Checkbox } from '../../../../../components/ui/checkbox';
import { Separator } from '../../../../../components/ui/separator';
import { ZeroQwaitLogo, GoogleIcon } from './CustomIcons';
import ForgotPassword from './ForgotPassword';
import { useAuth } from '../../../../../contexts/AuthContext';
import { cn } from '../../../../../lib/utils';

export default function SignInCard() {
  const [emailError, setEmailError] = React.useState('');
  const [passwordError, setPasswordError] = React.useState('');
  const [open, setOpen] = React.useState(false);

  const { login, loading, error, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  const emailRef = React.useRef<HTMLInputElement>(null);
  const passwordRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (isAuthenticated && !loading && !error && user) {
      const redirectToShopDashboard = async () => {
        try {
          const token = localStorage.getItem('token');
          if (!token) { navigate('/dashboard'); return; }

          const response = await axios.get('/shops/my-shops', {
            headers: { Authorization: `Bearer ${token}` },
          });
          const shops = response.data;

          if (shops && shops.length > 0) {
            const shop = shops[0];
            const shopSlug = shop.slug || shop.name.toLowerCase().replace(/\s+/g, '-');
            const currentHost = window.location.hostname;
            const protocol = window.location.protocol;
            let newUrl = '';

            if (currentHost.includes('nip.io') || currentHost.includes('np.io')) {
              const isBaseDomain = currentHost.match(/^\d+\.\d+\.\d+\.\d+\.(nip|np)\.io$/);
              if (isBaseDomain) {
                newUrl = `${protocol}//${shopSlug}.${currentHost}/dashboard`;
              } else {
                const ipSuffixMatch = currentHost.match(/(\d+\.\d+\.\d+\.\d+\.(nip|np)\.io)$/);
                newUrl = ipSuffixMatch
                  ? `${protocol}//${shopSlug}.${ipSuffixMatch[1]}/dashboard`
                  : '/dashboard';
              }
            } else if (currentHost === 'localhost') {
              newUrl = '/dashboard';
            } else {
              const parts = currentHost.split('.');
              const domain = parts.slice(-2).join('.');
              newUrl = `${protocol}//${shopSlug}.${domain}/dashboard`;
            }

            if (newUrl.startsWith('http')) newUrl += `?token=${token}`;

            if (newUrl.startsWith('http')) {
              window.location.href = newUrl;
            } else {
              navigate(newUrl);
            }
          } else {
            navigate('/dashboard');
          }
        } catch {
          navigate('/dashboard');
        }
      };

      const role = user.role?.toString().toUpperCase().trim();
      if (role === 'SHOP_OWNER') {
        redirectToShopDashboard();
      } else if (role === 'EMPLOYEE') {
        navigate('/employee-dashboard');
      } else if (role === 'SUPER_ADMIN') {
        window.location.href = '/admin';
      } else {
        navigate('/');
      }
    }
  }, [isAuthenticated, loading, error, user, navigate]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setEmailError('');
    setPasswordError('');

    const data = new FormData(event.currentTarget);
    let email = data.get('email') as string;
    let password = data.get('password') as string;

    if ((!email || email.trim() === '') && emailRef.current) {
      email = emailRef.current.value;
    }
    if ((!password || password.trim() === '') && passwordRef.current) {
      password = passwordRef.current.value;
    }

    let isValid = true;
    if (!email || email.trim().length === 0) {
      setEmailError('Please enter your email or username.');
      isValid = false;
    }
    if (!password || password.length < 3) {
      setPasswordError('Password must be at least 3 characters long.');
      isValid = false;
    }
    if (!isValid) return;

    await login(email, password);
  };

  return (
    <div className="w-full max-w-[440px] rounded-2xl border border-white/10 bg-white/[0.06] p-8 backdrop-blur-xl shadow-2xl">
      {/* Logo */}
      <div className="mb-6 flex items-center">
        <ZeroQwaitLogo className="text-white" />
      </div>

      <h1 className="mb-1 text-2xl font-bold text-white">Sign in</h1>
      <p className="mb-6 text-sm text-white/50">Welcome back — continue where you left off.</p>

      {error && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        {/* Email */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email" className="text-sm text-white/70">Email or Username</Label>
          <Input
            id="email"
            type="text"
            name="email"
            placeholder="username or email"
            autoComplete="username"
            autoFocus
            required
            ref={emailRef}
            className={cn(
              'border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-violet-500',
              emailError && 'border-red-500/60'
            )}
          />
          {emailError && <p className="text-xs text-red-400">{emailError}</p>}
        </div>

        {/* Password */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="password" className="text-sm text-white/70">Password</Label>
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="text-xs text-violet-400 hover:text-violet-300 transition-colors"
            >
              Forgot your password?
            </button>
          </div>
          <Input
            id="password"
            name="password"
            type="password"
            placeholder="••••••"
            autoComplete="current-password"
            required
            ref={passwordRef}
            className={cn(
              'border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-violet-500',
              passwordError && 'border-red-500/60'
            )}
          />
          {passwordError && <p className="text-xs text-red-400">{passwordError}</p>}
        </div>

        {/* Remember me */}
        <div className="flex items-center gap-2">
          <Checkbox
            id="remember"
            name="remember"
            className="border-white/20 data-[state=checked]:bg-violet-600 data-[state=checked]:border-violet-600"
          />
          <Label htmlFor="remember" className="text-sm text-white/60 cursor-pointer">Remember me</Label>
        </div>

        <ForgotPassword open={open} handleClose={() => setOpen(false)} />

        <Button
          type="submit"
          disabled={loading}
          className="mt-1 w-full bg-violet-600 hover:bg-violet-500 text-white font-semibold"
        >
          {loading ? 'Signing in...' : 'Sign in'}
        </Button>

        <p className="text-center text-sm text-white/50">
          Don&apos;t have an account?{' '}
          <a href="/signup" className="text-violet-400 hover:text-violet-300 transition-colors">
            Sign up
          </a>
        </p>
      </form>

      <div className="my-5 flex items-center gap-3">
        <Separator className="flex-1 bg-white/10" />
        <span className="text-xs text-white/30">or</span>
        <Separator className="flex-1 bg-white/10" />
      </div>

      <Button
        type="button"
        variant="outline"
        className="w-full border-white/10 bg-white/5 text-white/80 hover:bg-white/10 hover:text-white gap-2"
        onClick={() => alert('Sign in with Google')}
      >
        <GoogleIcon />
        Sign in with Google
      </Button>
    </div>
  );
}
