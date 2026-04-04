// Finance Portal Types
// Based on INFRASTRUCTURE_PLAN.md if-finance table schema

// ============ Profile Types ============

export interface Employment {
  status: 'full_time' | 'part_time' | 'self_employed' | 'unemployed' | 'student' | 'retired';
  role: string;
  company: string;
  tenure_years: number;
  gross_annual_income: number;
  trajectory: string;
  near_term_change_risk: 'low' | 'medium' | 'high';
}

export interface SecondaryIncome {
  source: string;
  monthly_amount: number;
  frequency: 'monthly' | 'quarterly' | 'annual' | 'irregular';
}

export interface Profile {
  age: number;
  employment: Employment;
  net_monthly_income: number;
  secondary_income: SecondaryIncome[];
  tax_bracket_federal: number;
  tax_bracket_provincial: number;
}

// ============ Goal Types ============

export interface Goal {
  id: string;
  title: string;
  description: string;
  target_amount: number;
  current_amount: number;
  deadline: string; // ISO date
  priority: 'critical' | 'high' | 'medium' | 'low';
  category: string;
  notes: string;
}

export interface Goals {
  short_term: Goal[];
  medium_term: Goal[];
  long_term: Goal[];
}

// ============ Risk Profile Types ============

export interface RiskProfile {
  tolerance: 'conservative' | 'moderate' | 'aggressive';
  time_horizon_years: number;
  investment_philosophy: string;
  max_drawdown_comfort_pct: number;
  notes: string;
}

// ============ Net Worth Types ============

export interface NetWorthSnapshot {
  as_of: string; // ISO date
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
}

// ============ Account Types ============

export interface ChequingAccount {
  id: string;
  name: string;
  institution: string;
  balance: number;
  account_number_last4: string;
  is_primary: boolean;
}

export interface SavingsAccount {
  id: string;
  name: string;
  institution: string;
  balance: number;
  interest_rate: number;
  account_number_last4: string;
  purpose: string;
}

export interface CreditCard {
  id: string;
  name: string;
  institution: string;
  balance_owing: number;
  credit_limit: number;
  utilization_pct: number; // Computed server-side
  apr: number;
  annual_fee: number;
  rewards_type: string;
  target_payment: number;
  due_date: number; // Day of month
  account_number_last4: string;
  notes: string;
}

export interface LineOfCredit {
  id: string;
  name: string;
  institution: string;
  balance_owing: number;
  credit_limit: number;
  apr: number;
  type: 'personal' | 'home_equity' | 'business';
  target_payment: number;
  account_number_last4: string;
  notes: string;
}

export interface Loan {
  id: string;
  name: string;
  institution: string;
  original_amount: number;
  current_balance: number;
  interest_rate: number;
  term_months: number;
  remaining_months: number;
  monthly_payment: number;
  type: 'personal' | 'auto' | 'student' | 'other';
  start_date: string;
  account_number_last4: string;
  notes: string;
}

export interface Accounts {
  chequing: ChequingAccount[];
  savings: SavingsAccount[];
  credit_cards: CreditCard[];
  lines_of_credit: LineOfCredit[];
  loans: Loan[];
}

// ============ Investment Types ============

export interface Holding {
  ticker: string;
  shares: number;
  avg_cost: number;
  current_price: number; // Updated manually
  last_price_update: string;
  notes: string;
}

export interface TargetAllocation {
  category: string;
  target_pct: number;
  current_pct: number;
}

export interface InvestmentAccount {
  id: string;
  name: string;
  institution: string;
  type: 'rrsp' | 'tfsa' | 'non_registered' | 'resp' | 'lira';
  holdings: Holding[];
  target_allocation: TargetAllocation[];
  cash_balance: number;
  account_number_last4: string;
  notes: string;
}

export interface WatchlistItem {
  ticker: string;
  name: string;
  target_price: number;
  notes: string;
  added_at: string;
}

// ============ Cashflow Types ============

export interface FixedExpense {
  id: string;
  name: string;
  amount: number;
  frequency: 'monthly' | 'quarterly' | 'annual';
  category: string;
  due_day: number | null;
  auto_pay: boolean;
  notes: string;
}

export interface DebtPayment {
  id: string;
  account_id: string;
  account_name: string;
  amount: number;
  type: 'credit_card' | 'loc' | 'loan';
}

export interface SavingsInvestment {
  id: string;
  name: string;
  amount: number;
  frequency: 'monthly' | 'quarterly';
  type: 'rrsp' | 'tfsa' | 'non_registered' | 'emergency_fund' | 'other';
  auto_transfer: boolean;
}

export interface VariableExpenseBudget {
  id: string;
  category: string;
  budget_amount: number;
  notes: string;
}

export interface MonthlyCashflow {
  as_of: string;
  net_monthly_income: number;
  fixed_expenses: FixedExpense[];
  debt_payments: DebtPayment[];
  savings_and_investments: SavingsInvestment[];
  variable_expense_budget: VariableExpenseBudget[];
  // Computed server-side
  total_fixed: number;
  total_debt_payments: number;
  total_savings_investments: number;
  total_variable_budget: number;
  total_outflow: number;
  monthly_surplus: number;
}

