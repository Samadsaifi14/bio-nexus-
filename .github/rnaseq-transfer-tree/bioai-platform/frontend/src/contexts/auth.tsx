'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { User } from '@supabase/supabase-js';
import { getSupabase } from '@/lib/supabase';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isGuest: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  upgradeToAccount: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  isGuest: false,
  signIn: async () => {},
  signOut: async () => {},
  upgradeToAccount: async () => {},
  getToken: async () => null,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGuest, setIsGuest] = useState(false);

  const restoreOrCreateSession = async () => {
    try {
      const supabase = getSupabase();
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.user) {
        setUser(session.user);
        setIsGuest(session.user.is_anonymous ?? false);
      } else {
        const { data, error } = await supabase.auth.signInAnonymously();
        if (error) {
          console.error('Anonymous sign-in failed:', error.message);
        }
        if (data?.user) {
          setUser(data.user);
          setIsGuest(true);
        }
      }
    } catch (err) {
      console.error('Session restore failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    restoreOrCreateSession();
  }, []);

  useEffect(() => {
    try {
      const supabase = getSupabase();
      const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
        setUser(session?.user ?? null);
        setIsGuest(session?.user?.is_anonymous ?? false);
      });
      return () => subscription.unsubscribe();
    } catch {}
  }, []);

  const signIn = async () => {
    try {
      const supabase = getSupabase();
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      });
      if (error) {
        console.error('Sign in error:', error.message);
      }
    } catch {
      console.error('Sign in failed');
    }
  };

  const upgradeToAccount = async () => {
    try {
      const supabase = getSupabase();
      const { error } = await supabase.auth.linkIdentity({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      });
      if (error) {
        console.error('Upgrade failed:', error.message);
        throw error;
      }
    } catch {
      console.error('Upgrade failed');
    }
  };

  const signOut = async () => {
    try {
      const supabase = getSupabase();
      await supabase.auth.signOut();
      setUser(null);
      setIsGuest(false);
    } catch {
      console.error('Sign out failed');
    }
  };

  const getToken = async (): Promise<string | null> => {
    try {
      const supabase = getSupabase();
      const { data: { session } } = await supabase.auth.getSession();
      return session?.access_token ?? null;
    } catch {
      return null;
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, isGuest, signIn, signOut, upgradeToAccount, getToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
