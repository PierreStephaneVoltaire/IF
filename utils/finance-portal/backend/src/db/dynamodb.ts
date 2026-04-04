import {
  DynamoDBClient,
  GetItemCommand,
  PutItemCommand,
  UpdateItemCommand,
  QueryCommand,
  AttributeValue,
} from '@aws-sdk/client-dynamodb';
import { marshall, unmarshall } from '@aws-sdk/util-dynamodb';
import {
  FinanceSnapshot,
  VersionPointer,
  VersionListItem,
  MonthlyCashflow,
  CreditCard,
} from '@finance-portal/types';

// Environment variables
const TABLE_NAME = process.env.IF_FINANCE_TABLE_NAME || 'if-finance';
const OPERATOR_PK = process.env.IF_OPERATOR_PK || 'operator';

// DynamoDB client - uses default credential chain (IAM role, EC2 instance profile, etc.)
const client = new DynamoDBClient({
  region: process.env.AWS_REGION || 'ca-central-1',
});

// SK prefixes
const CURRENT_POINTER_SK = 'finance#current';
const VERSION_SK_PREFIX = 'finance#v';

/**
 * Resolve the current pointer to get the actual versioned item
 */
export async function resolvePointer(pk: string = OPERATOR_PK): Promise<{
  versionedSk: string;
  item: FinanceSnapshot;
} | null> {
  // Get the current pointer
  const pointerResult = await client.send(
    new GetItemCommand({
      TableName: TABLE_NAME,
      Key: marshall({ pk, sk: CURRENT_POINTER_SK }),
    })
  );

  if (!pointerResult.Item) {
    return null;
  }

  const pointer = unmarshall(pointerResult.Item) as VersionPointer;

  // Get the actual versioned item
  const itemResult = await client.send(
    new GetItemCommand({
      TableName: TABLE_NAME,
      Key: marshall({ pk, sk: pointer.ref_sk }),
    })
  );

  if (!itemResult.Item) {
    return null;
  }

  const item = unmarshall(itemResult.Item) as FinanceSnapshot;
  return {
    versionedSk: pointer.ref_sk,
    item,
  };
}

/**
 * Get the current pointer without resolving
 */
export async function getPointer(pk: string = OPERATOR_PK): Promise<VersionPointer | null> {
  const result = await client.send(
    new GetItemCommand({
      TableName: TABLE_NAME,
      Key: marshall({ pk, sk: CURRENT_POINTER_SK }),
    })
  );

  if (!result.Item) {
    return null;
  }

  return unmarshall(result.Item) as VersionPointer;
}

/**
 * Save a new versioned snapshot
 * Creates new vXXX item and updates the pointer
 */
export async function saveVersioned(
  pk: string = OPERATOR_PK,
  item: FinanceSnapshot,
  changeLogEntry?: string
): Promise<string> {
  // Get current pointer to determine next version
  const pointer = await getPointer(pk);
  const nextVersion = pointer ? pointer.version + 1 : 1;
  const newSk = `${VERSION_SK_PREFIX}${String(nextVersion).padStart(3, '0')}`;
  const now = new Date().toISOString();

  // Update the snapshot with new version info
  const newItem: FinanceSnapshot = {
    ...item,
    pk,
    sk: newSk,
    version_label: `${nextVersion}.0`,
    updated_at: now,
    change_log: [
      ...item.change_log,
      changeLogEntry || `Version ${nextVersion} saved`,
    ],
  };

  // Write new versioned item
  await client.send(
    new PutItemCommand({
      TableName: TABLE_NAME,
      Item: marshall(newItem, { removeUndefinedValues: true }),
    })
  );

  // Update the pointer
  const newPointer: VersionPointer = {
    version: nextVersion,
    ref_sk: newSk,
    updated_at: now,
  };

  await client.send(
    new PutItemCommand({
      TableName: TABLE_NAME,
      Item: marshall({ pk, sk: CURRENT_POINTER_SK, ...newPointer }),
    })
  );

  return newSk;
}

/**
 * Patch a nested field in the current versioned item
 * Does NOT create a new version
 */
