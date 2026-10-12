'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X as CloseIcon,
  Link as LinkIcon,
  Copy,
  Check,
  ShareNetwork,
  ArrowSquareOut as ExternalLink,
  XLogo,
  FacebookLogo,
  LinkedinLogo,
  WhatsappLogo,
  TelegramLogo,
  RedditLogo,
  Envelope,
} from '@phosphor-icons/react';
import { SHARE_PLATFORMS, openSharePlatform } from '@/lib/share';

const PLATFORM_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  x: XLogo,
  facebook: FacebookLogo,
  linkedin: LinkedinLogo,
  whatsapp: WhatsappLogo,
  telegram: TelegramLogo,
  reddit: RedditLogo,
  email: Envelope,
};

interface ShareDialogProps {
  open: boolean;
  onClose: () => void;
  url: string;
  message?: string;
  title?: string;
}

export function ShareDialog({ open, onClose, url, message, title = 'Share result' }: ShareDialogProps) {
  const [copied, setCopied] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const copyLink = async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = url;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    }
  };

  const nativeShare = async () => {
    if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
      try {
        await navigator.share({ title: 'Bio Nexus — Analysis Result', text: message, url });
      } catch {
        // User dismissed — nothing to do.
      }
    }
  };

  const dialog = (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-6">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
      />
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        initial={{ opacity: 0, y: 24, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 24, scale: 0.98 }}
        transition={{ type: 'spring', stiffness: 400, damping: 32 }}
        className="relative w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl border border-glass-border bg-surface-0 shadow-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-glass-border">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <ShareNetwork className="w-4 h-4 text-accent-cyan" /> {title}
          </h3>
          <button
            onClick={onClose}
            aria-label="Close share dialog"
            className="p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-2 transition"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <div>
            <label className="text-xs text-text-muted mb-1.5 block">Anyone with this link can view the result</label>
            <div className="flex items-center gap-2">
              <div className="flex-1 flex items-center gap-2 rounded-lg bg-surface-1 border border-glass-border px-3 py-2 min-w-0">
                <LinkIcon className="w-4 h-4 shrink-0 text-accent-cyan" />
                <span className="text-xs font-mono text-text-secondary truncate">{url}</span>
              </div>
              <button
                onClick={copyLink}
                disabled={!url}
                className="inline-flex items-center gap-1.5 rounded-lg bg-accent-cyan/15 border border-accent-cyan/30 px-3 py-2 text-xs font-medium text-accent-cyan hover:bg-accent-cyan/25 transition disabled:opacity-40"
              >
                {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-xs text-text-muted hover:text-accent-cyan transition"
            >
              Preview shared result <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          {typeof navigator !== 'undefined' && typeof navigator.share === 'function' && (
            <button
              onClick={nativeShare}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-good px-4 py-2.5 text-sm font-semibold text-ink hover:bg-good/90 transition"
            >
              <ShareNetwork className="w-4 h-4" /> Share via apps…
            </button>
          )}

          <div>
            <p className="text-xs text-text-muted mb-2">Share to</p>
            <div className="grid grid-cols-4 gap-2">
              {SHARE_PLATFORMS.map((platform) => {
                const Icon = PLATFORM_ICONS[platform.id] ?? ShareNetwork;
                return (
                  <button
                    key={platform.id}
                    onClick={() => openSharePlatform(platform, url, message ?? url)}
                    className="flex flex-col items-center gap-1.5 rounded-xl border border-glass-border bg-surface-1 px-2 py-3 text-text-secondary hover:text-accent-cyan hover:border-accent-cyan/30 hover:bg-surface-2 transition"
                  >
                    <Icon className="w-5 h-5" />
                    <span className="text-[10px]">{platform.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );

  if (!mounted) return null;
  return createPortal(
    <AnimatePresence>{open ? dialog : null}</AnimatePresence>,
    document.body,
  );
}
