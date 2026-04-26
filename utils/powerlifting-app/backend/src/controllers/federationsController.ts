import { GetCommand, PutCommand } from '@aws-sdk/lib-dynamodb'
import { docClient, TABLE } from '../db/dynamo'
import type { FederationLibrary } from '@powerlifting/types'

const FEDERATIONS_SK = 'federations#v1'

function emptyLibrary(pk: string): FederationLibrary {
  return {
    pk,
    sk: FEDERATIONS_SK,
    updated_at: new Date().toISOString(),
    federations: [],
    qualification_standards: [],
  }
}

export async function getFederationLibrary(pk: string): Promise<FederationLibrary> {
  const result = await docClient.send(new GetCommand({
    TableName: TABLE,
    Key: { pk, sk: FEDERATIONS_SK },
  }))

  if (!result.Item) {
    return emptyLibrary(pk)
  }

  return result.Item as FederationLibrary
}

export async function updateFederationLibrary(
  pk: string,
  library: Pick<FederationLibrary, 'federations' | 'qualification_standards'>,
): Promise<FederationLibrary> {
  const nextLibrary: FederationLibrary = {
    pk,
    sk: FEDERATIONS_SK,
    updated_at: new Date().toISOString(),
    federations: library.federations ?? [],
    qualification_standards: library.qualification_standards ?? [],
  }

  await docClient.send(new PutCommand({
    TableName: TABLE,
    Item: nextLibrary,
  }))

  return nextLibrary
}
