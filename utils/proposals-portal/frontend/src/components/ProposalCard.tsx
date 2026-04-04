import { useNavigate } from 'react-router-dom';
import { Proposal } from '../types';
import { TypeBadge } from './TypeBadge';
import { AuthorBadge } from './AuthorBadge';
import { formatDate, truncateText } from '../utils/formatters';

interface ProposalCardProps {
  proposal: Proposal;
}

export function ProposalCard({ proposal }: ProposalCardProps) {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/proposal/${encodeURIComponent(proposal.sk)}`);
  };

  return (
    <div
      onClick={handleClick}
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 cursor-pointer hover:shadow-md hover:border-blue-300 transition-shadow"
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <TypeBadge type={proposal.type} />
          <AuthorBadge author={proposal.author} />
        </div>
        <span className="text-xs text-gray-500">{formatDate(proposal.created_at)}</span>
      </div>

      <h3 className="font-semibold text-gray-900 mb-2">{proposal.title}</h3>

      <p className="text-sm text-gray-600 mb-3">
        {truncateText(proposal.rationale, 120)}
      </p>

      <button
        className="text-sm text-blue-600 hover:text-blue-800 font-medium"
      >
        View & Decide →
      </button>
    </div>
  );
}
