'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Dna, History, Settings, Sparkles, Play, LogOut, Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/auth';
import { getJobCount } from '@/lib/api';

const navItems = [
  { href: '/analyze', label: 'Analyze', icon: Play },
  { href: '/dashboard', label: 'Dashboard', icon: Sparkles },
  { href: '/history', label: 'History', icon: History },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading: authLoading, signOut } = useAuth();
  const [usage, setUsage] = useState({ count: 0, limit: 10, remaining: 10 });

  useEffect(() => {
    getJobCount().then(setUsage).catch(() => {});
  }, [pathname]);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace('/auth');
    }
  }, [user, authLoading, router]);

  if (authLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-green-600 animate-spin" />
      </div>
    );
  }

  const usagePct = usage.limit > 0 ? ((usage.limit - usage.remaining) / usage.limit) * 100 : 0;

  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
        <div className="h-16 border-b border-gray-200 px-4 flex items-center gap-2">
          <Dna className="w-7 h-7 text-green-600" />
          <span className="text-lg font-bold text-gray-900">Bio Nexus</span>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${active ? 'bg-green-50 text-green-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}
              >
                <item.icon className="w-5 h-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="p-4 border-t border-gray-200 space-y-4">
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span className="truncate">{user.email}</span>
            <button onClick={signOut} className="p-1 hover:text-red-500 transition" title="Sign out">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-2">Free tier</div>
            <div className="text-sm font-medium text-gray-700">
              {usage.remaining} jobs remaining today
            </div>
            <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-green-500 rounded-full transition-all" style={{ width: `${usagePct}%` }} />
            </div>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="max-w-5xl mx-auto px-6 py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