export async function patchVersionedItem(
  pk: string,
  path: string,
  value: unknown
): Promise<void> {
  const resolved = await resolvePointer(pk);
  if (!resolved) {
    throw new Error('No current version found');
  }

  // Build update expression
  const updateExpression = `SET ${path} = :value, updated_at = :now`;
  const now = new Date().toISOString();

  await client.send(
    new UpdateItemCommand({
      TableName: TABLE_NAME,
      Key: marshall({ pk, sk: resolved.versionedSk }),
      UpdateExpression: updateExpression,
      ExpressionAttributeValues: marshall({
        ':value': value,
        ':now': now,
      }),
    })
  );
}

/**
 * List all versions for version history
 */
export async function listVersions(pk: string = OPERATOR_PK): Promise<VersionListItem[]> {
  const result = await client.send(
    new QueryCommand({
      TableName: TABLE_NAME,
      KeyConditionExpression: 'pk = :pk AND begins_with(sk, :skPrefix)',
      ExpressionAttributeValues: marshall({
        ':pk': pk,
        ':skPrefix': VERSION_SK_PREFIX,
      }),
      ProjectionExpression: 'sk, version_label, updated_at',
      ScanIndexForward: false, // Most recent first
    })
  );

  if (!result.Items) {
    return [];
  }

  return result.Items.map((item) => unmarshall(item) as VersionListItem);
}

/**
 * Get a specific version by sk
 */
export async function getVersion(pk: string, sk: string): Promise<FinanceSnapshot | null> {
  const result = await client.send(
    new GetItemCommand({
      TableName: TABLE_NAME,
      Key: marshall({ pk, sk }),
    })
  );

  if (!result.Item) {
    return null;
  }

  return unmarshall(result.Item) as FinanceSnapshot;
}

/**
 * Calculate utilization for credit cards
 */
export function calculateUtilization(card: CreditCard): number {
  if (card.credit_limit <= 0) return 0;
  return Math.round((card.balance_owing / card.credit_limit) * 100 * 100) / 100;
}

/**
 * Calculate cashflow totals
 */
export function calculateCashflowTotals(cashflow: MonthlyCashflow): Partial<MonthlyCashflow> {
  const totalFixed = cashflow.fixed_expenses.reduce((sum, e) => {
    // Convert to monthly if needed
    const monthly = e.frequency === 'quarterly' ? e.amount / 3 :
                   e.frequency === 'annual' ? e.amount / 12 : e.amount;
    return sum + monthly;
  }, 0);

  const totalDebtPayments = cashflow.debt_payments.reduce((sum, p) => sum + p.amount, 0);

  const totalSavingsInvestments = cashflow.savings_and_investments.reduce((sum, s) => {
    const monthly = s.frequency === 'quarterly' ? s.amount / 3 : s.amount;
    return sum + monthly;
  }, 0);

  const totalVariableBudget = cashflow.variable_expense_budget.reduce((sum, v) => sum + v.budget_amount, 0);

  const totalOutflow = totalFixed + totalDebtPayments + totalSavingsInvestments + totalVariableBudget;
  const monthlySurplus = cashflow.net_monthly_income - totalOutflow;

  return {
    total_fixed: Math.round(totalFixed * 100) / 100,
    total_debt_payments: Math.round(totalDebtPayments * 100) / 100,
    total_savings_investments: Math.round(totalSavingsInvestments * 100) / 100,
    total_variable_budget: Math.round(totalVariableBudget * 100) / 100,
    total_outflow: Math.round(totalOutflow * 100) / 100,
    monthly_surplus: Math.round(monthlySurplus * 100) / 100,
  };
}

/**
 * Create initial snapshot if none exists
 */
export async function initializeSnapshot(pk: string = OPERATOR_PK): Promise<FinanceSnapshot> {
  const { createEmptyFinanceSnapshot } = await import('@finance-portal/types');
  const snapshot = createEmptyFinanceSnapshot(pk);

  const now = new Date().toISOString();
  const initialSk = `${VERSION_SK_PREFIX}001`;

  // Write initial version
  await client.send(
    new PutItemCommand({
      TableName: TABLE_NAME,
      Item: marshall({
        ...snapshot,
        pk,
        sk: initialSk,
        updated_at: now,
      }, { removeUndefinedValues: true }),
    })
  );

  // Write pointer
  await client.send(
    new PutItemCommand({
      TableName: TABLE_NAME,
      Item: marshall({
        pk,
        sk: CURRENT_POINTER_SK,
        version: 1,
        ref_sk: initialSk,
        updated_at: now,
      }),
    })
  );

  return snapshot;
}
