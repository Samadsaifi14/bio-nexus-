import { redirect } from 'next/navigation';

export default async function ResultsRedirect({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  redirect(`/jobs/${jobId}`);
}
