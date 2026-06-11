export interface StreamEvent {
  chunk?: string;
  done?: boolean;
  error?: string;
  meta?: {
    model: string;
    pipeline_type: string;
  };
}
