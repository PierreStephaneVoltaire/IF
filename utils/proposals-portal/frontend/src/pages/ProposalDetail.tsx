import { useParams, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';
import { ProposalDetailPanel } from '../components/ProposalDetailPanel';
import { useProposalsStore } from '../store/proposalsStore';
import { useWebSocket } from '../hooks/useWebSocket';

export default function ProposalDetail() {
  const { sk } = useParams<{ sk: string }>();
  const navigate = useNavigate();
  const { selectedProposal, loading, error, loadProposal } = useProposalsStore();

  // Connect to WebSocket for real-time plan updates
  useWebSocket();

  useEffect(() => {
    if (sk) {
      loadProposal(decodeURIComponent(sk));
    }
  }, [sk, loadProposal]);

  if (loading && !selectedProposal) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p className="text-gray-500 mt-3">Loading proposal...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{error}</p>
        <button
          onClick={() => navigate('/')}
          className="mt-4 text-blue-600 hover:text-blue-800"
        >
          ← Back to Board
        </button>
      </div>
    );
  }

  if (!selectedProposal) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Proposal not found</p>
        <button
          onClick={() => navigate('/')}
          className="mt-4 text-blue-600 hover:text-blue-800"
        >
          ← Back to Board
        </button>
      </div>
    );
  }

  return (
    <ProposalDetailPanel
      proposal={selectedProposal}
      onBack={() => navigate('/')}
    />
  );
}
