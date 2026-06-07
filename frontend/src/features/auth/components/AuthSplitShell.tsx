import React from 'react';
import Content from './auth-sign-in/components/Content';

interface AuthSplitShellProps {
  title: string;
  description: string;
  children: React.ReactNode;
}

export default function AuthSplitShell({ title, description, children }: AuthSplitShellProps) {
  return (
    <div
      className="flex min-h-screen w-full items-center justify-center px-4 py-8"
      style={{
        background: 'radial-gradient(ellipse at 50% 50%, hsl(270, 50%, 25%), hsl(260, 60%, 8%))',
      }}
    >
      <div className="grid w-full max-w-6xl items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.9fr)] lg:gap-16">
        <Content />

        <div className="w-full max-w-[520px] justify-self-center rounded-[28px] border border-white/10 bg-white/[0.06] p-6 shadow-2xl backdrop-blur-xl sm:p-8">
          <div className="mb-6 flex flex-col gap-1">
            <div className="text-sm font-semibold uppercase tracking-[0.24em] text-violet-300/90">
              ZeroQwait
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-white">{title}</h1>
            <p className="max-w-md text-sm leading-6 text-white/55">{description}</p>
          </div>

          {children}
        </div>
      </div>
    </div>
  );
}