import { useEffect, useState } from 'react'
import { useDiaryStore } from '../store/diaryStore'
import { Trash2, Edit2, X, Check } from 'lucide-react'
import { formatDateTime, formatRelativeTime } from '../utils/formatters'

export function EntriesPanel() {
  const { entries, loading, error, fetchEntries, updateEntry, deleteEntry } = useDiaryStore()
  const [editingEntry, setEditingEntry] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null)

  useEffect(() => {
    fetchEntries()
  }, [fetchEntries])

  const handleEdit = (sk: string, content: string) => {
    setEditingEntry(sk)
    setEditContent(content)
  }

  const handleSave = async (sk: string) => {
    await updateEntry(sk, editContent)
    setEditingEntry(null)
    setEditContent('')
  }

  const handleCancel = () => {
    setEditingEntry(null)
    setEditContent('')
  }

  const handleDelete = async (sk: string) => {
    if (confirm('Are you sure you want to delete this entry?')) {
      await deleteEntry(sk)
    }
  }

  if (loading && entries.length === 0) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 animate-pulse">
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-32 bg-gray-800 rounded"></div>
          ))}
        </div>
      </div>
    )
  }

  if (entries.length === 0) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 text-center">
        <p className="text-gray-500">No entries yet. Write one to get started.</p>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-800 border-b border-gray-700">
        <h2 className="font-semibold text-gray-200">
          Your Entries ({entries.length})
        </h2>
        <p className="text-xs text-gray-400 mt-1">
          Entries expire after 3 days
        </p>
      </div>

      {error && (
        <div className="mx-4 mt-4 p-3 bg-red-900/50 border border-red-800 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="max-h-[600px] overflow-y-auto">
        <div className="divide-y divide-gray-800">
          {entries.map((entry) => (
            <div key={entry.sk} className="p-4 hover:bg-gray-800/50 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs text-gray-400" title={formatDateTime(entry.created_at)}>
                      {formatRelativeTime(entry.created_at)}
                    </span>
                    <span className="text-xs text-gray-500">
                      • {Math.ceil((entry.expires_at * 1000 - Date.now()) / (1000 * 60 * 60 * 24))} days left
                    </span>
                  </div>

                  {editingEntry === entry.sk ? (
                    <div className="space-y-3">
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[100px] resize-y"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSave(entry.sk)}
                          disabled={!editContent.trim()}
                          className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
                        >
                          <Check className="w-4 h-4" />
                          Save
                        </button>
                        <button
                          onClick={handleCancel}
                          className="flex items-center gap-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm font-medium rounded-lg transition-colors"
                        >
                          <X className="w-4 h-4" />
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      <p
                        className={`text-sm text-gray-300 whitespace-pre-wrap break-words ${
                          expandedEntry === entry.sk ? '' : 'line-clamp-3'
                        }`}
                      >
                        {entry.content}
                      </p>
                      {entry.content.length > 200 && (
                        <button
                          onClick={() => setExpandedEntry(expandedEntry === entry.sk ? null : entry.sk)}
                          className="text-xs text-blue-400 hover:text-blue-300 mt-2"
                        >
                          {expandedEntry === entry.sk ? 'Show less' : 'Show more'}
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {editingEntry !== entry.sk && (
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => handleEdit(entry.sk, entry.content)}
                      className="p-1.5 text-gray-400 hover:text-blue-400 hover:bg-gray-800 rounded-lg transition-colors"
                      title="Edit"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(entry.sk)}
                      className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-800 rounded-lg transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
