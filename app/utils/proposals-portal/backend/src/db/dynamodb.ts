import {
  DynamoDBClient,
  GetItemCommand,
  PutItemCommand,
  UpdateItemCommand,
  DeleteItemCommand,
  QueryCommand,
  AttributeValue,
} from '@aws-sdk/client-dynamodb';
import {
  DynamoDBDocumentClient,
  marshall,
  unmarshall,
} from '@aws-sdk/lib-dynamodb';

// Uses default credential chain (IAM role, instance profile, etc.)
const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'ca-central-1',
});

export const docClient = DynamoDBDocumentClient.from(client);

export const PROPOSALS_TABLE = process.env.IF_PROPOSALS_TABLE_NAME || 'if-proposals';
export const CORE_TABLE = process.env.IF_CORE_TABLE_NAME || 'if-core';
export const OPERATOR_PK = process.env.IF_OPERATOR_PK || 'operator';

// Proposal operations
export async function getProposalsByStatus(
  pk: string,
  status?: string
): Promise<any[]> {
  const params: any = {
    TableName: PROPOSALS_TABLE,
    KeyConditionExpression: 'pk = :pk',
    ExpressionAttributeValues: marshall({
      ':pk': pk,
    }),
  };

  if (status) {
    params.KeyConditionExpression += ' AND begins_with(sk, :prefix)';
    params.ExpressionAttributeValues[':prefix'] = `proposal#`;
    params.FilterExpression = '#status = :status';
    params.ExpressionAttributeNames = { '#status': 'status' };
    params.ExpressionAttributeValues[':status'] = status;
  } else {
    params.KeyConditionExpression += ' AND begins_with(sk, :prefix)';
    params.ExpressionAttributeValues[':prefix'] = `proposal#`;
  }

  const command = new QueryCommand(params);
  const result = await docClient.send(command);
  return result.Items?.map((item) => unmarshall(item)) || [];
}

export async function getProposal(pk: string, sk: string): Promise<any | null> {
  const command = new GetItemCommand({
    TableName: PROPOSALS_TABLE,
    Key: marshall({ pk, sk }),
  });

  const result = await docClient.send(command);
  return result.Item ? unmarshall(result.Item) : null;
}

export async function createProposal(proposal: any): Promise<any> {
  const command = new PutItemCommand({
    TableName: PROPOSALS_TABLE,
    Item: marshall(proposal),
  });

  await docClient.send(command);
  return proposal;
}

export async function updateProposalStatus(
  pk: string,
  sk: string,
  updates: Record<string, any>
): Promise<any | null> {
  const updateExpressions: string[] = [];
  const expressionAttributeNames: Record<string, string> = {};
  const expressionAttributeValues: Record<string, any> = {};

  Object.entries(updates).forEach(([key, value]) => {
    if (value !== undefined) {
      updateExpressions.push(`#${key} = :${key}`);
      expressionAttributeNames[`#${key}`] = key;
      expressionAttributeValues[`:${key}`] = value;
    }
  });

  if (updateExpressions.length === 0) {
    return getProposal(pk, sk);
  }

  const command = new UpdateItemCommand({
    TableName: PROPOSALS_TABLE,
    Key: marshall({ pk, sk }),
    UpdateExpression: `SET ${updateExpressions.join(', ')}`,
    ExpressionAttributeNames: expressionAttributeNames,
    ExpressionAttributeValues: marshall(expressionAttributeValues),
    ReturnValues: 'ALL_NEW',
  });

  const result = await docClient.send(command);
  return result.Attributes ? unmarshall(result.Attributes) : null;
}

export async function deleteProposal(pk: string, sk: string): Promise<boolean> {
  const command = new DeleteItemCommand({
    TableName: PROPOSALS_TABLE,
    Key: marshall({ pk, sk }),
    ConditionExpression: '#status = :status',
    ExpressionAttributeNames: { '#status': 'status' },
    ExpressionAttributeValues: marshall({ ':status': 'pending' }),
  });

  try {
    await docClient.send(command);
    return true;
  } catch (error: any) {
    if (error.name === 'ConditionalCheckFailedException') {
      return false;
    }
    throw error;
  }
}

// Directive operations (read-only from if-core)
export async function getDirectives(pk: string): Promise<any[]> {
  const command = new QueryCommand({
    TableName: CORE_TABLE,
    KeyConditionExpression: 'pk = :pk AND begins_with(sk, :prefix)',
    ExpressionAttributeValues: marshall({
      ':pk': pk,
      ':prefix': '01#',
    }),
  });

  const result = await docClient.send(command);
  return result.Items?.map((item) => unmarshall(item)) || [];
}

export async function getDirective(pk: string, sk: string): Promise<any | null> {
  const command = new GetItemCommand({
    TableName: CORE_TABLE,
    Key: marshall({ pk, sk }),
  });

  const result = await docClient.send(command);
  return result.Item ? unmarshall(result.Item) : null;
}
