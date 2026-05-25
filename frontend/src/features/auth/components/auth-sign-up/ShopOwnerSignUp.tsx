import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthPage } from 'supertokens-auth-react/ui';
import { EmailPasswordPreBuiltUI } from 'supertokens-auth-react/recipe/emailpassword/prebuiltui';

export default function ShopOwnerSignUp() {
  const navigate = useNavigate();

  return (
    <div
      className="flex min-h-screen w-full items-start justify-center px-4 py-10"
      style={{
        background: 'radial-gradient(ellipse at 50% 50%, hsl(270, 50%, 25%), hsl(260, 60%, 8%))',
      }}
    >
      <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-white/[0.06] p-8 backdrop-blur-xl shadow-2xl">
        <div className="mb-8">
          <div className="text-3xl font-bold text-violet-400 mb-1">ZeroQwait</div>
          <h1 className="text-2xl font-bold text-white">Create Your Shop Account</h1>
          <p className="text-sm text-white/50 mt-1">Register your business and start managing queues</p>
        </div>

        <AuthPage
          preBuiltUIList={[EmailPasswordPreBuiltUI]}
          isSignUp
          redirectOnSessionExists
          navigate={(path) => (typeof path === 'number' ? navigate(path) : navigate(path))}
        />
      </div>
    </div>
  );
}