// ============ Insurance Types ============

export interface Insurance {
  id: string;
  type: 'life' | 'disability' | 'critical_illness' | 'health' | 'travel' | 'property' | 'auto';
  provider: string;
  policy_number: string;
  coverage_amount: number;
  monthly_premium: number;
  deductible: number;
  renewal_date: string;
  beneficiaries: string[];
  notes: string;
}

// ============ Tax Types ============

export interface Tax {
  last_year_return_filed: boolean;
  last_refund_or_owing: number;
  ytd_rrsp_contributions: number;
  unused_rrsp_room: number;
  tfsa_room_used_this_year: number;
  tfsa_total_room: number;
  capital_gains_ytd: number;
  notes: string;
}

// ============ Agent Context Types ============

export interface AgentContext {
  known_biases: string[];
  recurring_questions: string[];
  notes: string;
}

// ============ Meta Types ============

export interface Meta {
  currency: string;
  province: string;
  last_reviewed: string;
}

// ============ Version Types ============

export interface VersionPointer {
  version: number;
  ref_sk: string;
  updated_at: string;
}

export interface VersionListItem {
  sk: string;
  version_label: string;
  updated_at: string;
}

// ============ Main Snapshot Type ============

export interface FinanceSnapshot {
  pk: string;
  sk: string;
  version_label: string;
  updated_at: string;
  change_log: string[];

  meta: Meta;
  profile: Profile;
  goals: Goals;
  risk_profile: RiskProfile;
  net_worth_snapshot: NetWorthSnapshot;
  accounts: Accounts;
  investment_accounts: InvestmentAccount[];
  watchlist: WatchlistItem[];
  monthly_cashflow: MonthlyCashflow;
  insurance: Insurance[];
  tax: Tax;
  agent_context: AgentContext;
}

// ============ API Types ============

export interface PatchCreditCardRequest {
  balance_owing?: number;
  credit_limit?: number;
  target_payment?: number;
  apr?: number;
  notes?: string;
}

export interface PatchLOCRequest {
  balance_owing?: number;
  target_payment?: number;
  notes?: string;
}

export interface PatchLoanRequest {
  current_balance?: number;
  notes?: string;
}

export interface PatchHoldingRequest {
  shares?: number;
  avg_cost?: number;
  current_price?: number;
  notes?: string;
}

export interface PutWatchlistRequest {
  watchlist: WatchlistItem[];
}

export interface PatchTargetAllocationRequest {
  allocation: TargetAllocation[];
}

export interface PutCashflowRequest {
  cashflow: MonthlyCashflow;
}

// ============ Helper Functions ============

export function createEmptyFinanceSnapshot(pk: string = 'operator'): FinanceSnapshot {
  const now = new Date().toISOString();
  return {
    pk,
    sk: 'finance#v001',
    version_label: '1.0',
    updated_at: now,
    change_log: ['Initial snapshot created'],

    meta: {
      currency: 'CAD',
      province: 'ON',
      last_reviewed: now,
    },

    profile: {
      age: 0,
      employment: {
        status: 'full_time',
        role: '',
        company: '',
        tenure_years: 0,
        gross_annual_income: 0,
        trajectory: '',
        near_term_change_risk: 'low',
      },
      net_monthly_income: 0,
      secondary_income: [],
      tax_bracket_federal: 0,
      tax_bracket_provincial: 0,
    },

    goals: {
      short_term: [],
      medium_term: [],
      long_term: [],
    },

    risk_profile: {
      tolerance: 'moderate',
      time_horizon_years: 0,
      investment_philosophy: '',
      max_drawdown_comfort_pct: 0,
      notes: '',
    },

    net_worth_snapshot: {
      as_of: now,
      total_assets: 0,
      total_liabilities: 0,
      net_worth: 0,
    },

    accounts: {
      chequing: [],
      savings: [],
      credit_cards: [],
      lines_of_credit: [],
      loans: [],
    },

    investment_accounts: [],
    watchlist: [],

    monthly_cashflow: {
      as_of: now,
      net_monthly_income: 0,
      fixed_expenses: [],
      debt_payments: [],
      savings_and_investments: [],
      variable_expense_budget: [],
      total_fixed: 0,
      total_debt_payments: 0,
      total_savings_investments: 0,
      total_variable_budget: 0,
      total_outflow: 0,
      monthly_surplus: 0,
    },

    insurance: [],

    tax: {
      last_year_return_filed: false,
      last_refund_or_owing: 0,
      ytd_rrsp_contributions: 0,
      unused_rrsp_room: 0,
      tfsa_room_used_this_year: 0,
      tfsa_total_room: 0,
      capital_gains_ytd: 0,
      notes: '',
    },

    agent_context: {
      known_biases: [],
      recurring_questions: [],
      notes: '',
    },
  };
}
