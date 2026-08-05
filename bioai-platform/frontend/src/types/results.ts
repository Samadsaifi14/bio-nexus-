export interface StreamEvent {
  chunk?: string;
  done?: boolean;
  error?: string;
  notice?: string;
  meta?: {
    model: string;
    pipeline_type: string;
  };
}
