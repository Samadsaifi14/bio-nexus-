'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Dna, Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/auth';
import { ThemeToggle } from '@/components/ThemeToggle';

export default function AuthPage() {
  const { user, loading, signIn, isGuest } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && (user || isGuest)) {
      router.replace('/analyze');
    }
  }, [user, isGuest, loading, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-teal-50 to-white">
        <div className="absolute top-4 right-4">
          <ThemeToggle compact />
        </div>
        <Loader2 className="w-8 h-8 text-teal-600 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-teal-50 to-white">
      <div className="absolute top-4 right-4">
        <ThemeToggle compact />
      </div>
      <div className="bg-white rounded-2xl border border-gray-200 p-8 w-full max-w-sm shadow-sm">
        <div className="flex items-center gap-2 justify-center mb-6">
          <Dna className="w-8 h-8 text-teal-600" />
          <span className="text-xl font-bold text-gray-900">Bio Nexus</span>
        </div>

        <h1 className="text-xl font-semibold text-gray-900 text-center mb-2">Welcome to Bio Nexus</h1>
        <p className="text-sm text-gray-500 text-center mb-8">
          Bioinformatics tools for sequence analysis
        </p>

        <button
          onClick={signIn}
          className="w-full px-6 py-3 bg-teal-600 text-white font-medium rounded-xl hover:bg-teal-700 transition flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Sign in with Google
        </button>

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200" />
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="bg-white px-2 text-gray-400">or</span>
          </div>
        </div>

        <button
          onClick={() => router.replace('/analyze')}
          className="w-full px-6 py-3 bg-white border border-gray-200 text-gray-700 font-medium rounded-xl hover:bg-gray-50 transition"
        >
          Continue without signing in
        </button>

        <p className="mt-6 text-xs text-gray-400 text-center leading-relaxed">
          Free for academic researchers. No spam, ever.<br />
          Guest results are saved for 24 hours.
        </p>
      </div>
    </div>
  );
}
