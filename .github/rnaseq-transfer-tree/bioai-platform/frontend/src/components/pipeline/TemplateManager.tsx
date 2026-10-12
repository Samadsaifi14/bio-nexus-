'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FloppyDisk, PencilSimple, Trash, ShareNetwork, Plus, BookOpen, X } from '@phosphor-icons/react';
import toast from 'react-hot-toast';
import {
  getTemplates,
  createTemplate,
  deleteTemplate,
  shareTemplate,
  type PipelineTemplate,
} from '@/lib/api';
import { STEP_LABELS, type JobStepStatus } from '@/types/pipeline';

const STEP_ORDER = ['blast', 'uniprot', 'msa', 'phylo', 'domains', 'pathway_enrichment', 'alphafold', 'interpret'];

function stepLabel(step: string): string {
  return STEP_LABELS[step as JobStepStatus] || step;
}

interface TemplateManagerProps {
  currentSteps: string[];
  onLoad?: (template: PipelineTemplate) => void;
}

export function TemplateManager({ currentSteps, onLoad }: TemplateManagerProps) {
  const [templates, setTemplates] = useState<PipelineTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [showSave, setShowSave] = useState(false);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getTemplates()
      .then(setTemplates)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const t = await createTemplate(name.trim(), desc.trim(), currentSteps);
      setTemplates((prev) => [t, ...prev]);
      setShowSave(false);
      setName('');
      setDesc('');
      toast.success('Template saved');
    } catch {
      toast.error('Failed to save template');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteTemplate(id);
      setTemplates((prev) => prev.filter((t) => t.id !== id));
      toast.success('Template deleted');
    } catch {
      toast.error('Failed to delete');
    }
  }

  async function handleShare(id: string) {
    try {
      const { url } = await shareTemplate(id);
      const full = `${window.location.origin}${url}`;
      await navigator.clipboard.writeText(full);
      toast.success('Share link copied');
    } catch {
      toast.error('Failed to share');
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400">
          <BookOpen className="w-4 h-4" />
          Pipeline Templates
        </div>
        <button
          onClick={() => setShowSave(!showSave)}
          className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 transition-colors"
        >
          {showSave ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
          {showSave ? 'Cancel' : 'Save current'}
        </button>
      </div>

      <AnimatePresence>
        {showSave && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="p-3 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 space-y-2">
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Template name"
                className="w-full text-sm px-3 py-1.5 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <input
                type="text"
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder="Description (optional)"
                className="w-full text-sm px-3 py-1.5 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Steps: {currentSteps.map(stepLabel).join(' → ')}
              </div>
              <button
                onClick={handleSave}
                disabled={!name.trim() || saving}
                className="flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                <FloppyDisk className="w-3 h-3" />
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {loading ? (
        <div className="text-xs text-gray-500 py-2">Loading templates...</div>
      ) : templates.length === 0 ? (
        <div className="text-xs text-gray-500 dark:text-gray-500 py-2">No templates saved yet.</div>
      ) : (
        <div className="space-y-1">
          {templates.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors group"
            >
              <button
                onClick={() => onLoad?.(t)}
                className="flex-1 text-left min-w-0"
              >
                <div className="text-sm font-medium truncate">{t.name}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {t.steps.map(stepLabel).join(' → ')}
                </div>
              </button>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handleShare(t.id)}
                  className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
                  title="Share"
                >
                  <ShareNetwork className="w-3 h-3 text-gray-500" />
                </button>
                <button
                  onClick={() => handleDelete(t.id)}
                  className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30"
                  title="Delete"
                >
                  <Trash className="w-3 h-3 text-red-400" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
