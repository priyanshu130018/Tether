import React from 'react';
import { Link } from 'react-router-dom';
import { Activity, ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center text-center p-6">
      <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 mb-6">
        <Activity className="w-10 h-10" />
      </div>
      <h1 className="text-4xl font-bold font-mono tracking-tight text-slate-100">404</h1>
      <h2 className="text-lg font-semibold text-slate-300 mt-2">Page Not Found</h2>
      <p className="text-sm text-slate-500 max-w-sm mt-2 font-mono">
        The monitoring route or endpoint you are looking for does not exist.
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-semibold shadow-lg shadow-emerald-950/40 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Return to Dashboard</span>
      </Link>
    </div>
  );
};
