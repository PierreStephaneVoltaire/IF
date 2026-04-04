import { Proposal, ProposalStatus, STATUS_LABELS } from '../types';
import { ProposalCard } from './ProposalCard';

interface KanbanColumnProps {
  title: string;
  status: ProposalStatus;
  proposals: Proposal[];
  color: string;
}

export function KanbanColumn({ title, status, proposals, color }: KanbanColumnProps) {
  const filteredProposals = proposals.filter((p) => p.status === status);

  return (
    <div className="flex-1 min-w-[300px]">
      <div className={`${color} rounded-t-lg px-4 py-2`}>
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-white">{title}</h2>
          <span className="bg-white/20 text-white text-sm px-2 py-0.5 rounded">
            {filteredProposals.length}
          </span>
        </div>
      </div>

      <div className="bg-gray-50 rounded-b-lg p-4 min-h-[400px] space-y-3 border border-t-0 border-gray-200">
        {filteredProposals.length === 0 ? (
          <p className="text-center text-gray-500 text-sm py-8">No proposals</p>
        ) : (
          filteredProposals.map((proposal) => (
            <ProposalCard key={proposal.sk} proposal={proposal} />
          ))
        )}
      </div>
    </div>
  );
}
