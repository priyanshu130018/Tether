import React, { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'outline' | 'ghost';
export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  icon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      children,
      variant = 'secondary',
      size = 'md',
      isLoading,
      loading,
      leftIcon,
      rightIcon,
      icon,
      disabled,
      className = '',
      type = 'button',
      ...props
    },
    ref
  ) => {
    const isButtonLoading = isLoading ?? loading ?? false;
    const buttonIcon = leftIcon || icon;
    const baseStyles =
      'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed select-none';

    const sizeStyles = {
      xs: 'text-xs px-2.5 py-1 gap-1.5',
      sm: 'text-xs px-3 py-1.5 gap-1.5',
      md: 'text-sm px-4 py-2 gap-2',
      lg: 'text-base px-5 py-2.5 gap-2.5',
    }[size];

    const variantStyles = {
      primary:
        'bg-emerald-600 text-white hover:bg-emerald-500 active:bg-emerald-700 shadow-sm shadow-emerald-950/40 border border-emerald-500/30',
      secondary:
        'bg-slate-800 text-slate-200 hover:bg-slate-700 hover:text-white active:bg-slate-800 border border-slate-700',
      danger:
        'bg-rose-600 text-white hover:bg-rose-500 active:bg-rose-700 shadow-sm shadow-rose-950/40 border border-rose-500/30',
      outline:
        'bg-transparent text-slate-300 hover:text-white hover:bg-slate-800/80 active:bg-slate-800 border border-slate-700',
      ghost:
        'bg-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 active:bg-slate-800 border border-transparent',
    }[variant];

    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || isButtonLoading}
        className={`${baseStyles} ${sizeStyles} ${variantStyles} ${className}`}
        {...props}
      >
        {isButtonLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-current shrink-0" />
        ) : (
          buttonIcon && <span className="shrink-0">{buttonIcon}</span>
        )}
        <span>{children}</span>
        {!isButtonLoading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';
