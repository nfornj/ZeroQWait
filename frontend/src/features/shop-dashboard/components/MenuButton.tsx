import * as React from 'react';
import { cn } from '@/lib/utils';

export interface MenuButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  showBadge?: boolean;
}

export default function MenuButton({ showBadge = false, className, children, ...props }: MenuButtonProps) {
  return (
    <div className="relative inline-flex">
      <button
        type="button"
        className={cn(
          'inline-flex items-center justify-center rounded-lg p-2 text-muted-foreground',
          'hover:bg-accent hover:text-foreground',
          'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          className,
        )}
        {...props}
      >
        {children}
      </button>
      {showBadge && (
        <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-destructive ring-2 ring-background" />
      )}
    </div>
  );
}
