import { useState, useEffect } from 'react';
import { Proposal, Directive } from '../types';
import { TypeBadge } from './TypeBadge';
import { AuthorBadge } from './AuthorBadge';
import { StatusBadge } from './StatusBadge';
import { DirectivePreview } from './DirectivePreview';
import { ImplementationPlan } from './ImplementationPlan';
import { useProposalsStore } from '../store/proposalsStore';
import { formatDateTime } from '../utils/formatters';

interface ProposalDetailPanelProps {
  proposal: Proposal;
  onBack?: () => void;
}

export function ProposalDetailPanel({ proposal, onBack }: ProposalDetailPanelProps) {
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
  const [targetDirective, setTargetDirective] = useState<Directive | null>(null);
  const [loadingDirective, setLoadingDirective] = useState(false);

  const {
    approveProposal,
    rejectProposal,
    deleteProposal,
    loadDirective,
    loading,
  } = useProposalsStore();

  useEffect(() => {
    if (proposal.target_id) {
      setLoadingDirective(true);
      loadDirective(proposal.target_id)
        .then(() => {
          const store = useProposalsStore.getState();
          setTargetDirective(store.selectedDirective);
        })
        .finally(() => setLoadingDirective(false));
    }
  }, [proposal.target_id, loadDirective]);

  const handleApprove = async () => {
    if (window.confirm('Approve this proposal? This will trigger plan generation.')) {
      await approveProposal(proposal.sk);
      setIsGeneratingPlan(true);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      setShowRejectInput(true);
      return;
    }
    await rejectProposal(proposal.sk, rejectReason);
    setShowRejectInput(false);
    setRejectReason('');
  };

  const handleDelete = async () => {
    if (window.confirm('Delete this proposal? This cannot be undone.')) {
      await deleteProposal(proposal.sk);
      onBack?.();
    }
  };

  const isPending = proposal.status === 'pending';
  const isApproved = proposal.status === 'approved';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <TypeBadge type={proposal.type} />
            <AuthorBadge author={proposal.author} />
            <StatusBadge status={proposal.status} />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">{proposal.title}</h1>
          <p className="text-sm text-gray-500 mt-1">
            Created {formatDateTime(proposal.created_at)}
          </p>
        </div>

        {onBack && (
          <button
            onClick={onBack}
            className="text-gray-500 hover:text-gray-700"
          >
            ← Back to Board
          </button>
        )}
      </div>

      {/* Rationale */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-900 mb-2">Rationale</h3>
        <p className="text-gray-700 whitespace-pre-wrap">{proposal.rationale}</p>
      </div>

      {/* Proposed Content */}
      {proposal.content && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-900 mb-2">Proposed Content</h3>
          <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-gray-50 p-4 rounded border border-gray-200 font-mono">
            {proposal.content}
          </pre>
        </div>
      )}

      {/* Target Directive Context (for rewrite/deprecate) */}
      {proposal.target_id && (
        <div>
          <h3 className="font-semibold text-gray-900 mb-2">Current Directive</h3>
          <DirectivePreview directive={targetDirective} loading={loadingDirective} />
        </div>
      )}

      {/* Rejection Reason */}
      {proposal.status === 'rejected' && proposal.rejection_reason && (
        <div className="bg-red-50 rounded-lg border border-red-200 p-4">
          <h3 className="font-semibold text-red-900 mb-2">Rejection Reason</h3>
          <p className="text-red-700">{proposal.rejection_reason}</p>
        </div>
      )}

      {/* Implementation Plan */}
      {isApproved && (
        <ImplementationPlan
          plan={proposal.implementation_plan}
          isGenerating={isGeneratingPlan && !proposal.implementation_plan}
        />
      )}

      {/* Actions */}
      {isPending && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-900 mb-3">Actions</h3>

          {!showRejectInput ? (
            <div className="flex gap-3">
              <button
                onClick={handleApprove}
                disabled={loading}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
              >
                {loading ? 'Processing...' : 'Approve'}
              </button>
              <button
                onClick={() => setShowRejectInput(true)}
                disabled={loading}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
              >
                Reject
              </button>
              <button
                onClick={handleDelete}
                disabled={loading}
                className="px-4 py-2 text-gray-600 hover:text-red-600"
              >
                Delete
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Enter rejection reason..."
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
                rows={2}
              />
              <div className="flex gap-3">
                <button
                  onClick={handleReject}
                  disabled={loading || !rejectReason.trim()}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
                >
                  Confirm Rejection
                </button>
                <button
                  onClick={() => {
                    setShowRejectInput(false);
                    setRejectReason('');
                  }}
                  className="px-4 py-2 text-gray-600 hover:text-gray-900"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Resolution Info */}
      {proposal.resolved_at && (
        <div className="text-sm text-gray-500">
          Resolved {formatDateTime(proposal.resolved_at)} by {proposal.resolved_by}
        </div>
      )}
    </div>
  );
}
