'use client';

import { useState } from 'react';
import type { ContactCategory, IntramolecularContacts } from '@/lib/api';

const CONTACT_SECTIONS: { key: keyof Omit<IntramolecularContacts, 'status' | 'error' | 'method' | 'limitation'>; label: string; blurb: string }[] = [
  { key: 'hbonds', label: 'Hydrogen Bonds', blurb: 'Polar donor/acceptor contacts within the structure' },
  { key: 'salt_bridges', label: 'Salt Bridges', blurb: 'Oppositely charged side chains (LYS/ARG vs ASP/GLU)' },
  { key: 'hydrophobic', label: 'Hydrophobic Core', blurb: 'Apolar side-chain packing' },
  { key: 'disulfides', label: 'Disulfide Bridges', blurb: 'Covalent CYS SG-SG bridges' },
];

const PREVIEW_LIMIT = 100;

function ContactSection({ label, blurb, category }: { label: string; blurb: string; category: ContactCategory }) {
  const [open, setOpen] = useState(false);
  const shown = open ? category.items.slice(0, PREVIEW_LIMIT) : [];
  return (
    <div className="border-b border-glass-border/50 last:border-b-0 py-2">
      <button type="button" onClick={() => setOpen((v) => !v)} className="w-full flex items-center justify-between text-left gap-3">
        <span className="text-xs font-medium text-text-primary">
          {label}
          <span className="ml-2 text-text-muted font-normal">{blurb}</span>
        </span>
        <span className="text-xs text-text-muted bg-surface-1 px-2 py-0.5 rounded shrink-0">{category.count}</span>
      </button>
      {category.truncated && (
        <p className="text-xs text-status-warning mt-1">
          Showing the first {category.count} of {category.total} detected contacts.
        </p>
      )}
      {open && (
        shown.length === 0 ? (
          <p className="text-xs text-text-muted mt-1">None detected</p>
        ) : (
          <div className="overflow-x-auto mt-1">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-glass-border text-text-muted text-left">
                  <th className="pb-1 font-medium">Residue 1</th>
                  <th className="pb-1 font-medium">Atom</th>
                  <th className="pb-1 font-medium">Residue 2</th>
                  <th className="pb-1 font-medium">Atom</th>
                  <th className="pb-1 font-medium">Distance (&Aring;)</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((c, idx) => (
                  <tr key={idx} className="border-b border-glass-border/50">
                    <td className="py-1 text-accent-cyan font-mono">{c.donor ?? c.partner_residue}</td>
                    <td className="py-1 font-mono">{c.donor_atom ?? c.partner_atom}</td>
                    <td className="py-1 text-accent-cyan font-mono">
                      {c.acceptor ?? `${c.partner_residue_seq ?? ''}`}
                    </td>
                    <td className="py-1 font-mono">{c.acceptor_atom ?? c.partner_chain}</td>
                    <td className="py-1">{c.distance.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}

export function IntramolecularContactsPanel({ contacts }: { contacts?: IntramolecularContacts | null }) {
  if (!contacts) return null;
  return (
    <div className="data-card p-5">
      <h3 className="font-semibold text-text-primary mb-1">Intramolecular Contacts</h3>
      <p className="text-xs text-text-muted mb-3">
        The analysed structure is a bare receptor with no ligand, so these are the bonds
        defined within the structure itself.
      </p>
      {contacts.status === 'error' ? (
        <p className="text-xs text-status-warning">
          Contact analysis failed: {contacts.error}. This is an analysis error, not a
          result of zero contacts.
        </p>
      ) : (
        <>
          {CONTACT_SECTIONS.map((s) => (
            <ContactSection key={s.key} label={s.label} blurb={s.blurb} category={contacts[s.key]} />
          ))}
          {contacts.limitation && (
            <p className="text-xs text-text-muted mt-3">{contacts.limitation}</p>
          )}
        </>
      )}
    </div>
  );
}
