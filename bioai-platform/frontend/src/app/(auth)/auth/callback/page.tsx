'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
import { getSupabase } from '@/lib/supabase';

export default function AuthCallback() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');

    if (!code) {
      router.replace('/auth');
      return;
    }

    getSupabase().auth.exchangeCodeForSession(code).then(({ error }: { error?: any }) => {
      if (error) {
        setError(error.message);
        return;
      }
      router.replace('/dashboard');
    }).catch((e: any) => {
      setError(e.message || 'Unknown error');
    });
  }, [router]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-green-50 to-white">
        <div className="bg-white rounded-2xl border border-red-200 p-8 max-w-sm text-center">
          <h2 className="text-lg font-semibold text-red-900 mb-2">Sign in failed</h2>
          <p className="text-sm text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-green-50 to-white">
      <div className="text-center">
        <Loader2 className="w-8 h-8 text-green-600 animate-spin mx-auto mb-4" />
        <p className="text-sm text-gray-500">Completing sign in...</p>
      </div>
    </div>
  );
}
