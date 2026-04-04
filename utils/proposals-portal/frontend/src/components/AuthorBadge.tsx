import { ProposalAuthor } from '../types';

interface AuthorBadgeProps {
  author: ProposalAuthor;
  className?: string;
}

export function AuthorBadge({ author, className = '' }: AuthorBadgeProps) {
  const isAgent = author === 'agent';

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
        isAgent
          ? 'bg-purple-100 text-purple-800'
          : 'bg-gray-100 text-gray-800'
      } ${className}`}
    >
      {isAgent ? '🤖 Agent' : '👤 You'}
    </span>
  );
}
