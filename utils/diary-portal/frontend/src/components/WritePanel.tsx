import { useState } from 'react'
import { useDiaryStore } from '../store/diaryStore'
import { Send, Loader2, CheckCircle } from 'lucide-react'

const MAX_CHARS = 10000

export function WritePanel() {
  const [content, setContent] = useState('')
  const { submitEntry, loading, submitSuccess, error } = useDiaryStore()

  const charCount = content.length
  const isOverLimit = charCount > MAX_CHARS

  const handleSubmit = async () => {
    if (!content.trim() || isOverLimit) return

    const result = await submitEntry(content.trim())

    // Clear on success
    if (result.ok) {
      setContent('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Submit on Ctrl+Enter or Cmd+Enter
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      handleSubmit()
    }
  }

  return (
    <div className="space-y-4">
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Write it down. It won't be here in 3 days."
        className="write-textarea"
        disabled={loading}
      />

      {/* Footer with char count and submit */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-500">
          <span className={isOverLimit ? 'text-red-400' : ''}>
            {charCount.toLocaleString()}
          </span>
          <span className="text-gray-600"> / {MAX_CHARS.toLocaleString()} chars</span>
        </div>

        <button
          onClick={handleSubmit}
          disabled={!content.trim() || isOverLimit || loading}
          className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 disabled:text-gray-600 rounded-lg transition-colors text-sm font-medium"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              Submit & Let Go
            </>
          )}
        </button>
      </div>

      {/* Success message */}
      {submitSuccess && (
        <div className="flex items-center gap-2 text-green-400 text-sm">
          <CheckCircle className="w-4 h-4" />
          Done. The agent will process this.
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="text-red-400 text-sm">Error: {error}</div>
      )}

      {/* Hint */}
      <p className="text-gray-600 text-xs">
        Press <kbd className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-400">Ctrl</kbd> + <kbd className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-400">Enter</kbd> to submit
      </p>
    </div>
  )
}
