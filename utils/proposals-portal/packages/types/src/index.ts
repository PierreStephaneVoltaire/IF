// Shared types for Proposals Portal

export type ProposalType =
  | 'new_directive'
  | 'rewrite_directive'
  | 'deprecate_directive'
  | 'new_tool'
  | 'system_observation';

export type ProposalStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'implemented';

export type ProposalAuthor = 'agent' | 'user';

export interface Proposal {
  pk: string;
  sk: string;
  type: ProposalType;
  status: ProposalStatus;
  author: ProposalAuthor;
  title: string;
  rationale: string;
  content: string;
  target_id: string | null;
  implementation_plan: string | null;
  created_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  rejection_reason: string | null;
}

export interface CreateProposalInput {
  type: ProposalType;
  title: string;
  rationale: string;
  content: string;
  target_id?: string;
}

export interface ProposalFilters {
  status?: ProposalStatus;
  type?: ProposalType;
  author?: ProposalAuthor;
  q?: string;
}

export interface ImplementationPlan {
  affected_files: string[];
  steps: ImplementationStep[];
  test_steps: string[];
  rollback_notes?: string;
}

export interface ImplementationStep {
  order: number;
  description: string;
  file_path?: string;
  code_snippet?: string;
}

export interface Directive {
  pk: string;
  sk: string;
  alpha: number;
  beta: number;
  label: string;
  content: string;
  types: string[];
  version: number;
  active: boolean;
  created_by: string;
  created_at: string;
  superseded_at: string | null;
}

// API Response types
export interface ProposalsListResponse {
  proposals: Proposal[];
  total: number;
}

export interface ProposalResponse {
  proposal: Proposal;
}

export interface DirectivesListResponse {
  directives: Directive[];
  total: number;
}

export interface DirectiveResponse {
  directive: Directive;
}

export interface GeneratePlanResponse {
  success: boolean;
  plan: string | null;
  error?: string;
}

export interface RejectProposalInput {
  reason: string;
}

// WebSocket event types
export type WebSocketEventType =
  | 'plan_generating'
  | 'plan_ready'
  | 'plan_failed';

export interface WebSocketEvent {
  type: WebSocketEventType;
  sk: string;
  plan?: string;
  error?: string;
}

// Type badge colors
export const TYPE_BADGE_COLORS: Record<ProposalType, string> = {
  new_directive: 'bg-blue-500',
  rewrite_directive: 'bg-yellow-500',
  deprecate_directive: 'bg-red-500',
  new_tool: 'bg-green-500',
  system_observation: 'bg-purple-500',
};

export const TYPE_LABELS: Record<ProposalType, string> = {
  new_directive: 'New Directive',
  rewrite_directive: 'Rewrite Directive',
  deprecate_directive: 'Deprecate Directive',
  new_tool: 'New Tool',
  system_observation: 'System Observation',
};

export const STATUS_COLORS: Record<ProposalStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  approved: 'bg-green-100 text-green-800 border-green-300',
  rejected: 'bg-red-100 text-red-800 border-red-300',
  implemented: 'bg-blue-100 text-blue-800 border-blue-300',
};
