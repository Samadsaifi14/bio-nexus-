'use client';

import { useState } from 'react';
import { DownloadSimple, CaretDown, Warning } from '@phosphor-icons/react';
import toast from 'react-hot-toast';
import { longApi } from '@/lib/api';

interface StructureExportMenuProps {
  /** UniProt accession or PDB ID — enables structure exports (PDB/CIF/PSE/ChimeraX/VMD) */
  identifier?: string | null;
  /** Docking job ID — enables docking exports (complex PDB / ligand SDF) */
  dockingJobId?: string | null;
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function downloadFile(path: string, filename: string) {
  const res = await longApi.get(path, { responseType: 'blob', timeout: 120_000 });
  saveBlob(new Blob([res.data]), filename);
}

const CHIMERAX_SCRIPT_NOTE =
  '# ChimeraX command script — run after opening the downloaded CIF/PDB:\n' +
  '#   open <file>\n' +
  '#   cartoon\n' +
  '#   color byattribute bfactor palette 0,#ff7d45:50,#ffcb12:70,#65cbf3:90,#0053d6 target a\n\n' +
  'open $1\ncartoon\ncolor byattribute bfactor palette 0,#ff7d45:50,#ffcb12:70,#65cbf3:90,#0053d6 target a\n';

const VMD_SCRIPT_NOTE =
  '# VMD/Tcl script — run after opening the downloaded PDB:\n' +
  '#   vmd -e docking.tcl\n\n' +
  'mol new [lindex $argv 0]\nmol delrep 0 top\nmol representation NewCartoon\nmol color Beta\nmol addrep top\n';

export function StructureExportMenu({ identifier, dockingJobId }: StructureExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  if (!identifier && !dockingJobId) return null;

  const label = identifier ?? `job-${dockingJobId!.slice(0, 8)}`;

  const items: Array<{
    id: string;
    label: string;
    hint: string;
    run: () => Promise<void>;
  }> = [];

  if (identifier) {
    items.push(
      { id: 'pdb', label: 'PDB', hint: '.pdb coordinates', run: async () => {
        await downloadFile(`/api/structure-export/structure/${identifier}?format=pdb`, `${label}.pdb`);
      } },
      { id: 'cif', label: 'mmCIF', hint: '.cif coordinates', run: async () => {
        await downloadFile(`/api/structure-export/structure/${identifier}?format=cif`, `${label}.cif`);
      } },
      { id: 'pse', label: 'PyMOL session', hint: '.pse — cartoon + pLDDT spectrum pre-applied', run: async () => {
        await downloadFile(`/api/structure-export/structure/${identifier}?format=pse`, `${label}_styled.pse`);
      } },
      { id: 'chimerax', label: 'ChimeraX bundle', hint: '.cif + command script (no fake .cxs)', run: async () => {
        await downloadFile(`/api/structure-export/structure/${identifier}?format=cif`, `${label}.cif`);
        saveBlob(new Blob([CHIMERAX_SCRIPT_NOTE], { type: 'text/plain' }), `${label}_chimerax.cxc`);
      } },
      { id: 'vmd', label: 'VMD bundle', hint: '.pdb + tcl script (no fake state file)', run: async () => {
        await downloadFile(`/api/structure-export/structure/${identifier}?format=pdb`, `${label}.pdb`);
        saveBlob(new Blob([VMD_SCRIPT_NOTE], { type: 'text/plain' }), `${label}_vmd.tcl`);
      } },
    );
  }

  if (dockingJobId) {
    items.push(
      { id: 'complex', label: 'Complex PDB', hint: 'receptor + docked ligand merged', run: async () => {
        await downloadFile(`/api/docking/result/${dockingJobId}/complex.pdb`, `complex_${dockingJobId.slice(0, 8)}.pdb`);
      } },
      { id: 'sdf', label: 'Ligand SDF', hint: 'docked poses only', run: async () => {
        await downloadFile(`/api/docking/result/${dockingJobId}/ligand.sdf`, `docked_${dockingJobId.slice(0, 8)}.sdf`);
      } },
    );
  }

  const handle = async (item: (typeof items)[number]) => {
    setOpen(false);
    setBusy(item.id);
    try {
      await item.run();
      toast.success(`Downloaded ${item.label}`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: Blob | unknown; status?: number } }).response;
      if (detail?.status === 503) toast.error('PyMOL export unavailable on this deployment');
      else toast.error(`Export failed${detail?.status ? ` (HTTP ${detail.status})` : ''}`);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={busy !== null}
        title="Download structure files"
        className="rounded-md border border-glass-border bg-hud/40 px-2 py-1 text-xs text-text-secondary hover:bg-hud/60 hover:text-text-primary disabled:opacity-40 transition-colors flex items-center gap-1"
      >
        {busy
          ? <Warning className="w-3.5 h-3.5" />
          : <DownloadSimple className="w-3.5 h-3.5" />}
        {busy ? '…' : 'Export'}
        <CaretDown className="w-3 h-3" />
      </button>
      {open && (
        <>
          {/* click-away layer */}
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 z-30 min-w-[240px] rounded-lg border border-glass-border bg-viewer shadow-lg overflow-hidden">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => void handle(item)}
                className="w-full text-left px-3 py-2 hover:bg-surface-2 transition-colors"
              >
                <div className="text-xs font-medium text-text-primary">{item.label}</div>
                <div className="text-[10px] text-text-muted">{item.hint}</div>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
