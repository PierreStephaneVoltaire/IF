import { useState } from 'react';

interface ImplementationPlanProps {
  plan: string | null;
  isGenerating?: boolean;
}

export function ImplementationPlan({ plan, isGenerating }: ImplementationPlanProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!plan) return;
    try {
      await navigator.clipboard.writeText(plan);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  if (isGenerating) {
    return (
      <div className="bg-blue-50 rounded-lg border border-blue-200 p-6 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3"></div>
        <p className="text-blue-700 font-medium">Generating implementation plan...</p>
        <p className="text-blue-600 text-sm mt-1">This may take a moment</p>
      </div>
    );
  }

  if (!plan) {
    return null;
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="bg-gray-100 px-4 py-2 border-b border-gray-200 flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Implementation Plan</h3>
        <button
          onClick={handleCopy}
          className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
        >
          {copied ? '✓ Copied!' : 'Copy Plan'}
        </button>
      </div>
      <div className="p-4">
        <div className="prose prose-sm max-w-none">
          <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-gray-50 p-4 rounded border border-gray-200 overflow-x-auto">
            {plan}
          </pre>
        </div>
      </div>
    </div>
  );
}
