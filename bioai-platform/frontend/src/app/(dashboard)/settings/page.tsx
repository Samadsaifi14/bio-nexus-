'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';
import { fadeUp, stagger } from '@/lib/animations';
import {
  User, BarChart3, Key, Shield, LoaderCircle, Save, Sun,
  Mail, Building2, LogOut, ChevronRight, Zap,
} from 'lucide-react';
import { useAuth } from '@/contexts/auth';
import { getSupabase } from '@/lib/supabase';
import { useRouter } from 'next/navigation';

function getInitials(name?: string, email?: string): string {
  if (name)  return name.split(' ').map(p => p[0]).slice(0, 2).join('').toUpperCase();
  if (email) return email[0].toUpperCase();
  return 'G';
}

export default function SettingsPage() {
  const { user, isGuest } = useAuth();
  const router = useRouter();

  const [fullName, setFullName]       = useState('');
  const [institution, setInstitution] = useState('');
  const [saving, setSaving]           = useState(false);
  const [loading, setLoading]         = useState(true);
  const [jobsToday, setJobsToday]     = useState(0);
  const [jobsTotal, setJobsTotal]     = useState(0);
  const [dailyLimit, setDailyLimit]   = useState(10);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const api = axios.create({ baseURL: '/api/backend' });
        const supabase = getSupabase();
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.access_token) api.defaults.headers.Authorization = `Bearer ${session.access_token}`;

        const [profileRes, countRes, jobsRes] = await Promise.all([
          api.get('/api/profile'),
          api.get('/api/jobs/count'),
          api.get('/api/jobs'),
        ]);

        if (profileRes.data && !profileRes.data.error) {
          setFullName(profileRes.data.full_name || '');
          setInstitution(profileRes.data.institution || '');
        }
        setJobsToday(countRes.data.count   || 0);
        setDailyLimit(countRes.data.limit  || 10);
        setJobsTotal((jobsRes.data.jobs    || []).length);
      } catch { /* guest users may 401 */ } finally { setLoading(false); }
    };
    fetchData();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const api = axios.create({ baseURL: '/api/backend' });
      const supabase = getSupabase();
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) api.defaults.headers.Authorization = `Bearer ${session.access_token}`;
      await api.put('/api/profile', { full_name: fullName, institution });
      toast.success('Profile updated');
    } catch { toast.error('Failed to save settings'); } finally { setSaving(false); }
  };

  const handleSignOut = async () => {
    const supabase = getSupabase();
    await supabase.auth.signOut();
    router.push('/auth');
  };

  const resolvedName  = fullName || (user?.user_metadata?.full_name as string | undefined);
  const initials      = getInitials(resolvedName, user?.email);
  const usagePercent  = Math.min(Math.round((jobsToday / dailyLimit) * 100), 100);
  const memberSince   = user?.created_at
    ? new Date(user.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : null;

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <motion.h1 variants={fadeUp} className="text-2xl font-bold text-text-primary">Settings</motion.h1>
        <motion.p variants={fadeUp} className="text-sm text-text-muted mt-1">
          Manage your profile, usage, and preferences
        </motion.p>
      </div>

      <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">

        {/* ── Profile ── */}
        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-6">
            <User className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-base font-semibold text-text-primary">Profile</h2>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <LoaderCircle className="w-5 h-5 animate-spin text-accent-cyan" />
            </div>
          ) : (
            <div className="space-y-5">
              {/* Avatar identity row */}
              <div className="flex items-center gap-4 p-4 rounded-xl bg-surface-0 border border-glass-border">
                <div className="w-14 h-14 rounded-2xl bg-accent-cyan/15 border border-accent-cyan/25 flex items-center justify-center shrink-0">
                  <span className="text-accent-cyan font-bold text-xl tracking-tight">{initials}</span>
                </div>
                <div>
                  <p className="text-sm font-semibold text-text-primary">
                    {resolvedName || (isGuest ? 'Guest User' : 'Bio Nexus User')}
                  </p>
                  <p className="text-xs text-text-muted mt-0.5">{user?.email ?? (isGuest ? 'No account' : '')}</p>
                  {memberSince && <p className="text-[11px] text-text-muted/50 mt-0.5">Member since {memberSince}</p>}
                  {isGuest     && <p className="text-[11px] text-accent-amber mt-0.5">Guest session — data not persisted</p>}
                </div>
              </div>

              {/* Email (read-only) */}
              <div>
                <label className="block text-[11px] font-semibold text-text-muted mb-1.5 uppercase tracking-widest">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    type="email" disabled
                    value={user?.email ?? (isGuest ? 'Guest session' : '')}
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-glass-border bg-surface-0 text-text-muted text-sm cursor-not-allowed"
                  />
                </div>
              </div>

              {/* Editable fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-semibold text-text-muted mb-1.5 uppercase tracking-widest">Full Name</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <input
                      type="text" value={fullName} onChange={e => setFullName(e.target.value)}
                      placeholder="Your full name"
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm text-text-primary bg-surface-1"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-text-muted mb-1.5 uppercase tracking-widest">Institution</label>
                  <div className="relative">
                    <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <input
                      type="text" value={institution} onChange={e => setInstitution(e.target.value)}
                      placeholder="University or lab"
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm text-text-primary bg-surface-1"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-1">
                <button
                  onClick={handleSave} disabled={saving || isGuest}
                  className="btn-primary px-5 py-2.5 text-sm flex items-center gap-2 disabled:opacity-50"
                >
                  {saving ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Profile
                </button>
                {isGuest && <p className="text-xs text-text-muted">Sign in to persist profile data</p>}
              </div>
            </div>
          )}
        </motion.section>

        {/* ── Usage & Plan ── */}
        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-6">
            <BarChart3 className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-base font-semibold text-text-primary">Usage & Plan</h2>
          </div>
          <div className="space-y-5">
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Today',    value: jobsToday,   sub: `of ${dailyLimit} limit` },
                { label: 'All time', value: jobsTotal,   sub: 'total runs'             },
                { label: 'Plan',     value: 'Free',      sub: 'no credit card'         },
              ].map(stat => (
                <div key={stat.label} className="rounded-xl p-4 text-center bg-surface-0 border border-glass-border">
                  <p className="text-xl font-bold text-text-primary">{stat.value}</p>
                  <p className="text-xs text-text-muted mt-0.5 font-medium">{stat.label}</p>
                  <p className="text-[10px] text-text-muted/50 mt-0.5">{stat.sub}</p>
                </div>
              ))}
            </div>

            {/* Usage bar */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-text-muted">Daily analyses used</span>
                <span className="text-xs text-text-muted">{jobsToday} / {dailyLimit}</span>
              </div>
              <div className="h-1.5 bg-surface-0 rounded-full overflow-hidden border border-glass-border">
                <motion.div
                  className={`h-full rounded-full ${usagePercent >= 80 ? 'bg-accent-amber' : 'bg-accent-cyan'}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${usagePercent}%` }}
                  transition={{ duration: 0.9, ease: 'easeOut' }}
                />
              </div>
              <p className="text-[11px] text-text-muted mt-2">Resets daily at midnight UTC</p>
            </div>

            {/* Pro upsell stub */}
            <div className="flex items-center justify-between p-3.5 rounded-xl bg-accent-cyan/5 border border-accent-cyan/15 cursor-default">
              <div className="flex items-center gap-2.5">
                <Zap className="w-4 h-4 text-accent-cyan shrink-0" />
                <div>
                  <p className="text-sm font-medium text-text-primary">Need more capacity?</p>
                  <p className="text-xs text-text-muted">Pro plan with higher limits — coming soon</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-text-muted shrink-0" />
            </div>
          </div>
        </motion.section>

        {/* ── Appearance ── */}
        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Sun className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-base font-semibold text-text-primary">Appearance</h2>
          </div>
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-surface-0 border border-glass-border">
            <div>
              <p className="text-sm font-medium text-text-primary">Void Dark</p>
              <p className="text-xs text-text-muted mt-0.5">Designed for long research sessions — reduced eye strain</p>
            </div>
            <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan font-medium">Active</span>
          </div>
          <p className="text-xs text-text-muted mt-3">Additional themes will be available in a future update.</p>
        </motion.section>

        {/* ── API Access ── */}
        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Key className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-base font-semibold text-text-primary">API Access</h2>
          </div>
          <div className="p-5 rounded-xl bg-surface-0 border border-glass-border text-center">
            <Key className="w-8 h-8 text-text-muted mx-auto mb-3" />
            <p className="text-sm font-medium text-text-primary">Coming in Phase 2</p>
            <p className="text-xs text-text-muted mt-1 max-w-xs mx-auto">
              Programmatic access to run BioNexus pipelines from your scripts and notebooks.
            </p>
          </div>
        </motion.section>

        {/* ── Data & Privacy ── */}
        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-accent-cyan" />
            <h2 className="text-base font-semibold text-text-primary">Data & Privacy</h2>
          </div>
          <div className="space-y-3">
            {[
              'Your uploaded sequences and results belong to you. We never train models on your data.',
              'Cached query results are stored for 24 hours, keyed by input hash — not your user ID.',
              'All AI outputs are labeled "AI-assisted research analysis — not for clinical or diagnostic use."',
            ].map((line, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <div className="w-1 h-1 rounded-full bg-accent-cyan/60 mt-2 shrink-0" />
                <p className="text-sm text-text-secondary">{line}</p>
              </div>
            ))}
          </div>
        </motion.section>

        {/* ── Account Actions ── */}
        {!isGuest && (
          <motion.section variants={fadeUp} className="glass-card p-6 border border-error/10">
            <h2 className="text-base font-semibold text-text-primary mb-4">Account Actions</h2>
            <button
              onClick={handleSignOut}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-error/20 text-error text-sm hover:bg-error/5 transition"
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </motion.section>
        )}
      </motion.div>
    </div>
  );
}