'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  FlaskConical,
  Clock,
  History,
  Search,
  Settings,
  BookOpen,
  ChevronRight,
  LogOut,
  Dna,
  Menu,
} from 'lucide-react';
import { useAuth } from '@/contexts/auth';
import { ThemeToggle } from '@/components/ThemeToggle';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { TutorialWalkthrough } from '@/components/TutorialWalkthrough';
import { AuditInsightPanel } from '@/components/AuditInsightPanel';

const NAV_ITEMS = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard'  },
  { href: '/analyze',   icon: FlaskConical,    label: 'Analyze'    },
  { href: '/retrieve',  icon: Search,          label: 'Retrieve'   },
  { href: '/jobs',      icon: Clock,           label: 'Jobs'       },
  { href: '/history',   icon: History,         label: 'History'    },
  { href: '/learn',     icon: BookOpen,        label: 'Learn'      },
  { href: '/settings',  icon: Settings,        label: 'Settings'   },
] as const;

const labelVariants = {
  hidden: { opacity: 0, width: 0,    transition: { duration: 0.15 } },
  show:   { opacity: 1, width: 'auto', transition: { duration: 0.2, delay: 0.05 } },
};

function SidebarContent({
  collapsed,
  pathname,
  user,
  signOut,
}: {
  collapsed: boolean;
  pathname: string;
  user: { email?: string | null } | null;
  signOut: () => void;
}) {
  return (
    <div className="flex flex-col h-full py-4">
      <div className={`flex items-center gap-3 px-4 pb-5 mb-1 ${collapsed ? 'justify-center' : ''}`}>
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{
            background: 'rgba(0,245,212,0.1)',
            border:     '1px solid rgba(0,245,212,0.25)',
            boxShadow:  '0 0 12px rgba(0,245,212,0.1)',
          }}
        >
          <Dna size={14} className="text-accent-cyan" />
        </div>

        <AnimatePresence>
          {!collapsed && (
            <motion.span
              key="logo-text"
              variants={labelVariants}
              initial="hidden"
              animate="show"
              exit="hidden"
              className="font-display text-sm font-semibold overflow-hidden whitespace-nowrap"
            >
              Bio <span className="text-gradient">Nexus</span>
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      <div className="divider mx-4 mb-3" />

      <nav className="flex-1 px-3 space-y-0.5">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href || (href !== '/dashboard' && pathname.startsWith(href + '/'));

          return (
            <Link
              key={href}
              href={href}
              className={`nav-item ${active ? 'active' : ''} ${collapsed ? 'justify-center' : ''} group`}
            >
              {active && (
                <motion.div
                  layoutId="nav-indicator"
                  className="absolute left-0 inset-y-[6px] w-[3px] rounded-full"
                  style={{ background: 'var(--accent-cyan)' }}
                  transition={{ type: 'spring', stiffness: 380, damping: 35 }}
                />
              )}

              <Icon
                size={16}
                className="flex-shrink-0"
                strokeWidth={active ? 2 : 1.75}
              />

              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    key={`label-${href}`}
                    variants={labelVariants}
                    initial="hidden"
                    animate="show"
                    exit="hidden"
                    className="overflow-hidden whitespace-nowrap text-sm"
                  >
                    {label}
                  </motion.span>
                )}
              </AnimatePresence>

              {collapsed && (
                <div
                  className="absolute left-full ml-3 px-2.5 py-1.5 rounded-lg text-xs whitespace-nowrap text-text-primary pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-[100]"
                  style={{
                    background: 'var(--bg-surface-2)',
                    border:     '1px solid var(--glass-border)',
                    boxShadow:  '0 4px 16px rgba(0,0,0,0.5)',
                  }}
                >
                  {label}
                </div>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="px-3 pt-3 space-y-1">
        <div className="divider mb-3" />

        {user && !collapsed && (
          <div className="px-3 py-2">
            <p className="text-[11px] text-text-muted font-mono truncate">
              {user.email ?? 'Guest session'}
            </p>
          </div>
        )}

        <button
          onClick={signOut}
          className={`nav-item w-full text-left hover:!text-red-400 hover:!bg-red-500/10 ${collapsed ? 'justify-center' : ''} group`}
        >
          <LogOut size={15} className="flex-shrink-0" strokeWidth={1.75} />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                key="signout-label"
                variants={labelVariants}
                initial="hidden"
                animate="show"
                exit="hidden"
                className="overflow-hidden whitespace-nowrap text-sm"
              >
                Sign out
              </motion.span>
            )}
          </AnimatePresence>

          {collapsed && (
            <div
              className="absolute left-full ml-3 px-2.5 py-1.5 rounded-lg text-xs whitespace-nowrap text-text-primary pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-[100]"
              style={{
                background: 'var(--bg-surface-2)',
                border:     '1px solid var(--glass-border)',
                boxShadow:  '0 4px 16px rgba(0,0,0,0.5)',
              }}
            >
              Sign out
            </div>
          )}
        </button>
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname              = usePathname();
  const { user, signOut }     = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => { setMobileOpen(false); }, [pathname]);

  const sidebarBg = {
    background:           'rgba(8, 8, 18, 0.75)',
    borderRight:          '1px solid rgba(100, 110, 180, 0.10)',
    backdropFilter:       'blur(24px) saturate(160%)',
    WebkitBackdropFilter: 'blur(24px) saturate(160%)',
  };

  return (
    <div className="flex h-screen bg-void overflow-hidden">
      <motion.aside
        animate={{ width: collapsed ? 68 : 220 }}
        transition={{ duration: 0.28, ease: [0.25, 1, 0.5, 1] }}
        className="relative hidden md:flex flex-col flex-shrink-0 overflow-visible"
        style={sidebarBg}
      >
        <SidebarContent
          collapsed={collapsed}
          pathname={pathname}
          user={user}
          signOut={signOut}
        />

        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-6 z-10 w-6 h-6 rounded-full flex items-center justify-center transition-all"
          style={{
            background: 'var(--bg-surface-2)',
            border:     '1px solid var(--glass-border)',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(0,245,212,0.4)';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--glass-border)';
          }}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronRight
            size={11}
            className="text-text-muted transition-transform"
            style={{ transform: collapsed ? 'rotate(0deg)' : 'rotate(180deg)' }}
          />
        </button>
      </motion.aside>

      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 z-40 md:hidden"
              style={{ background: 'rgba(4,4,10,0.8)', backdropFilter: 'blur(8px)' }}
              onClick={() => setMobileOpen(false)}
            />

            <motion.aside
              key="drawer"
              initial={{ x: -240 }}
              animate={{ x: 0 }}
              exit={{ x: -240 }}
              transition={{ type: 'spring', damping: 32, stiffness: 300 }}
              className="fixed left-0 top-0 bottom-0 w-56 z-50 md:hidden overflow-hidden"
              style={sidebarBg}
            >
              <SidebarContent
                collapsed={false}
                pathname={pathname}
                user={user}
                signOut={signOut}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header
          className="flex items-center gap-4 px-6 py-4 flex-shrink-0"
          style={{
            background:   'rgba(4,4,10,0.6)',
            borderBottom: '1px solid rgba(100,110,180,0.09)',
            backdropFilter: 'blur(12px)',
          }}
        >
          <button
            onClick={() => setMobileOpen(true)}
            className="md:hidden text-text-muted hover:text-text-primary transition-colors"
            aria-label="Open navigation"
          >
            <Menu size={18} />
          </button>

          <div className="flex-1">
            <span className="text-xs font-mono text-text-muted capitalize">
              {pathname.split('/').filter(Boolean).join(' · ')}
            </span>
          </div>

          <ThemeToggle />
        </header>

        <main className="flex-1 overflow-y-auto relative">
          <div className="absolute inset-0 bg-grid pointer-events-none opacity-[0.025]" />
          <div className="relative z-10 max-w-content mx-auto px-6 py-8">
            <ErrorBoundary>{children}</ErrorBoundary>
          </div>
        </main>
      </div>
      <TutorialWalkthrough />
      <AuditInsightPanel sessionId={typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}`} />
    </div>
  );
}
