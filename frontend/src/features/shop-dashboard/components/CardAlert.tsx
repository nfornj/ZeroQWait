import { Sparkles } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../../contexts/AuthContext';

export default function CardAlert() {
  const location = useLocation();
  const { user } = useAuth();
  const isEmployee = user?.role === 'employee' || location.pathname.startsWith('/employee-dashboard');

  if (isEmployee) return null;

  return (
    <div className="mx-3 mb-3 flex-shrink-0 rounded-xl border border-border bg-muted/50 p-4">
      <div className="mb-2 inline-flex h-8 w-8 items-center justify-center rounded-full bg-background">
        <Sparkles className="h-4 w-4" style={{ color: 'var(--owner-secondary, var(--owner-primary))' }} />
      </div>
      <p className="text-sm font-semibold text-foreground leading-snug">
        Create a better experience
      </p>
      <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
        Discover tips to improve your shop's efficiency and delight your clients.
      </p>
      <button
        type="button"
        className="mt-3 text-xs font-medium hover:underline transition-colors"
        style={{ color: 'var(--owner-primary)' }}
      >
        Learn more →
      </button>
    </div>
  );
}
