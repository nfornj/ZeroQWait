import React, { useState, useEffect } from 'react';
import { KeyRound } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import AuthPageShell from '../components/AuthPageShell';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';

const ResetPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const tokenParam = searchParams.get('token');
    if (!tokenParam) {
      setError('Invalid reset link. Please request a new password reset.');
    } else {
      setToken(tokenParam);
    }
  }, [searchParams]);

  const submitPasswordReset = async () => {
    setError('');
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters long');
      return;
    }
    setLoading(true);
    try {
      await axios.post(`/auth/reset-password`, null, {
        params: { token, new_password: newPassword },
      });
      setSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset password');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void submitPasswordReset();
  };

  if (success) {
    return (
      <AuthPageShell
        icon={<KeyRound className="h-6 w-6" />}
        iconBgColor="success"
        title="Password Reset Successful"
        description="Your password has been updated. You can sign back in immediately with the new one."
      >
        <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400">
            Your password has been reset successfully.
          </div>
          <Button
            className="w-full bg-violet-600 hover:bg-violet-500 text-white"
            onClick={() => navigate('/login')}
          >
            Go to Login
          </Button>
        </div>
      </AuthPageShell>
    );
  }

  return (
    <AuthPageShell
      icon={<KeyRound className="h-6 w-6" />}
      title="Set New Password"
      description="Enter a new password below. Reset links are single-use and expire after a short time."
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="newPassword" className="text-sm text-white/70">New Password</Label>
          <Input
            id="newPassword"
            name="newPassword"
            type="password"
            autoComplete="new-password"
            required
            disabled={!token}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-violet-500"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="confirmPassword" className="text-sm text-white/70">Confirm New Password</Label>
          <Input
            id="confirmPassword"
            name="confirmPassword"
            type="password"
            autoComplete="new-password"
            required
            disabled={!token}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="border-white/10 bg-white/5 text-white placeholder:text-white/30 focus-visible:ring-violet-500"
          />
        </div>
        <Button
          type="submit"
          disabled={loading || !token}
          className="w-full bg-violet-600 hover:bg-violet-500 text-white"
        >
          {loading ? 'Resetting...' : 'Reset Password'}
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

export default ResetPasswordPage;
