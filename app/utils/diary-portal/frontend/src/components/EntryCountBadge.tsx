import { useDiaryStore } from '../store/diaryStore'
import { FileText } from 'lucide-react'

export function EntryCountBadge() {
  const { entryCount } = useDiaryStore()

  return (
    <div className="flex items-center gap-2 text-gray-500 text-sm">
      <FileText className="w-4 h-4" />
      <span>
        <span className="text-gray-300 font-medium">{entryCount}</span> active{' '}
        {entryCount === 1 ? 'entry' : 'entries'}
      </span>
      <span className="text-gray-600">• expires in 3 days</span>
    </div>
  )
}
