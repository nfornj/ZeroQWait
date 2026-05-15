import React from 'react';
import Content from './auth-sign-in/components/Content';

interface AuthPageShellProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  iconBgColor?: 'primary' | 'success' | 'error' | 'warning';
  children: React.ReactNode;
}

const iconBgMap: Record<string, string> = {
  primary: 'bg-violet-600',
  success: 'bg-emerald-600',
  error: 'bg-red-600',
  warning: 'bg-amber-600',
};

export default function AuthPageShell({
  icon,
  title,
  description,
  iconBgColor = 'primary',
  children,
}: AuthPageShellProps) {
  const iconBg = iconBgMap[iconBgColor] ?? iconBgMap.primary;

  return (
    <div
      className="flex min-h-screen w-full items-center justify-center px-4 py-8"
      style={{
        background: 'radial-gradient(ellipse at 50% 50%, hsl(270, 50%, 25%), hsl(260, 60%, 8%))',
      }}
    >
      <div className="flex w-full max-w-5xl items-center justify-center gap-16">
        <Content />

        <div className="w-full max-w-[440px] rounded-2xl border border-white/10 bg-white/[0.06] p-8 backdrop-blur-xl shadow-2xl">
          {/* Icon + Title + Description */}
          <div className="mb-6 flex flex-col items-center text-center gap-3">
            <div className={`flex h-14 w-14 items-center justify-center rounded-full ${iconBg} text-white shadow-lg`}>
              {icon}
            </div>
            <h1 className="text-2xl font-bold text-white">{title}</h1>
            <p className="text-sm text-white/50 max-w-xs">{description}</p>
          </div>

          {children}
        </div>
      </div>
    </div>
  );
}
