'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { SquaresFour as LayoutDashboard, TestTube as FlaskConical, Clock, ClockCounterClockwise as History, MagnifyingGlass as Search, GearSix as Settings, BookOpen, SignOut as LogOut, Dna, List as Menu, CaretRight as ChevronRight } from '@phosphor-icons/react';
import { useAuth } from '@/contexts/auth';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { TutorialWalkthrough } from '@/components/TutorialWalkthrough';
import { AuditInsightPanel } from '@/components/AuditInsightPanel';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
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
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 bg-accent-cyan/10 border border-accent-cyan/25"
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
              Syn<span className="text-accent-cyan">teny</span>
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
                  style={{ background: 'rgb(var(--accent-cyan))' }}
                  transition={{ type: 'spring', stiffness: 380, damping: 35 }}
                />
              )}

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
                  className="absolute left-full ml-3 px-2.5 py-1.5 rounded-lg text-xs whitespace-nowrap text-text-primary pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-[100]"
                  style={{
                    background: 'rgb(var(--bg-surface-2))',
                    border:     '1px solid rgb(var(--glass-border) / var(--glass-border-a))',
                    boxShadow:  'var(--shadow-float)',
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
                boxShadow:  'var(--shadow-float)',
              }}
            >
              Sign out
            </div>
          )}
        </button>

        {!collapsed && (
          <div className="px-3 pt-2">
            <div className="divider mb-3" />
            <div className="flex items-center justify-between px-3">
              <span className="text-[10px] font-mono text-text-muted/70">SYNTENY-CORE</span>
              <span className="flex items-center gap-1.5 text-[10px] font-mono text-accent-cyan/80">
                <span className="w-1 h-1 rounded-full bg-accent-cyan" />
                v2.1
              </span>
            </div>
          </div>
        )}
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

  return (
    <div className="flex h-screen bg-void overflow-hidden">
      <motion.aside
        animate={{ width: collapsed ? 68 : 220 }}
        transition={{ duration: 0.28, ease: [0.25, 1, 0.5, 1] }}
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
          className="absolute -right-3 top-[18px] z-20 w-6 h-6 rounded-full flex items-center justify-center transition-all hover:scale-110"
          style={{
            background: 'rgb(var(--bg-surface-2))',
            border:     '1px solid rgb(var(--glass-border) / var(--glass-border-a))',
            boxShadow:  'var(--shadow-float-sm)',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(74,222,128,0.4)';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgb(var(--glass-border) / var(--glass-border-a))';
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
              className="scrim fixed inset-0 z-40 md:hidden"
              onClick={() => setMobileOpen(false)}
            />

            <motion.aside
              key="drawer"
              initial={{ x: -240 }}
              animate={{ x: 0 }}
              exit={{ x: -240 }}
              transition={{ type: 'spring', damping: 32, stiffness: 300 }}
              className="glass-sidebar fixed left-0 top-0 bottom-0 w-56 z-50 md:hidden overflow-hidden"
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
          className="glass-header flex items-center gap-4 px-6 py-4 flex-shrink-0"
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

          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full border border-accent-cyan/20 bg-accent-cyan/5">
            <span className="relative flex w-1.5 h-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-cyan opacity-60" />
              <span className="relative inline-flex rounded-full w-1.5 h-1.5 bg-accent-cyan" />
            </span>
            <span className="text-[11px] font-mono text-text-muted">systems live</span>
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
      <BreadcrumbSchema />
    </div>
  );
}
