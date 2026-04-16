import * as XLSX from 'xlsx'
import crypto from 'crypto'
import { AnalysisGateway } from '../ai/analysisGateway'
import { 
  stagePending, 
  getPending, 
  listPendingImports, 
  markImportApplied, 
  markImportRejected,
  existingPendingForType,
  existingByHash,
  putTemplate
} from '../db/dynamo'
import { transformImportPending } from '../db/transforms'
import type { ImportPending, ImportType } from '@powerlifting/types'
import { v4 as uuidv4 } from 'uuid'

export class ImportService {
  /**
   * Stage a new import by parsing and classifying a file buffer.
   */
  async stageImport({ buffer, filename, type }: { buffer: Buffer, filename: string, type: ImportType }): Promise<ImportPending> {
    const hash = this.computeHash(buffer)
    
    // 1. Hash check
    const existing = await existingByHash(hash, type)
    if (existing) {
      throw new Error(`This file has already been uploaded as a pending ${type} import.`)
    }

    // 2. Guard: one pending per type
    const pendingOfType = await existingPendingForType(type)
    if (pendingOfType) {
      throw new Error(`An import of type '${type}' is already awaiting review. Apply or reject it first.`)
    }

    // 3. Extract rows
    const { rows, sheetName } = this.extractRows(buffer, filename)
    
    // 4. Pre-classify (deterministic)
    let classification = this.preclassify(rows)
    let reasoning = 'Deterministic heuristic'
    
    // 5. If ambiguous -> AI classify
    if (!classification) {
      const aiClassify = await AnalysisGateway.classify(rows.slice(0, 30))
      classification = aiClassify.classification
      reasoning = aiClassify.reasoning
    }

    // 6. AI Parse
    const parseResult = await AnalysisGateway.parse(rows)
    
    // 7. Resolve Glossary (TODO: integrate Fuse.js resolution before AI)
    // For now, we rely on the AI parse result's glossary_ids or let the AI resolve it.
    // Plan says "Glossary resolve (fuzzy via Fuse.js, AI for misses)"

    // 8. Stage to DynamoDB
    const importId = uuidv4()
    const now = new Date().toISOString()
    const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
    
    const record: ImportPending = {
      pk: 'operator',
      sk: `import#pending#${importId}`,
      import_id: importId,
      import_type: type,
      status: 'awaiting_review',
      source_filename: filename,
      source_file_hash: hash,
      source_sheet_name: sheetName,
      classification: classification as any,
      ai_parse_result: parseResult,
      uploaded_at: now,
      expires_at: expiresAt,
      ttl: Math.floor(Date.now() / 1000) + 7 * 24 * 60 * 60,
    }

    await stagePending(record)
    return record
  }

  private computeHash(buffer: Buffer): string {
    const h = crypto.createHash('sha256').update(buffer).digest('hex')
    return `sha256:${h.substring(0, 16)}`
  }

  private extractRows(buffer: Buffer, filename: string): { rows: any[], sheetName: string } {
    const workbook = XLSX.read(buffer, { type: 'buffer' })
    const sheetName = workbook.SheetNames[0]
    const sheet = workbook.Sheets[sheetName]
    const rows = XLSX.utils.sheet_to_json(sheet)
    return { rows, sheetName }
  }

  private preclassify(rows: any[]): string | null {
    if (rows.length === 0) return null
    
    const firstRow = rows[0]
    const keys = Object.keys(firstRow).map(k => k.toLowerCase())
    
    // Heuristic 1: Dates
    const hasDates = rows.slice(0, 10).some(row => 
      Object.entries(row).some(([k, v]) => 
        k.toLowerCase().includes('date') && 
        (v instanceof Date || (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}/.test(v)))
      )
    )
    if (hasDates) return 'session_import'
    
    // Heuristic 2: Week/Day without dates
    const hasWeeks = keys.some(k => k.includes('week'))
    if (hasWeeks) return 'template'
    
    // Heuristic 3: RPE/%
    const hasLoadTargets = keys.some(k => k.includes('rpe') || k.includes('%') || k.includes('percentage') || k.includes('target'))
    if (hasLoadTargets) return 'template'
    
    return null
  }

  async listPending(): Promise<ImportPending[]> {
    return listPendingImports()
  }

  async get(importId: string): Promise<ImportPending | null> {
    const item = await getPending(importId)
    return item ? transformImportPending(item as any) : null
  }

  async apply(importId: string, strategy: string, conflicts?: any, startDate?: string): Promise<{ program_sk?: string, template_sk?: string }> {
    const record = await this.get(importId)
    if (!record) throw new Error(`Import ${importId} not found`)
    
    if (record.classification === 'template') {
      // ... existing template logic ...
      const templateSk = await putTemplate({
        pk: 'operator',
        sk: '', // Will be assigned in putTemplate/TemplateService
        meta: {
          name: record.source_filename.split('.')[0],
          source_filename: record.source_filename,
          source_file_hash: record.source_file_hash,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          archived: false,
          estimated_weeks: record.ai_parse_result.phases.reduce((acc: number, p: any) => Math.max(acc, p.end_week), 0),
          days_per_week: 4, // Estimate or extract from parseResult
        },
        phases: record.ai_parse_result.phases,
        sessions: record.ai_parse_result.sessions,
        required_maxes: record.ai_parse_result.required_maxes,
      } as any)
      
      await markImportApplied(importId, new Date().toISOString())
      return { template_sk: templateSk }
    } else {
      // Session Import -> Program
      // Delegate to Python tool for complex merging/versioning logic
      const { invokeToolDirect } = require('../utils/agent')
      return invokeToolDirect('import_apply', {
        import_id: importId,
        merge_strategy: strategy,
        conflict_resolutions: conflicts,
        start_date: startDate,
      })
    }
  }

  async reject(importId: string, reason?: string): Promise<void> {
    await markImportRejected(importId, reason || null)
  }
}

export const importService = new ImportService()
