import { DynamoDBClient } from '@aws-sdk/client-dynamodb'
import { DynamoDBDocumentClient, GetCommand, PutCommand, QueryCommand, UpdateCommand } from '@aws-sdk/lib-dynamodb'
import type { Template, TemplateListEntry, ImportPending, ImportType } from '@powerlifting/types'

const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'ca-central-1',
  credentials: process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY
    ? {
        accessKeyId: process.env.AWS_ACCESS_KEY_ID,
        secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
      }
    : undefined,
})

export const docClient = DynamoDBDocumentClient.from(client)
export const TABLE = process.env.DYNAMO_TABLE || 'if-health'
const PK = 'operator'

// --- Template Accessors ---

export async function getTemplate(sk: string): Promise<Template | null> {
  const result = await docClient.send(new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
  }))
  return (result.Item as Template) || null
}

export async function listTemplates(includeArchived: boolean = false): Promise<TemplateListEntry[]> {
  const result = await docClient.send(new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk: 'template#current_list' },
  }))
  if (!result.Item) return []
  
  const templates: TemplateListEntry[] = result.Item.templates || []
  if (!includeArchived) {
    return templates.filter(t => !t.archived)
  }
  return templates
}

export async function putTemplate(template: Template): Promise<string> {
  await docClient.send(new PutCommand({
    TableName: TABLE,
    Item: { ...template, pk: PK },
  }))
  return template.sk
}

export async function archiveTemplate(sk: string): Promise<void> {
  const now = new Date().toISOString()
  await docClient.send(new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    UpdateExpression: 'SET meta.archived = :a, meta.updated_at = :u',
    ExpressionAttributeValues: { ':a': true, ':u': now },
  }))
}

export async function unarchiveTemplate(sk: string): Promise<void> {
  const now = new Date().toISOString()
  await docClient.send(new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk },
    UpdateExpression: 'SET meta.archived = :a, meta.updated_at = :u',
    ExpressionAttributeValues: { ':a': false, ':u': now },
  }))
}

// --- Import Pending Accessors ---

export async function stagePending(record: ImportPending): Promise<string> {
  await docClient.send(new PutCommand({
    TableName: TABLE,
    Item: { ...record, pk: PK },
  }))
  return record.import_id
}

export async function getPending(importId: string): Promise<ImportPending | null> {
  const result = await docClient.send(new GetCommand({
    TableName: TABLE,
    Key: { pk: PK, sk: `import#pending#${importId}` },
  }))
  return (result.Item as ImportPending) || null
}

export async function listPendingImports(): Promise<ImportPending[]> {
  const result = await docClient.send(new QueryCommand({
    TableName: TABLE,
    KeyConditionExpression: 'pk = :pk AND begins_with(sk, :sk)',
    FilterExpression: '#status = :status',
    ExpressionAttributeNames: { '#status': 'status' },
    ExpressionAttributeValues: {
      ':pk': PK,
      ':sk': 'import#pending#',
      ':status': 'awaiting_review',
    },
  }))
  return (result.Items as ImportPending[]) || []
}

export async function markImportApplied(importId: string, at: string): Promise<void> {
  await docClient.send(new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk: `import#pending#${importId}` },
    UpdateExpression: 'SET #status = :s, applied_at = :a',
    ExpressionAttributeNames: { '#status': 'status' },
    ExpressionAttributeValues: { ':s': 'applied', ':a': at },
  }))
}

export async function markImportRejected(importId: string, reason: string | null): Promise<void> {
  const now = new Date().toISOString()
  await docClient.send(new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk: `import#pending#${importId}` },
    UpdateExpression: 'SET #status = :s, rejected_at = :r' + (reason ? ', rejection_reason = :reason' : ''),
    ExpressionAttributeNames: { '#status': 'status' },
    ExpressionAttributeValues: {
      ':s': 'rejected',
      ':r': now,
      ...(reason ? { ':reason': reason } : {}),
    },
  }))
}

export async function existingPendingForType(type: ImportType): Promise<ImportPending | null> {
  const pending = await listPendingImports()
  return pending.find(p => p.import_type === type) || null
}

export async function existingByHash(hash: string, type: ImportType): Promise<ImportPending | null> {
  const result = await docClient.send(new QueryCommand({
    TableName: TABLE,
    KeyConditionExpression: 'pk = :pk AND begins_with(sk, :sk)',
    FilterExpression: 'source_file_hash = :h AND import_type = :t',
    ExpressionAttributeValues: {
      ':pk': PK,
      ':sk': 'import#pending#',
      ':h': hash,
      ':t': type,
    },
  }))
  return (result.Items?.[0] as ImportPending) || null
}

// --- Program Archive Accessors ---

export async function archiveProgram(version: string): Promise<void> {
  const now = new Date().toISOString()
  await docClient.send(new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk: `program#${version}` },
    UpdateExpression: 'SET meta.archived = :a, meta.archived_at = :u',
    ExpressionAttributeValues: { ':a': true, ':u': now },
  }))
}

export async function unarchiveProgram(version: string): Promise<void> {
  await docClient.send(new UpdateCommand({
    TableName: TABLE,
    Key: { pk: PK, sk: `program#${version}` },
    UpdateExpression: 'SET meta.archived = :a, meta.archived_at = :u',
    ExpressionAttributeValues: { ':a': false, ':u': null },
  }))
}
