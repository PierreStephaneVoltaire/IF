import {
  FinanceSnapshot,
  VersionListItem,
  PatchCreditCardRequest,
  PatchLOCRequest,
  PatchLoanRequest,
  PatchHoldingRequest,
  PutWatchlistRequest,
  PatchTargetAllocationRequest,
  PutCashflowRequest,
  CreditCard,
  LineOfCredit,
  Loan,
  InvestmentAccount,
  Holding,
  MonthlyCashflow,
} from '@finance-portal/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3002';

interface ApiResponse<T> {
  data?: T;
  error?: {
    message: string;
    code: string;
  };
}

interface FinanceResponse {
  snapshot: FinanceSnapshot;
  version: {
    sk: string;
    label: string;
    updated_at: string;
  };
}

interface VersionsResponse {
  versions: VersionListItem[];
}

interface CashflowResponse {
  cashflow: MonthlyCashflow;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;

    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: { message: 'Unknown error' } }));
      throw new Error(error.error?.message || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // ============ Finance Snapshot ============

  async getCurrentSnapshot(): Promise<FinanceResponse> {
    return this.request<FinanceResponse>('/api/finance/current');
  }

  async saveSnapshot(snapshot: FinanceSnapshot, changeLogEntry?: string): Promise<FinanceResponse> {
    return this.request<FinanceResponse>('/api/finance', {
      method: 'PUT',
      body: JSON.stringify({ ...snapshot, _changeLogEntry: changeLogEntry }),
    });
  }

  async listVersions(): Promise<VersionsResponse> {
    return this.request<VersionsResponse>('/api/finance/versions');
  }

  async getVersion(sk: string): Promise<FinanceResponse> {
    return this.request<FinanceResponse>(`/api/finance/versions/${encodeURIComponent(sk)}`);
  }

  // ============ Accounts ============

  async patchCreditCard(id: string, updates: PatchCreditCardRequest): Promise<{ success: boolean; card: CreditCard }> {
    return this.request<{ success: boolean; card: CreditCard }>(`/api/accounts/credit-cards/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async patchLineOfCredit(id: string, updates: PatchLOCRequest): Promise<{ success: boolean; loc: LineOfCredit }> {
    return this.request<{ success: boolean; loc: LineOfCredit }>(`/api/accounts/loc/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async patchLoan(id: string, updates: PatchLoanRequest): Promise<{ success: boolean; loan: Loan }> {
    return this.request<{ success: boolean; loan: Loan }>(`/api/accounts/loans/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async patchChequing(id: string, updates: Partial<ChequingAccount>): Promise<{ success: boolean; account: ChequingAccount }> {
    return this.request<{ success: boolean; account: ChequingAccount }>(`/api/accounts/chequing/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  async patchSavings(id: string, updates: Partial<SavingsAccount>): Promise<{ success: boolean; account: SavingsAccount }> {
    return this.request<{ success: boolean; account: SavingsAccount }>(`/api/accounts/savings/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  // ============ Investments ============

  async postHolding(accountId: string, holding: Partial<Holding>): Promise<{ success: boolean; holding: Holding }> {
    return this.request<{ success: boolean; holding: Holding }>(`/api/investments/${accountId}/holdings`, {
      method: 'POST',
      body: JSON.stringify(holding),
    });
  }

  async patchHolding(accountId: string, ticker: string, updates: PatchHoldingRequest): Promise<{ success: boolean; holding: Holding }> {
    return this.request<{ success: boolean; holding: Holding }>(
      `/api/investments/${accountId}/holdings/${encodeURIComponent(ticker)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(updates),
      }
    );
  }

  async putWatchlist(accountId: string, watchlist: PutWatchlistRequest['watchlist']): Promise<{ success: boolean; watchlist: PutWatchlistRequest['watchlist'] }> {
    return this.request<{ success: boolean; watchlist: PutWatchlistRequest['watchlist'] }>(
      `/api/investments/${accountId}/watchlist`,
      {
        method: 'PUT',
        body: JSON.stringify({ watchlist }),
      }
    );
  }

  async patchTargetAllocation(accountId: string, allocation: PatchTargetAllocationRequest['allocation']): Promise<{ success: boolean; allocation: PatchTargetAllocationRequest['allocation'] }> {
    return this.request<{ success: boolean; allocation: PatchTargetAllocationRequest['allocation'] }>(
      `/api/investments/${accountId}/target-allocation`,
      {
        method: 'PATCH',
        body: JSON.stringify({ allocation }),
      }
    );
  }

  async patchInvestmentAccount(accountId: string, updates: Partial<InvestmentAccount>): Promise<{ success: boolean; account: InvestmentAccount }> {
    return this.request<{ success: boolean; account: InvestmentAccount }>(`/api/investments/${accountId}`, {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  // ============ Cashflow ============

  async getCashflow(): Promise<CashflowResponse> {
    return this.request<CashflowResponse>('/api/cashflow');
  }

  async putCashflow(cashflow: PutCashflowRequest['cashflow']): Promise<CashflowResponse> {
    return this.request<CashflowResponse>('/api/cashflow', {
      method: 'PUT',
      body: JSON.stringify({ cashflow }),
    });
  }

  async patchIncome(netMonthlyIncome: number): Promise<CashflowResponse> {
    return this.request<CashflowResponse>('/api/cashflow/income', {
      method: 'PATCH',
      body: JSON.stringify({ net_monthly_income: netMonthlyIncome }),
    });
  }

  async patchFixedExpenses(fixedExpenses: MonthlyCashflow['fixed_expenses']): Promise<CashflowResponse> {
    return this.request<CashflowResponse>('/api/cashflow/fixed-expenses', {
      method: 'PATCH',
      body: JSON.stringify({ fixed_expenses: fixedExpenses }),
    });
  }

  async patchDebtPayments(debtPayments: MonthlyCashflow['debt_payments']): Promise<CashflowResponse> {
    return this.request<CashflowResponse>('/api/cashflow/debt-payments', {
      method: 'PATCH',
      body: JSON.stringify({ debt_payments: debtPayments }),
    });
  }

  async patchSavingsInvestments(savingsInvestments: MonthlyCashflow['savings_and_investments']): Promise<CashflowResponse> {
    return this.request<CashflowResponse>('/api/cashflow/savings-investments', {
      method: 'PATCH',
      body: JSON.stringify({ savings_and_investments: savingsInvestments }),
    });
  }

  async patchVariableBudget(variableBudget: MonthlyCashflow['variable_expense_budget']): Promise<CashflowResponse> {
    return this.request<CashflowResponse>('/api/cashflow/variable-budget', {
      method: 'PATCH',
      body: JSON.stringify({ variable_expense_budget: variableBudget }),
    });
  }
}

// Types for chequing/savings that weren't exported
interface ChequingAccount {
  id: string;
  name: string;
  institution: string;
  balance: number;
  account_number_last4: string;
  is_primary: boolean;
}

interface SavingsAccount {
  id: string;
  name: string;
  institution: string;
  balance: number;
  interest_rate: number;
  account_number_last4: string;
  purpose: string;
}

export const apiClient = new ApiClient();
export default apiClient;
