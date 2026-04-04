import { useState, useEffect } from 'react';
import { KanbanColumn } from '../components/KanbanColumn';
import { FilterBar } from '../components/FilterBar';
import { NewProposalModal } from '../components/NewProposalModal';
import { useProposalsStore } from '../store/proposalsStore';
import { useWebSocket } from '../hooks/useWebSocket';
import { ProposalFilters } from '../types';

export default function Board() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const { proposals, loading, filters, loadProposals } = useProposalsStore();

  // Connect to WebSocket for real-time updates
  useWebSocket();

  useEffect(() => {
    loadProposals();
  }, [loadProposals]);

  const handleFilterChange = (newFilters: ProposalFilters) => {
    loadProposals(newFilters);
  };

  return (
    <div>
      {/* Header Actions */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Proposal Board</h2>
          <p className="text-sm text-gray-500">
            {proposals.length} total proposals
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center gap-2"
        >
          <span>+</span>
          New Proposal
        </button>
      </div>

      {/* Filters */}
      <FilterBar filters={filters} onFilterChange={handleFilterChange} />

      {/* Loading State */}
      {loading && proposals.length === 0 && (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-gray-500 mt-3">Loading proposals...</p>
        </div>
      )}

      {/* Kanban Board */}
      {!loading && proposals.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <p className="text-gray-500">No proposals yet.</p>
          <button
            onClick={() => setIsModalOpen(true)}
            className="mt-4 text-blue-600 hover:text-blue-800"
          >
            Create your first proposal
          </button>
        </div>
      ) : (
        <div className="flex gap-6 overflow-x-auto pb-4">
          <KanbanColumn
            title="Pending"
            status="pending"
            proposals={proposals}
            color="bg-yellow-500"
          />
          <KanbanColumn
            title="Approved"
            status="approved"
            proposals={proposals}
            color="bg-green-500"
          />
          <KanbanColumn
            title="Rejected"
            status="rejected"
            proposals={proposals}
            color="bg-red-500"
          />
        </div>
      )}

      {/* New Proposal Modal */}
      <NewProposalModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
}
