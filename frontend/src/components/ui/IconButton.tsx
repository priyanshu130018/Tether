import React, { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';

export type IconButtonVariant = 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost';
export type IconButtonSize = 'xs' | 'sm' | 'md' | 'lg';

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: IconButtonVariant;
  size?: IconButtonSize;
  isLoading?: boolean;
  icon: React.ReactNode;
  'aria-label': string;
  title?: string;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      variant = 'secondary',
      size = 'md',
      isLoading = false,
      icon,
      'aria-label': ariaLabel,
      title,
      disabled,
      className = '',
      type = 'button',
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center rounded-lg transition-all duration-150 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed select-none';

    const sizeStyles = {
      xs: 'p-1 text-xs',
      sm: 'p-1.5 text-xs',
      md: 'p-2 text-sm',
      lg: 'p-2.5 text-base',
    }[size];

    const variantStyles = {
      primary:
        'bg-emerald-600 text-white hover:bg-emerald-500 active:bg-emerald-700 shadow-sm border border-emerald-500/30',
      secondary:
        'bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 active:bg-slate-800 border border-slate-700',
      danger:
        'bg-slate-800 text-slate-400 hover:text-rose-400 hover:bg-rose-950/40 active:bg-rose-950/60 border border-slate-700 hover:border-rose-900/60',
      outline:
        'bg-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 active:bg-slate-800 border border-slate-700',
      ghost:
        'bg-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 active:bg-slate-800 border border-transparent',
    }[variant];

    return (
      <button
        ref={ref}
        type={type}
        aria-label={ariaLabel}
        title={title || ariaLabel}
        disabled={disabled || isLoading}
        className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-current" />
        ) : (
          icon
        )}
      </button>
    );
  }
);

IconButton.displayName = 'IconButton';
