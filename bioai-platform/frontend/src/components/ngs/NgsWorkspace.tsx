import RnaSeqWorkflow from './RnaSeqWorkflow';
import NextflowRunnerPanel from './NextflowRunnerPanel';

export default function NgsWorkspace() {
  return (
    <div className="space-y-10">
      <RnaSeqWorkflow />
      <NextflowRunnerPanel />
    </div>
  );
}
