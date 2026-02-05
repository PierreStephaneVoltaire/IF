import type { FormattedHistory, ProcessedAttachment, FilterContext } from '../types';

export interface FlowContext {
  workspaceId: string;
  channelId: string;
  messageId: string;
  history: FormattedHistory;
  filterContext: FilterContext;
  isProjectChannel: boolean;
  needsWorkspace: boolean;
  executionId: string;
  userAddedFilesMessage?: string; // NEW: Message about newly synced files
  parentName?: string | null;
}

export interface FlowResult {
  response: string;
  model: string;
  branchName?: string;
  responseChannelId: string;
}
