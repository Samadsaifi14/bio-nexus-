export type AuditEvent = {
  session_id: string;
  user_id: string | null;
  step: string;
  tool: string;
  status: "started" | "success" | "failed" | "partial";
  input_summary: string;
  output_summary: string;
  duration_ms: number;
  metadata?: Record<string, unknown>;
  timestamp: string;
};

export type AuditInsight = {
  id: string;
  session_id: string;
  triggered_by: string | null;
  severity: "info" | "warning" | "critical";
  insight: string;
  affected_steps: string[];
  suggestion: string;
  raw_audit: { events: AuditEvent[]; anomalies: string[] };
  created_at: string;
};
