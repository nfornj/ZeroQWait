import * as React from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthPage } from 'supertokens-auth-react/ui';
import { EmailPasswordPreBuiltUI } from 'supertokens-auth-react/recipe/emailpassword/prebuiltui';

export default function SignInCard() {
  const navigate = useNavigate();

  return (
    <AuthPage
      preBuiltUIList={[EmailPasswordPreBuiltUI]}
      isSignUp={false}
      redirectOnSessionExists
      navigate={(path) => (typeof path === 'number' ? navigate(path) : navigate(path))}
    />
  );
}