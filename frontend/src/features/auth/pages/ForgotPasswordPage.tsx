import React, { useState } from 'react';
import { Lock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AuthPageShell from '../components/AuthPageShell';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';

const ForgotPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const submitResetRequest = async () => {
    setLoading(true);
    setError('');
    try {
      await axios.post(`/auth/forgot-password`, null, { params: { email } });
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send reset email');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void submitResetRequest();
  };

  if (success) {
    return (
      <AuthPageShell
        icon={<Lock className="h-6 w-6" />}
        iconBgColor="success"
        title="Check Your Email"
        description="If an account exists with that email address, ZeroQwait will send password reset instructions."
      >
        <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
            If an account exists with that email, we&apos;ve sent password reset instructions.
          </div>
          <p className="text-sm text-white/50">Check your inbox for the reset link. The link expires in 1 hour.</p>
          <Button
            className="w-full bg-violet-600 hover:bg-violet-500 text-white"
            onClick={() => navigate('/login')}
          >
            Back to Login
          </Button>
        </div>
      </AuthPageShell>
    );
  }

  return (
    <AuthPageShell
      icon={<Lock className="h-6 w-6" />}
      iconBgColor="error"
      title="Reset Password"
      description="Enter your email address and ZeroQwait will send you a secure reset link."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email" className="text-sm text-white/70">Email Address</Label>
          <Input
            id="email"
            name="email"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
            autoFocus
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-violet-500"
          />
        </div>
        <Button
          type="submit"
          disabled={loading}
          className="w-full bg-violet-600 hover:bg-violet-500 text-white"
        >
          {loading ? 'Sending...' : 'Send Reset Link'}
        </Button>
        <Button
          type="button"
          variant="ghost"
          className="w-full text-white/50 hover:text-white hover:bg-white/5"
          onClick={() => navigate('/login')}
        >
          Back to Login
        </Button>
      </form>
    </AuthPageShell>
  );
};

export default ForgotPasswordPage;
