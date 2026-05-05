import SignInCard from './components/SignInCard';
import Content from './components/Content';

export default function SignInSide() {
  return (
    <div
      className="flex min-h-screen w-full items-center justify-center px-4 py-8"
      style={{
        background: 'radial-gradient(ellipse at 50% 50%, hsl(270, 50%, 25%), hsl(260, 60%, 8%))',
      }}
    >
      <div className="flex w-full max-w-5xl items-center justify-center gap-16">
        <Content />
        <SignInCard />
      </div>
    </div>
  );
}
