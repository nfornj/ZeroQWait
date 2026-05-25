import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthPage } from 'supertokens-auth-react/ui';
import { EmailPasswordPreBuiltUI } from 'supertokens-auth-react/recipe/emailpassword/prebuiltui';
import { ZeroQwaitLogo } from './CustomIcons';

export default function SignInCard() {
  const navigate = useNavigate();

  return (
    <div className="w-full max-w-[440px] rounded-2xl border border-white/10 bg-white/[0.06] p-8 backdrop-blur-xl shadow-2xl">
      <div className="mb-6 flex items-center">
        <ZeroQwaitLogo className="text-white" />
      </div>

      <h1 className="mb-1 text-2xl font-bold text-white">Sign in</h1>
      <p className="mb-6 text-sm text-white/50">Welcome back — continue where you left off.</p>

      <AuthPage
        preBuiltUIList={[EmailPasswordPreBuiltUI]}
        isSignUp={false}
        redirectOnSessionExists
        navigate={(path) => (typeof path === 'number' ? navigate(path) : navigate(path))}
      />
    </div>
  );
}