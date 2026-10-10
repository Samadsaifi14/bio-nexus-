'use client';

import { useState, useEffect, useId } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { SquaresFour as LayoutDashboard, TestTube as FlaskConical, Clock, ClockCounterClockwise as History, MagnifyingGlass as Search, GearSix as Settings, BookOpen, SignOut as LogOut, List as Menu, CaretRight as ChevronRight, ArrowUpRight } from '@phosphor-icons/react';
import { useAuth } from '@/contexts/auth';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { TutorialWalkthrough } from '@/components/TutorialWalkthrough';
import { AuditInsightPanel } from '@/components/AuditInsightPanel';
import { BreadcrumbSchema } from '@/components/seo/BreadcrumbSchema';

const NAV_ITEMS = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard'  },
  { href: '/analyze',   icon: FlaskConical,    label: 'Analyze'    },
  { href: '/retrieve',  icon: Search,          label: 'Retrieve'   },
  { href: '/jobs',      icon: Clock,           label: 'Jobs'       },
  { href: '/history',   icon: History,         label: 'History'    },
  { href: '/learn',     icon: BookOpen,        label: 'Learn'      },
  { href: '/settings',  icon: Settings,        label: 'Settings'   },
] as const;

const PAGE_TITLES: Record<string, string> = {
  dashboard: 'Research desk', analyze: 'Methods', retrieve: 'Retrieve evidence', jobs: 'Jobs', history: 'History', learn: 'Learning library', settings: 'Settings', results: 'Results', report: 'Report', wizard: 'Guided workflow', shared: 'Shared result',
};

const labelVariants = {
  hidden: { opacity: 0, width: 0,    transition: { duration: 0.15 } },
  show:   { opacity: 1, width: 'auto', transition: { duration: 0.2, delay: 0.05 } },
};

function SidebarContent({
  collapsed,
  pathname,
  user,
  signOut,
  onNavigate,
}: {
  collapsed: boolean;
  pathname: string;
  user: { email?: string | null } | null;
  signOut: () => void;
  onNavigate?: () => void;
}) {
  return (
    <div className="flex flex-col h-full py-5">
      <div className={`flex items-center gap-3 px-4 pb-6 mb-1 ${collapsed ? 'justify-center' : ''}`}>
        <div className="bn-mark flex-shrink-0" aria-hidden="true">B<span className="bn-mark-dot" /></div>

        <AnimatePresence>
          {!collapsed && (
            <motion.span
              key="logo-text"
              variants={labelVariants}
              initial="hidden"
              animate="show"
              exit="hidden"
              className="font-display text-lg font-semibold overflow-hidden whitespace-nowrap"
            >
              BioNexus
            </motion.span>
          )}
        </AnimatePresence>
      </div>

      {!collapsed && <p className="px-5 pb-3 text-[10px] font-mono uppercase tracking-[.16em] text-text-muted">Workspace</p>}
      <nav aria-label="Workspace navigation" className="flex-1 px-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href || (href !== '/dashboard' && pathname.startsWith(href + '/'));

          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              aria-current={active ? 'page' : undefined}
              title={collapsed ? label : undefined}
              className={`nav-item ${active ? 'active' : ''} ${collapsed ? 'justify-center' : ''} group`}
            >
              <Icon
                size={16}
                className="flex-shrink-0"
                weight={active ? 'bold' : 'regular'}
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
                  className="absolute left-full ml-3 px-2.5 py-1.5 rounded-lg text-xs whitespace-nowrap text-text-primary pointer-events-none opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity z-[100]"
                  style={{
                    background: 'rgb(var(--bg-surface-2))',
                    border:     '1px solid rgb(var(--glass-border) / var(--glass-border-a))',
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
          className={`nav-item w-full text-left hover:bg-surface-2 hover:text-text-primary ${collapsed ? 'justify-center' : ''} group`}
        >
          <LogOut size={15} className="flex-shrink-0" weight="regular" />
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
                background: 'rgb(var(--bg-surface-2))',
                border:     '1px solid rgb(var(--glass-border) / var(--glass-border-a))',
              }}
            >
              Sign out
            </div>
          )}
        </button>

        {!collapsed && <p className="px-3 pt-2 text-[10px] font-mono uppercase tracking-widest text-text-muted">Research workspace</p>}
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname              = usePathname();
  const { user, signOut }     = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const auditSessionId = useId();
  const reduceMotion = useReducedMotion();
  const section = pathname.split('/').filter(Boolean)[0] || 'dashboard';

  useEffect(() => {
    if (!mobileOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setMobileOpen(false); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [mobileOpen]);

  return (
    <div className="bn-app-shell flex min-h-[100dvh] h-[100dvh] bg-void overflow-hidden">
      <motion.aside
        animate={{ width: collapsed ? 72 : 248 }}
        transition={{ duration: reduceMotion ? 0 : 0.34, ease: [0.22, 1, 0.36, 1] }}
        className="glass-sidebar relative hidden md:flex flex-col flex-shrink-0 overflow-visible"
      >
        <SidebarContent
          collapsed={collapsed}
          pathname={pathname}
          user={user}
          signOut={signOut}
        />

        <button
          onClick={() => setCollapsed(!collapsed)}
          aria-expanded={!collapsed}
          className="absolute -right-5 top-[10px] z-20 w-11 h-11 rounded-sm flex items-center justify-center"
          style={{
            background: 'rgb(var(--bg-surface-2))',
            border:     '1px solid rgb(var(--glass-border) / var(--glass-border-a))',
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
            <motion.button
              type="button"
              aria-label="Close navigation"
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="scrim fixed inset-0 z-40 md:hidden"
              onClick={() => setMobileOpen(false)}
            />

            <motion.aside
              key="drawer"
              initial={reduceMotion ? false : { x: -256 }}
              animate={{ x: 0 }}
              exit={reduceMotion ? { opacity: 0 } : { x: -256 }}
              transition={{ duration: reduceMotion ? 0 : .3, ease: [0.22, 1, 0.36, 1] }}
              className="glass-sidebar fixed left-0 top-0 bottom-0 w-64 z-50 md:hidden overflow-hidden"
            >
              <SidebarContent
                collapsed={false}
                pathname={pathname}
                user={user}
                signOut={signOut}
                onNavigate={() => setMobileOpen(false)}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header
          className="glass-header bn-app-topbar flex items-center gap-4 px-4 py-3 sm:px-8 flex-shrink-0"
        >
          <button
            onClick={() => setMobileOpen(true)}
            className="md:hidden flex h-11 w-11 items-center justify-center text-text-secondary hover:text-text-primary transition-colors"
            aria-label="Open navigation"
          >
            <Menu size={18} />
          </button>

          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-mono uppercase tracking-[.13em] text-text-muted">BioNexus / {section}</p>
            <p className="truncate font-display text-lg leading-tight text-text-primary">{PAGE_TITLES[section] || section}</p>
          </div>

          <Link href="/analyze" className="bn-shell-action hidden sm:inline-flex">New analysis <ArrowUpRight size={17} aria-hidden="true" /></Link>
        </header>

        <main className="flex-1 overflow-y-auto relative">
          <div className="relative z-10 max-w-[1380px] mx-auto px-4 py-8 sm:px-8 lg:py-10">
            <motion.div key={pathname} initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .35, ease: [0.22, 1, 0.36, 1] }}>
              <ErrorBoundary>{children}</ErrorBoundary>
            </motion.div>
          </div>
        </main>
      </div>
      <TutorialWalkthrough />
      <AuditInsightPanel sessionId={auditSessionId} />
      <BreadcrumbSchema />
    </div>
  );
}
