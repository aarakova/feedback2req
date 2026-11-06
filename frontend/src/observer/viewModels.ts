// Presentation models only. These are neither HTTP DTOs nor AI contracts.
// A future approved adapter must supply project scope, coverage and real values.
export type ViewState<T> = { projectId: string } & (
  { status: 'unavailable'; message: string } | { status: 'loading' } |
  { status: 'error'; message: string } | { status: 'empty' } |
  { status: 'ready'; data: T } | { status: 'partial'; data: T; message: string }
);
export function unavailable<T>(projectId: string, message = 'Данные анализа пока недоступны.'): ViewState<T> {
  return { projectId, status: 'unavailable', message };
}
export function inProject<T>(state: ViewState<T>, projectId: string): ViewState<T> {
  return state.projectId === projectId ? state : unavailable(projectId, 'Данные другого проекта не отображаются.');
}
export function viewData<T>(state: ViewState<T>): T | undefined {
  return state.status === 'ready' || state.status === 'partial' ? state.data : undefined;
}
export type Decision = 'Draft' | 'Approved' | 'Rejected';
export type EvidenceState = 'available' | 'partial' | 'lost' | 'unknown';
export type VerificationState = 'current' | 'stale' | 'not_checked' | 'unavailable';
export interface EvidenceView {
  id: string; sourceLabel: string; state: 'available' | 'deleted' | 'unavailable';
  quote?: string; interpretation?: string; position?: string;
  source?: { kind: 'sources' | 'documents'; id: string };
  fragment?: { id: string; stateId: string; sourceStateId: string };
}
export interface IssueView {
  id: string; title: string; text: string; kind: 'remark' | 'question' | 'conflict';
  severity: string; blocking: boolean; open: boolean; resolution?: string;
  positions?: readonly { label: string; text: string }[];
}
export interface HistoryView { id: string; title: string; text?: string; author?: string; time?: string }
export interface RequirementSummary {
  id: string; title: string; decision: Decision | null; evidenceState: EvidenceState;
  verificationState: VerificationState; openBlockingIssues: boolean | null;
  // Explicit count for this requirement, not inferred from a partial issue list.
  openIssues?: number | null;
}
export interface RevisionView {
  revision: string; wording: string; rationale?: string; originLabel?: string;
  evidenceState: EvidenceState;
  evidence: readonly EvidenceView[]; context: readonly EvidenceView[];
  verificationState: VerificationState; coverage?: string;
  issues: readonly IssueView[]; history: readonly HistoryView[];
}
export interface RequirementView extends RequirementSummary, RevisionView { proposal?: RevisionView }
export interface RequirementsView { items: readonly RequirementView[] }
export interface ExtractionOutcomeView {
  synthetic: boolean; aiLabel: string; provider: string | null; model: string | null; coverage: string[];
  questions: { id: string; text: string; reason: string; blocking: boolean; links: { kind: string; id: string }[] }[];
  uncertainties: { id: string; reason: string; links: { kind: string; id: string }[] }[];
}
export interface FindingView {
  id: string; text: string; types: readonly string[]; originLabel: string;
  evidence: readonly EvidenceView[]; conflictsWith: readonly string[];
  requirementIds: readonly string[]; humanEdited?: boolean;
  extraction?: ExtractionOutcomeView & {
    stateId: string; attemptId: string; createdAt: string; freshness: string; stale: boolean;
  };
}
export interface GroupView {
  id: string; title: string; findingIds: readonly string[]; requirementIds: readonly string[];
  conflict: boolean; summary?: string;
}
export interface FindingsView {
  groups: readonly GroupView[]; findings: readonly FindingView[];
  requirements: readonly RequirementSummary[];
  requirementIssues?: readonly { requirementId: string; requirementTitle: string; issue: IssueView }[];
  groupsAvailable?: boolean; relationsAvailable?: boolean;
}
export interface OverviewView {
  // True only for explicit authoritative project aggregates, never page-derived totals.
  aggregatesAuthoritative: boolean;
  metrics: { requirements: number | null; approved: number | null; blockers: number | null; lostEvidence: number | null };
  decisions: { draft: number; approved: number; rejected: number } | null;
  // Confirmed comparison scale, not inferred from a paginated/partial group list.
  groupScaleMaximum?: number | null;
  groups: readonly { id: string; title: string; findings: number | null; requirements: number | null; openIssues?: number | null }[];
  attention: readonly RequirementSummary[];
  approvedEvidence: { available: number | null; partial: number | null; lost: number | null };
  coverage: string;
}
export type ProcessingStatus = 'unavailable' | 'waiting' | 'running' | 'partial' | 'error' | 'completed';
export type StageKey = 'preparation' | 'analysis' | 'generation' | 'verification';
export interface StageView { key: StageKey; status: ProcessingStatus; summary?: string; errors?: readonly string[] }
export interface ProcessingView {
  stages: readonly StageView[]; coverage?: string;
  // inspect_text belongs here, never to semantic analysis/generation/verification.
  technicalInspection?: { status: ProcessingStatus; summary: string };
}
export interface MaterialProcessingView {
  status: ProcessingStatus; errors?: readonly string[]; unreliableIntervals?: readonly string[];
}
