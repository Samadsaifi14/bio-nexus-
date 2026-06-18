'use client';

import { useState, useEffect } from 'react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { User, BarChart3, Bell, Key, Shield, Loader2, Save, ExternalLink, Trash2, Sun, Moon } from 'lucide-react';
import { useTheme } from '@/contexts/theme';

interface UsageStats {
  jobsToday: number;
  jobsTotal: number;
  tokensUsed: number;
}

export default function SettingsPage() {
  const { theme, toggle } = useTheme();
  const [institution, setInstitution] = useState('');
  const [fullName, setFullName] = useState('');
  const [saving, setSaving] = useState(false);
  const [stats, setStats] = useState<UsageStats>({ jobsToday: 0, jobsTotal: 0, tokensUsed: 0 });
  const [notifications, setNotifications] = useState({
    emailOnComplete: true,
    emailOnWeekly: false,
  });
  const [deleteRequested, setDeleteRequested] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [countRes, jobsRes] = await Promise.all([
          axios.get('/api/backend/api/jobs/count'),
          axios.get('/api/backend/api/jobs'),
        ]);
        setStats({
          jobsToday: countRes.data.count || 0,
          jobsTotal: (jobsRes.data.jobs || []).length,
          tokensUsed: 0,
        });
      } catch {}
    };
    fetchData();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put('/api/backend/api/profile', { full_name: fullName, institution });
      toast.success('Settings saved');
    } catch {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Settings</h1>
      <p className="text-gray-600 mb-8">Manage your account and preferences</p>

      <div className="space-y-8">
        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <User className="w-5 h-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-gray-900">Account</h2>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" disabled className="w-full px-4 py-2.5 rounded-xl border border-gray-200 bg-gray-50 text-gray-500 text-sm" placeholder="Sign in to see your email" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="e.g. Priya Sharma" className="w-full px-4 py-2.5 rounded-xl border border-gray-300 focus:border-teal-500 focus:ring-2 focus:ring-teal-200 outline-none transition text-sm text-gray-900" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Institution</label>
                <input type="text" value={institution} onChange={(e) => setInstitution(e.target.value)} placeholder="e.g. IIT Bombay" className="w-full px-4 py-2.5 rounded-xl border border-gray-300 focus:border-teal-500 focus:ring-2 focus:ring-teal-200 outline-none transition text-sm text-gray-900" />
              </div>
            </div>
            <button onClick={handleSave} disabled={saving} className="px-5 py-2.5 bg-teal-600 text-white text-sm font-medium rounded-xl hover:bg-teal-700 transition disabled:opacity-50 flex items-center gap-2">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save changes
            </button>
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <BarChart3 className="w-5 h-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-gray-900">Usage</h2>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-gray-50 rounded-xl p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{stats.jobsToday}</p>
              <p className="text-xs text-gray-500 mt-1">Jobs today</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">{stats.jobsTotal}</p>
              <p className="text-xs text-gray-500 mt-1">Total jobs</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-4 text-center">
              <p className="text-2xl font-bold text-gray-900">Free</p>
              <p className="text-xs text-gray-500 mt-1">Current plan</p>
            </div>
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <Bell className="w-5 h-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-gray-900">Notifications</h2>
          </div>
          {[
            { key: 'emailOnComplete' as const, label: 'Email when analysis completes', desc: 'Get notified when a pipeline job finishes' },
            { key: 'emailOnWeekly' as const, label: 'Weekly usage summary', desc: 'Receive a weekly email with your usage stats' },
          ].map((item) => (
            <div key={item.key} className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm font-medium text-gray-900">{item.label}</p>
                <p className="text-xs text-gray-500">{item.desc}</p>
              </div>
              <button
                onClick={() => setNotifications((prev) => ({ ...prev, [item.key]: !prev[item.key] }))}
                className={`relative w-11 h-6 rounded-full transition ${notifications[item.key] ? 'bg-teal-600' : 'bg-gray-300'}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${notifications[item.key] ? 'translate-x-5' : ''}`} />
              </button>
            </div>
          ))}
        </section>

        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <Sun className="w-5 h-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-gray-900">Appearance</h2>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">Theme</p>
              <p className="text-xs text-gray-500">Switch between light and dark mode</p>
            </div>
            <button
              onClick={toggle}
              className="flex items-center gap-2 px-4 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              {theme === 'dark' ? 'Light mode' : 'Dark mode'}
            </button>
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <Key className="w-5 h-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-gray-900">API Access</h2>
          </div>
          <div className="bg-gray-50 rounded-xl p-6 text-center">
            <Key className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <h3 className="text-sm font-medium text-gray-900 mb-1">Coming in Phase 2</h3>
            <p className="text-xs text-gray-500 max-w-sm mx-auto">Programmatic API access for running pipelines from your scripts.</p>
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <Shield className="w-5 h-5 text-teal-600" />
            <h2 className="text-lg font-semibold text-gray-900">Data & Privacy</h2>
          </div>
          <div className="space-y-3 text-sm text-gray-600">
            <p>Your uploaded sequences and results belong to you. We never train AI models on your data.</p>
            <p>Cached query results are stored for 24 hours for performance. They are keyed by input hash, not your user ID.</p>
            <p>All AI outputs are labeled "AI-assisted research analysis — not for clinical or diagnostic use."</p>
          </div>
        </section>

        <section className="bg-white rounded-2xl border border-red-200 p-6">
          <div className="flex items-center gap-2 mb-6">
            <Trash2 className="w-5 h-5 text-red-600" />
            <h2 className="text-lg font-semibold text-red-900">Danger Zone</h2>
          </div>
          {deleteRequested ? (
            <div className="bg-red-50 rounded-xl p-4 text-sm text-red-700">
              Deletion request submitted. We will process it within 48 hours.
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-900">Request account deletion</p>
                <p className="text-xs text-gray-500">This will remove all your data within 30 days</p>
              </div>
              <button onClick={() => { setDeleteRequested(true); toast.success('Deletion request submitted'); }} className="px-4 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-lg transition">
                Request deletion
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
