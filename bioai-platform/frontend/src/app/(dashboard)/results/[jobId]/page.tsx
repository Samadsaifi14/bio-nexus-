import { redirect } from 'next/navigation';

export default function ResultsRedirect({ params }: { params: { jobId: string } }) {
  redirect(`/jobs/${params.jobId}`);
}
