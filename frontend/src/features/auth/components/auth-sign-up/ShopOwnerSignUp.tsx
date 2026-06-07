import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthPage } from 'supertokens-auth-react/ui';
import { EmailPasswordPreBuiltUI } from 'supertokens-auth-react/recipe/emailpassword/prebuiltui';
import AuthSplitShell from '../AuthSplitShell';

export default function ShopOwnerSignUp() {
  const navigate = useNavigate();

  return (
    <AuthSplitShell
      title="Create Your Shop Account"
      description="Register your business and start managing queues."
    >
      <AuthPage
        preBuiltUIList={[EmailPasswordPreBuiltUI]}
        isSignUp
        redirectOnSessionExists
        navigate={(path) => (typeof path === 'number' ? navigate(path) : navigate(path))}
      />
    </AuthSplitShell>
  );
}