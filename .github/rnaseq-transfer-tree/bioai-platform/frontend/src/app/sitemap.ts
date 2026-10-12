import type { MetadataRoute } from 'next';
import { SITE_URL } from '@/lib/seo';

const PUBLIC_ROUTES = [
  '/',
  '/analyze',
  '/wizard',
  '/learn',
  '/analyze/blast',
  '/analyze/alignment',
  '/analyze/pairwise',
  '/analyze/compare',
  '/analyze/docking',
  '/analyze/domains',
  '/analyze/function',
  '/analyze/interactions',
  '/analyze/md',
  '/analyze/pathway',
  '/analyze/phylo',
  '/analyze/primers',
  '/analyze/sequencing',
  '/analyze/structure',
  '/analyze/uniprot',
  '/analyze/admet',
] as const;

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return PUBLIC_ROUTES.map((path) => ({
    url: new URL(path, SITE_URL).toString(),
    lastModified,
    changeFrequency: path === '/' ? 'weekly' : 'monthly',
    priority: path === '/' ? 1 : path === '/analyze' ? 0.9 : 0.7,
  }));
}
