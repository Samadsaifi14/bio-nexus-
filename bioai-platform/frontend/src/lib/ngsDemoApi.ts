import { api } from './api';

export type NgsDemoCatalogItem = {
  id: string;
  label: string;
  assay: string;
  description: string;
  purpose: string;
  read_pairs: number;
  read_length: number;
  paired_end: boolean;
  truth_bearing: boolean;
  downloads: { r1: string; r2: string; reference?: string };
};

export async function getNgsDemoCatalog(): Promise<NgsDemoCatalogItem[]> {
  const response = await api.get('/api/ngs/v2/demos/catalog');
  return Array.isArray(response.data?.demos) ? response.data.demos : [];
}

export async function downloadNgsDemoFile(profile: string, kind: 'r1' | 'r2' | 'reference'): Promise<void> {
  const response = await api.get(`/api/ngs/v2/demos/${encodeURIComponent(profile)}/download/${kind}`, {
    responseType: 'blob',
  });
  const disposition = String(response.headers?.['content-disposition'] ?? '');
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match?.[1] ?? `${profile}_${kind}.txt`;
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
