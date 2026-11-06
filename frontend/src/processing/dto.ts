// Existing TEXT_PROCESSING_API transport shapes; these are not Observer view models.
export type Operation = 'inspect_text' | 'extract_feedback';
export type UnitState = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
export type RunState = UnitState | 'partial';
export type ReasonCode = 'provider_not_configured' | 'provider_error' | 'invalid_response' | 'execution_error'
  | 'lease_expired' | 'deadline_exceeded' | 'input_changed' | 'access_revoked';
export interface InputRef { kind: 'source' | 'document'; id: string; state_id: string }
export interface StartCommand { operation: Operation; inputs: InputRef[] }
export interface CoverageDTO {
  input_key: string; reviewed: boolean;
  disposition: 'completed' | 'insufficient_information' | 'not_processed'; reason?: string;
}
export interface ResultLinkDTO { origin: 'input' | 'output'; key: string; id: string }
export interface UncertaintyDTO { local_id: string; related: ResultLinkDTO[]; reason: string }
export interface QuestionDTO extends UncertaintyDTO { text: string; blocking: boolean }
export interface AnnotationsDTO { questions: QuestionDTO[]; uncertainties: UncertaintyDTO[] }
export interface AttemptDTO {
  id: string; request_id: string; state: Exclude<UnitState, 'queued'>;
  started_at: string; finished_at: string | null; reason_code: ReasonCode | null;
  provider: string | null; model: string | null; synthetic: boolean; ai_performed: boolean | null;
  coverage: CoverageDTO[] | null; annotations: AnnotationsDTO | null;
  finding_ids: string[]; fragment_ids: string[];
  technical_result: { character_count: number; utf8_byte_count: number } | null;
}
export interface UnitDTO { id: string; input: InputRef; state: UnitState; retry_of_attempt_id: string | null; attempt: AttemptDTO | null }
export interface RunDTO { id: string; operation: Operation; created_at: string; execution_kind: 'technical' | 'semantic'; state: RunState; units: UnitDTO[] }
export interface SourceRefDTO { kind: 'feedback_source'; id: string; state_id: string }
export interface FragmentDTO {
  id: string; state_id: string; attempt_id: string; source_ref: SourceRefDTO; text_ref: SourceRefDTO;
  quote: string; locator: { start: number; end: number }; reliability: 'usable';
}
export interface FindingDTO {
  id: string; state_id: string; text: string; types: ('problem' | 'request' | 'observation' | 'need')[];
  mode: 'direct' | 'inferred'; authorship: 'ai'; synthetic: boolean; attempt_id: string;
  created_at: string; freshness: 'current' | 'requires_update'; evidence: FragmentDTO[];
  coverage: CoverageDTO[] | null; annotations: AnnotationsDTO | null;
  provider: string | null; model: string | null; ai_performed: boolean | null;
}
export interface OverviewDTO {
  project_id: string; calculated_at: string;
  material_counts: { text_sources: number; product_documents: number };
  semantic_metrics: { availability: 'not_implemented' };
  processing: { availability: 'available'; latest_run_id: string | null };
}
export const INPUT_LIMIT = 32;
export const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const activeRun = (run: RunDTO) => run.state === 'queued' || run.state === 'running';

