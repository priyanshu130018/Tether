import React, { useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  Server,
  Bell,
  Cpu,
  Layers,
  Radio,
  Menu,
  X,
  RefreshCw,
  PlusCircle,
  Building,
  Users,
  Settings,
  LogOut,
  ChevronDown,
  Shield,
} from 'lucide-react';
import { getDashboardSummary } from '../api/dashboard';
import { useAuth } from '../context/AuthContext';

export const AppLayout: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [orgDropdownOpen, setOrgDropdownOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const { user, activeTenant, role, memberships, switchTenant, logout } = useAuth();

  const { data: summary, isFetching } = useQuery({
    queryKey: ['dashboardSummary', activeTenant?.id],
    queryFn: getDashboardSummary,
    refetchInterval: 10000,
  });

  const navigation = [
    { name: 'Dashboard', href: '/', icon: Activity },
    { name: 'Targets', href: '/targets', icon: Server, count: summary?.targets },
    { name: 'Alerts', href: '/alerts', icon: Bell, badge: summary?.active_alerts ? `${summary.active_alerts}` : undefined, badgeColor: 'bg-rose-500' },
    { name: 'Jobs', href: '/jobs', icon: Layers, badge: summary?.running_jobs ? `${summary.running_jobs}` : undefined, badgeColor: 'bg-sky-500' },
    { name: 'Workers', href: '/workers', icon: Cpu, count: summary?.active_workers },
    { name: 'Notifications', href: '/notifications', icon: Radio },
    { name: 'System', href: '/system', icon: Activity },
    { name: 'Team', href: '/settings/team', icon: Users },
    { name: 'Settings', href: '/settings', icon: Settings },
  ];

  const systemStatus = summary?.down && summary.down > 0 ? 'degraded' : 'operational';
  const canCreateTarget = role !== 'VIEWER';

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#0B0F17] flex flex-col font-sans text-slate-100 selection:bg-emerald-500/20 selection:text-emerald-400">
      {/* Top Header */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-[#0B0F17]/90 backdrop-blur-md">
        <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Logo & Brand */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 lg:hidden"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            <NavLink to="/" className="flex items-center gap-2.5 font-mono text-lg font-bold tracking-widest text-slate-100 group">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 group-hover:bg-emerald-500/20 transition-colors">
                <Activity className="w-4 h-4" />
              </div>
              <span>TETHER</span>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                v0.6.0
              </span>
            </NavLink>

            {/* Tenant Selector Dropdown */}
            {activeTenant && (
              <div className="relative ml-2 sm:ml-4">
                <button
                  type="button"
                  onClick={() => {
                    setOrgDropdownOpen(!orgDropdownOpen);
                    setUserDropdownOpen(false);
                  }}
                  className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-mono text-slate-200 transition-colors"
                >
                  <Building className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="max-w-[130px] truncate font-bold">{activeTenant.name}</span>
                  <ChevronDown className="w-3 h-3 text-slate-500" />
                </button>

                {orgDropdownOpen && (
                  <div className="absolute left-0 mt-2 w-56 rounded-xl bg-slate-900 border border-slate-800 shadow-2xl py-1 z-50 font-mono text-xs">
                    <div className="px-3 py-2 border-b border-slate-800 text-[10px] uppercase text-slate-500">
                      Switch Organization
                    </div>
                    {memberships.map((m) => (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => {
                          switchTenant(m.tenant_id);
                          setOrgDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 flex items-center justify-between hover:bg-slate-800 transition-colors ${
                          m.tenant_id === activeTenant.id ? 'text-emerald-400 font-bold bg-slate-800/40' : 'text-slate-300'
                        }`}
                      >
                        <span className="truncate">Org #{m.tenant_id}</span>
                        <span className="text-[10px] text-slate-500">{m.role}</span>
                      </button>
                    ))}
                    <div className="border-t border-slate-800 mt-1 pt-1">
                      <NavLink
                        to="/settings"
                        onClick={() => setOrgDropdownOpen(false)}
                        className="block px-3 py-1.5 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                      >
                        + Create Organization
                      </NavLink>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Header: System Status Indicator & User Menu */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-xs font-mono">
              <span className="relative flex h-2 w-2">
                <span
                  className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                    systemStatus === 'operational' ? 'bg-emerald-400' : 'bg-rose-400'
                  }`}
                />
                <span
                  className={`relative inline-flex rounded-full h-2 w-2 ${
                    systemStatus === 'operational' ? 'bg-emerald-500' : 'bg-rose-500'
                  }`}
                />
              </span>
              <span className="text-slate-400">System:</span>
              <span className={systemStatus === 'operational' ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'}>
                {systemStatus === 'operational' ? 'OPERATIONAL' : 'DEGRADED'}
              </span>
              {isFetching && <RefreshCw className="w-3 h-3 text-slate-500 animate-spin ml-1" />}
            </div>

            {canCreateTarget && (
              <NavLink
                to="/targets/new"
                className="hidden sm:inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md transition-colors"
              >
                <PlusCircle className="w-3.5 h-3.5" />
                <span>Add Target</span>
              </NavLink>
            )}

            {/* User Dropdown */}
            {user && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => {
                    setUserDropdownOpen(!userDropdownOpen);
                    setOrgDropdownOpen(false);
                  }}
                  className="flex items-center gap-2 p-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-mono text-slate-200 transition-colors"
                >
                  <div className="w-6 h-6 rounded-md bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">
                    {user.full_name ? user.full_name[0].toUpperCase() : 'U'}
                  </div>
                  <span className="hidden md:inline font-semibold">{user.full_name}</span>
                  <ChevronDown className="w-3 h-3 text-slate-500" />
                </button>

                {userDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-xl bg-slate-900 border border-slate-800 shadow-2xl py-2 z-50 font-mono text-xs space-y-1">
                    <div className="px-3 py-2 border-b border-slate-800">
                      <div className="font-bold text-slate-200 truncate">{user.full_name}</div>
                      <div className="text-[10px] text-slate-500 truncate">{user.email}</div>
                      <div className="mt-1 flex items-center gap-1 text-[10px] text-emerald-400">
                        <Shield className="w-3 h-3" />
                        <span>Role: {role}</span>
                      </div>
                    </div>

                    <NavLink
                      to="/settings"
                      onClick={() => setUserDropdownOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                    >
                      <Settings className="w-3.5 h-3.5 text-slate-400" />
                      <span>Organization Settings</span>
                    </NavLink>

                    <NavLink
                      to="/settings/team"
                      onClick={() => setUserDropdownOpen(false)}
                      className="flex items-center gap-2 px-3 py-2 text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                    >
                      <Users className="w-3.5 h-3.5 text-slate-400" />
                      <span>Team Members</span>
                    </NavLink>

                    <div className="border-t border-slate-800 pt-1">
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="w-full text-left flex items-center gap-2 px-3 py-2 text-rose-400 hover:bg-rose-950/40 transition-colors"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        <span>Sign Out</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Layout Body */}
      <div className="flex flex-1">
        {/* Desktop Sidebar */}
        <aside className="hidden lg:flex w-64 flex-col border-r border-slate-800/80 bg-slate-950/40 p-4 shrink-0">
          <nav className="space-y-1.5">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href || (item.href !== '/' && location.pathname.startsWith(item.href));
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.name}
                  to={item.href}
                  className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                    <span>{item.name}</span>
                  </div>
                  {item.badge ? (
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold text-white ${item.badgeColor || 'bg-slate-700'}`}>
                      {item.badge}
                    </span>
                  ) : item.count !== undefined ? (
                    <span className="text-xs font-mono text-slate-500">{item.count}</span>
                  ) : null}
                </NavLink>
              );
            })}
          </nav>
        </aside>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-50 lg:hidden flex">
            <div
              className="fixed inset-0 bg-black/70 backdrop-blur-sm"
              onClick={() => setMobileMenuOpen(false)}
            />
            <div className="relative flex w-64 flex-col bg-slate-900 border-r border-slate-800 p-4 shadow-2xl z-10">
              <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
                <span className="font-mono font-bold text-sm tracking-wider text-slate-300">NAVIGATION</span>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-1 rounded text-slate-400 hover:text-slate-200"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <nav className="space-y-2">
                {navigation.map((item) => {
                  const isActive = location.pathname === item.href || (item.href !== '/' && location.pathname.startsWith(item.href));
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.name}
                      to={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium ${
                        isActive
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Icon className="w-4 h-4" />
                        <span>{item.name}</span>
                      </div>
                      {item.badge && (
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold text-white ${item.badgeColor || 'bg-slate-700'}`}>
                          {item.badge}
                        </span>
                      )}
                    </NavLink>
                  );
                })}
              </nav>
            </div>
          </div>
        )}

        {/* Page Content Viewport */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
