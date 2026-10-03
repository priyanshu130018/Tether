import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'flat' | 'outline';
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  variant = 'default',
  ...props
}) => {
  const variantStyles = {
    default: 'bg-slate-900 border border-slate-800 rounded-xl',
    flat: 'bg-slate-950/60 border border-slate-800/80 rounded-xl',
    outline: 'bg-transparent border border-slate-800 rounded-xl',
  }[variant];

  return (
    <div className={`${variantStyles} p-5 ${className}`} {...props}>
      {children}
    </div>
  );
};

export const CardHeader: React.FC<{
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}> = ({ title, description, action, className = '' }) => (
  <div className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-4 mb-4 border-b border-slate-800/80 ${className}`}>
    <div>
      <h3 className="text-sm font-semibold text-slate-100">{title}</h3>
      {description && <p className="text-xs text-slate-400 mt-0.5">{description}</p>}
    </div>
    {action && <div className="flex items-center gap-2">{action}</div>}
  </div>
);
