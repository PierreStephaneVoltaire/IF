import { Directive } from '../types';

interface DirectivePreviewProps {
  directive: Directive | null;
  loading?: boolean;
}

export function DirectivePreview({ directive, loading }: DirectivePreviewProps) {
  if (loading) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-2"></div>
        <div className="h-4 bg-gray-200 rounded w-full mb-1"></div>
        <div className="h-4 bg-gray-200 rounded w-3/4"></div>
      </div>
    );
  }

  if (!directive) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 text-gray-500 text-sm">
        Directive not found
      </div>
    );
  }

  return (
    <div className="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden">
      <div className="bg-gray-100 px-4 py-2 border-b border-gray-200">
        <h4 className="font-medium text-gray-900">
          {directive.label} <span className="text-gray-500 text-sm">(v{directive.version})</span>
        </h4>
        <p className="text-xs text-gray-500">
          Alpha: {directive.alpha} | Beta: {directive.beta} | Types: {directive.types.join(', ')}
        </p>
      </div>
      <div className="p-4">
        <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono">
          {directive.content}
        </pre>
      </div>
    </div>
  );
}
