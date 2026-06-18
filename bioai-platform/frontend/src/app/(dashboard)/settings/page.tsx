'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';
import { fadeUp, stagger, cardHover } from '@/lib/animations';
import { User, BarChart3, Key, Shield, LoaderCircle, Save, Sun } from 'lucide-react';
import { useAuth } from '@/contexts/auth';
import { getSupabase } from '@/lib/supabase';

export default function SettingsPage() {
  const { user, isGuest } = useAuth();
  const [fullName, setFullName] = useState('');
  const [institution, setInstitution] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [jobsToday, setJobsToday] = useState(0);
  const [jobsTotal, setJobsTotal] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const api = axios.create({ baseURL: '/api/backend' });
        const supabase = getSupabase();
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.access_token) {
          api.defaults.headers.Authorization = `Bearer ${session.access_token}`;
        }

        const [profileRes, countRes, jobsRes] = await Promise.all([
          api.get('/api/profile'),
          api.get('/api/jobs/count'),
          api.get('/api/jobs'),
        ]);

        if (profileRes.data && !profileRes.data.error) {
          setFullName(profileRes.data.full_name || '');
          setInstitution(profileRes.data.institution || '');
        }
        setJobsToday(countRes.data.count || 0);
        setJobsTotal((jobsRes.data.jobs || []).length);
      } catch {
        // Profile fetch may fail for guest users
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const api = axios.create({ baseURL: '/api/backend' });
      const supabase = getSupabase();
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        api.defaults.headers.Authorization = `Bearer ${session.access_token}`;
      }
      await api.put('/api/profile', { full_name: fullName, institution });
      toast.success('Settings saved');
    } catch {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <motion.h1 variants={fadeUp} className="text-2xl font-bold text-text-primary mb-2">Settings</motion.h1>
      <motion.p variants={fadeUp} className="text-text-secondary mb-8">Manage your account and preferences</motion.p>

      <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-6">
        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-6">
            <User className="w-5 h-5 text-accent-cyan" />
            <h2 className="text-lg font-semibold text-text-primary">Account</h2>
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <LoaderCircle className="w-5 h-5 animate-spin text-accent-cyan" />
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">Email</label>
                <input
                  type="email"
                  disabled
                  value={user?.email ?? (isGuest ? 'Guest session' : '')}
                  className="w-full px-4 py-2.5 rounded-xl border border-glass-border bg-surface-0 text-text-muted text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-1">Full Name</label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Priya Sharma"
                    className="w-full px-4 py-2.5 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm text-text-primary bg-surface-1"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-text-secondary mb-1">Institution</label>
                  <input
                    type="text"
                    value={institution}
                    onChange={(e) => setInstitution(e.target.value)}
                    placeholder="e.g. IIT Bombay"
                    className="w-full px-4 py-2.5 rounded-xl border border-glass-border focus:border-accent-cyan/40 focus:ring-2 focus:ring-accent-cyan/10 outline-none transition text-sm text-text-primary bg-surface-1"
                  />
                </div>
              </div>
              <button
                onClick={handleSave}
                disabled={saving}
                className="btn-primary px-5 py-2.5 text-sm flex items-center gap-2 disabled:opacity-50"
              >
                {saving ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                Save changes
              </button>
            </div>
          )}
        </motion.section>

        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-6">
            <BarChart3 className="w-5 h-5 text-accent-cyan" />
            <h2 className="text-lg font-semibold text-text-primary">Usage</h2>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="glass p-4 text-center">
              <p className="text-2xl font-bold text-text-primary">{jobsToday}</p>
              <p className="text-xs text-text-muted mt-1">Jobs today</p>
            </div>
            <div className="glass p-4 text-center">
              <p className="text-2xl font-bold text-text-primary">{jobsTotal}</p>
              <p className="text-xs text-text-muted mt-1">Total jobs</p>
            </div>
            <div className="glass p-4 text-center">
              <p className="text-2xl font-bold text-text-primary">Free</p>
              <p className="text-xs text-text-muted mt-1">Current plan</p>
            </div>
          </div>
        </motion.section>

        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-6">
            <Sun className="w-5 h-5 text-accent-cyan" />
            <h2 className="text-lg font-semibold text-text-primary">Design</h2>
          </div>
          <p className="text-sm text-text-secondary">Void-dark theme is always active — designed for long research sessions with reduced eye strain.</p>
        </motion.section>

        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-6">
            <Key className="w-5 h-5 text-accent-cyan" />
            <h2 className="text-lg font-semibold text-text-primary">API Access</h2>
          </div>
          <div className="glass p-6 text-center">
            <Key className="w-10 h-10 text-text-muted mx-auto mb-3" />
            <h3 className="text-sm font-medium text-text-primary mb-1">Coming in Phase 2</h3>
            <p className="text-xs text-text-muted max-w-sm mx-auto">Programmatic API access for running pipelines from your scripts.</p>
          </div>
        </motion.section>

        <motion.section variants={fadeUp} className="glass-card p-6">
          <div className="flex items-center gap-2 mb-6">
            <Shield className="w-5 h-5 text-accent-cyan" />
            <h2 className="text-lg font-semibold text-text-primary">Data & Privacy</h2>
          </div>
          <div className="space-y-3 text-sm text-text-secondary">
            <p>Your uploaded sequences and results belong to you. We never train AI models on your data.</p>
            <p>Cached query results are stored for 24 hours for performance. They are keyed by input hash, not your user ID.</p>
            <p>All AI outputs are labeled "AI-assisted research analysis — not for clinical or diagnostic use."</p>
          </div>
        </motion.section>
      </motion.div>
    </div>
  );
}
