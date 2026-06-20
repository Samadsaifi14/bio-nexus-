import { AnalysisWizard } from "@/components/wizard/AnalysisWizard";

export default function WizardPage() {
  return (
    <div className="min-h-screen pt-8">
      <div className="text-center mb-10">
        <h1 className="text-3xl font-bold text-text-primary">Guided Analysis</h1>
        <p className="text-text-muted mt-2">Step-by-step bioinformatics pipeline</p>
      </div>
      <AnalysisWizard />
    </div>
  );
}
