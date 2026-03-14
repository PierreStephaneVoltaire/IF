import { useState, useEffect } from 'react';
import { CreateProposalInput, ProposalType, Directive, TYPE_LABELS } from '../types';
import { useProposalsStore } from '../store/proposalsStore';

interface NewProposalModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function NewProposalModal({ isOpen, onClose }: NewProposalModalProps) {
  const [type, setType] = useState<ProposalType>('system_observation');
  const [title, setTitle] = useState('');
  const [rationale, setRationale] = useState('');
  const [content, setContent] = useState('');
  const [targetId, setTargetId] = useState('');
  const [error, setError] = useState('');

  const { createProposal, loadDirectives, directives, loading } = useProposalsStore();

  useEffect(() => {
    if (isOpen) {
      loadDirectives();
    }
  }, [isOpen, loadDirectives]);

  const showTargetSelect = type === 'rewrite_directive' || type === 'deprecate_directive';
  const requiresContent = type !== 'system_observation';

  const resetForm = () => {
    setType('system_observation');
    setTitle('');
    setRationale('');
    setContent('');
    setTargetId('');
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!title.trim()) {
      setError('Title is required');
      return;
    }
    if (!rationale.trim()) {
      setError('Rationale is required');
      return;
    }
    if (requiresContent && !content.trim()) {
      setError('Content is required for this proposal type');
      return;
    }
    if (showTargetSelect && !targetId) {
      setError('Target directive is required for this proposal type');
      return;
    }

    try {
      await createProposal({
        type,
        title: title.trim(),
        rationale: rationale.trim(),
        content: content.trim(),
        target_id: targetId || undefined,
      });
      resetForm();
      onClose();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">New Proposal</h2>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="bg-red-50 text-red-800 px-4 py-2 rounded-md text-sm">
              {error}
            </div>
          )}

          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Type
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as ProposalType)}
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              {Object.entries(TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Target (for rewrite/deprecate) */}
          {showTargetSelect && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Target Directive
              </label>
              <select
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              >
                <option value="">Select a directive...</option>
                {directives.map((d) => (
                  <option key={d.sk} value={d.sk}>
                    {d.label} (v{d.version})
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., CONTEXT_WINDOW_DISCIPLINE"
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </div>

          {/* Rationale */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Rationale
            </label>
            <textarea
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              rows={3}
              placeholder="Why should this proposal be implemented?"
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </div>

          {/* Content */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Proposed Content {requiresContent && <span className="text-red-500">*</span>}
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={6}
              placeholder="The actual proposed text (directive content, tool spec, etc.)"
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 font-mono text-sm"
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-gray-700 hover:text-gray-900"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Proposal'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
