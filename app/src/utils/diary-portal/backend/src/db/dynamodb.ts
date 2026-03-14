import { DynamoDBClient } from '@aws-sdk/client-dynamodb'
import { DynamoDBDocumentClient } from '@aws-sdk/lib-dynamodb'
import 'dotenv/config'

const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'ca-central-1',
  credentials:
    process.env.AWS_ACCESS_KEY_ID && process.env.AWS_SECRET_ACCESS_KEY
      ? {
          accessKeyId: process.env.AWS_ACCESS_KEY_ID,
          secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
        }
      : undefined,
})

export const docClient = DynamoDBDocumentClient.from(client)
export const ENTRIES_TABLE =
  process.env.IF_DIARY_ENTRIES_TABLE_NAME || 'if-diary-entries'
export const SIGNALS_TABLE =
  process.env.IF_DIARY_SIGNALS_TABLE_NAME || 'if-diary-signals'
export const OPERATOR_PK = process.env.IF_OPERATOR_PK || 'operator'
