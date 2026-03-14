import { useState } from 'react';
import { ProposalFilters, ProposalType, ProposalAuthor, TYPE_LABELS } from '../types';

interface FilterBarProps {
  filters: ProposalFilters;
  onFilterChange: (filters: ProposalFilters) => void;
}

export function FilterBar({ filters, onFilterChange }: FilterBarProps) {
  const [searchQuery, setSearchQuery] = useState(filters.q || '');

  const handleFilterChange = (key: keyof ProposalFilters, value: string) => {
    const newFilters = { ...filters };
    if (value === '') {
      delete newFilters[key];
    } else {
      newFilters[key] = value as any;
    }
    onFilterChange(newFilters);
  };

  const handleSearch = () => {
    onFilterChange({ ...filters, q: searchQuery || undefined });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const clearFilters = () => {
    setSearchQuery('');
    onFilterChange({});
  };

  const hasActiveFilters = Object.keys(filters).length > 0;

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
      <div className="flex flex-wrap gap-4 items-end">
        {/* Search */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Search
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search title or rationale..."
              className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
            />
            <button
              onClick={handleSearch}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700"
            >
              Search
            </button>
          </div>
        </div>

        {/* Type Filter */}
        <div className="min-w-[150px]">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Type
          </label>
          <select
            value={filters.type || ''}
            onChange={(e) => handleFilterChange('type', e.target.value)}
            className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
          >
            <option value="">All Types</option>
            {Object.entries(TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        {/* Author Filter */}
        <div className="min-w-[120px]">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Author
          </label>
          <select
            value={filters.author || ''}
            onChange={(e) => handleFilterChange('author', e.target.value)}
            className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
          >
            <option value="">All Authors</option>
            <option value="agent">🤖 Agent</option>
            <option value="user">👤 You</option>
          </select>
        </div>

        {/* Clear Filters */}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="px-3 py-1.5 text-gray-600 hover:text-gray-900 text-sm"
          >
            Clear Filters
          </button>
        )}
      </div>
    </div>
  );
}
