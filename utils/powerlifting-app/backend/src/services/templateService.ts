import { GetCommand, PutCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import { AnalysisGateway } from '../ai/analysisGateway'
import type { Template, TemplateListEntry, Program } from '@powerlifting/types'
import { v4 as uuidv4 } from 'uuid'

const PK = 'operator'
const INDEX_SK = 'template#current_list'
const TEMPLATE_SK_PREFIX = 'template#v'
const GLOSSARY_SK = 'glossary#v1'

export class TemplateService {
  /**
   * Get all templates (default excludes archived)
   */
  async listTemplates(includeArchived: boolean = false): Promise<TemplateListEntry[]> {
    const command = new GetCommand({
      TableName: TABLE,
      Key: { pk: PK, sk: INDEX_SK },
    })

    const result = await docClient.send(command)
    if (!result.Item) return []

    const templates: TemplateListEntry[] = result.Item.templates || []
    if (!includeArchived) {
      return templates.filter(t => !t.archived)
    }
    return templates
  }

  /**
   * Get a template by SK
   */
  async getTemplate(sk: string): Promise<Template | null> {
    const command = new GetCommand({
      TableName: TABLE,
      Key: { pk: PK, sk },
    })

    const result = await docClient.send(command)
    if (!result.Item) return null

    const { pk, sk: _sk, ...template } = result.Item
    return template as Template
  }

  /**
   * Create a new template version
   */
  async createTemplate(template: Omit<Template, 'pk' | 'sk'>): Promise<string> {
    const now = new Date().toISOString()
    const allTemplates = await this.listTemplates(true)
    
    let maxV = 0
    for (const t of allTemplates) {
      if (t.sk.startsWith(TEMPLATE_SK_PREFIX)) {
        const v = parseInt(t.sk.replace(TEMPLATE_SK_PREFIX, ''), 10)
        if (!isNaN(v) && v > maxV) maxV = v
      }
    }

    const newV = maxV + 1
    const newSk = `${TEMPLATE_SK_PREFIX}${newV.toString().padStart(3, '0')}`

    const newTemplate = {
      ...template,
      pk: PK,
      sk: newSk,
      meta: {
        ...template.meta,
        created_at: template.meta.created_at || now,
        updated_at: now,
        archived: template.meta.archived || false,
      }
    }

    // Write template
    await docClient.send(new PutCommand({
      TableName: TABLE,
      Item: newTemplate,
    }))

    // Update index
    const summary: TemplateListEntry = {
      sk: newSk,
      name: newTemplate.meta.name,
      source_filename: newTemplate.meta.source_filename,
      source_file_hash: newTemplate.meta.source_file_hash,
      estimated_weeks: newTemplate.meta.estimated_weeks,
      days_per_week: newTemplate.meta.days_per_week,
      archived: newTemplate.meta.archived,
      created_at: newTemplate.meta.created_at,
      updated_at: now,
    }

    const updatedTemplates = [...allTemplates, summary]
    await docClient.send(new PutCommand({
      TableName: TABLE,
      Item: {
        pk: PK,
        sk: INDEX_SK,
        templates: updatedTemplates,
        updated_at: now,
      }
    }))

    return newSk
  }

  /**
   * Archive a template
   */
  async setArchiveStatus(sk: string, archived: boolean): Promise<void> {
    const template = await this.getTemplate(sk)
    if (!template) throw new Error(`Template not found: ${sk}`)

    const now = new Date().toISOString()
    
    // Update template item
    await docClient.send(new UpdateCommand({
      TableName: TABLE,
      Key: { pk: PK, sk },
      UpdateExpression: 'SET meta.archived = :a, meta.updated_at = :u',
      ExpressionAttributeValues: {
        ':a': archived,
        ':u': now,
      }
    }))

    // Update index
    const allTemplates = await this.listTemplates(true)
    const updatedTemplates = allTemplates.map(t => {
      if (t.sk === sk) {
        return { ...t, archived }
      }
      return t
    })

    await docClient.send(new UpdateCommand({
      TableName: TABLE,
      Key: { pk: PK, sk: INDEX_SK },
      UpdateExpression: 'SET templates = :t, updated_at = :u',
      ExpressionAttributeValues: {
        ':t': updatedTemplates,
        ':u': now,
      }
    }))
  }

  /**
   * Copy a template
   */
  async copyTemplate(sk: string, newName: string): Promise<string> {
    const template = await this.getTemplate(sk)
    if (!template) throw new Error(`Template not found: ${sk}`)

    const newTemplate = {
      ...template,
      meta: {
        ...template.meta,
        name: newName,
        derived_from_template_sk: sk,
        created_at: '', // Will be set in createTemplate
      }
    }

    return this.createTemplate(newTemplate)
  }

  /**
   * Run AI evaluation on a template
   */
  async evaluate(sk: string): Promise<any> {
    const template = await this.getTemplate(sk)
    if (!template) throw new Error('Template not found')

    // Get athlete context (current program, etc.)
    const program = await this.getCurrentProgram()
    const athleteContext = {
      current_program: program,
      // Add other metrics if available
    }

    const evaluation = await AnalysisGateway.evaluateTemplate(template, athleteContext)
    
    // Store evaluation on template meta
    await docClient.send(new UpdateCommand({
      TableName: TABLE,
      Key: { pk: PK, sk },
      UpdateExpression: 'SET meta.ai_evaluation = :e, meta.updated_at = :u',
      ExpressionAttributeValues: {
        ':e': evaluation,
        ':u': new Date().toISOString(),
      }
    }))

    return evaluation
  }

  private async getCurrentProgram(): Promise<Program | null> {
    const pointer = await docClient.send(new GetCommand({
      TableName: TABLE,
      Key: { pk: PK, sk: 'program#current' }
    }))
    if (!pointer.Item) return null
    
    const program = await docClient.send(new GetCommand({
      TableName: TABLE,
      Key: { pk: PK, sk: pointer.Item.ref_sk }
    }))
    return program.Item as Program
  }

  /**
   * Apply template preview (gate check)
   */
  async applyPreview(sk: string, target: string, startDate: string, weekStartDay: string): Promise<any> {
    const template = await this.getTemplate(sk)
    if (!template) throw new Error('Template not found')

    // Check Max Resolution Gate
    const glossary = await this.getGlossary()
    const currentMaxes = await this.getCurrentMaxes()
    
    const requiredIds = template.required_maxes || []
    const missingIds = requiredIds.filter(id => {
      if (['squat', 'bench', 'deadlift'].includes(id)) {
        return !currentMaxes[id]
      }
      const ex = glossary.find((e: any) => e.id === id)
      return !ex?.e1rm_estimate
    })

    if (missingIds.length > 0) {
      return { status: 'gate_blocked', missing_maxes: missingIds }
    }

    return { status: 'ready', preview: 'Template ready to apply' }
  }

  private async getGlossary(): Promise<any[]> {
    const resp = await docClient.send(new GetCommand({
      TableName: TABLE,
      Key: { pk: PK, sk: GLOSSARY_SK }
    }))
    return resp.Item?.exercises || []
  }

  private async getCurrentMaxes(): Promise<Record<string, number>> {
    const resp = await docClient.send(new GetCommand({
      TableName: TABLE,
      Key: { pk: PK, sk: 'maxes#current' }
    }))
    const maxes: Record<string, number> = {}
    if (resp.Item?.entries) {
      for (const entry of resp.Item.entries) {
        maxes[entry.lift] = entry.value
      }
    }
    return maxes
  }
}

export const templateService = new TemplateService()
