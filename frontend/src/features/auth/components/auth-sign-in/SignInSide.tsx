import AuthSplitShell from '../AuthSplitShell';
import SignInCard from './components/SignInCard';

export default function SignInSide() {
  return (
    <AuthSplitShell
      title="Welcome back"
      description="Sign in to review live operations, approvals, and your shop's AI workspace."
    >
      <SignInCard />
    </AuthSplitShell>
  );
}
