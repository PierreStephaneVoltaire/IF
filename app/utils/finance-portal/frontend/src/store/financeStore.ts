import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import {
  FinanceSnapshot,
  VersionListItem,
  createEmptyFinanceSnapshot,
  CreditCard,
  LineOfCredit,
  Loan,
  InvestmentAccount,
  Holding,
  MonthlyCashflow,
} from '@finance-portal/types';
import apiClient from '../api/client';

interface VersionInfo {
  sk: string;
  label: string;
  updated_at: string;
}

interface DirtyFields {
  [path: string]: boolean;
}

interface FinanceState {
  // Data
  snapshot: FinanceSnapshot | null;
  version: VersionInfo | null;
  versions: VersionListItem[];

  // UI State
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
  dirtyFields: DirtyFields;
  lastFetched: string | null;

  // Actions - Data fetching
  fetchCurrentSnapshot: () => Promise<void>;
  fetchVersions: () => Promise<void>;
  fetchVersion: (sk: string) => Promise<void>;

  // Actions - Saving
  saveSnapshot: (changeLogEntry?: string) => Promise<void>;

  // Actions - Optimistic updates
  updateCreditCard: (id: string, updates: Partial<CreditCard>) => Promise<void>;
  updateLineOfCredit: (id: string, updates: Partial<LineOfCredit>) => Promise<void>;
  updateLoan: (id: string, updates: Partial<Loan>) => Promise<void>;
  updateInvestmentAccount: (id: string, updates: Partial<InvestmentAccount>) => Promise<void>;
  updateHolding: (accountId: string, ticker: string, updates: Partial<Holding>) => Promise<void>;
  updateCashflow: (updates: Partial<MonthlyCashflow>) => void;

  // Actions - Dirty tracking
  markDirty: (path: string) => void;
  markClean: (path: string) => void;
  isDirty: (path: string) => boolean;
  hasUnsavedChanges: () => boolean;
  clearDirty: () => void;

  // Actions - Utilities
  reset: () => void;
  clearError: () => void;
}

const initialState = {
  snapshot: null,
  version: null,
  versions: [],
  isLoading: false,
  isSaving: false,
  error: null,
  dirtyFields: {},
  lastFetched: null,
};

export const useFinanceStore = create<FinanceState>()(
  devtools(
    (set, get) => ({
      ...initialState,

      // ============ Data Fetching ============

      fetchCurrentSnapshot: async () => {
        set({ isLoading: true, error: null });
        try {
          const response = await apiClient.getCurrentSnapshot();
          set({
            snapshot: response.snapshot,
            version: response.version,
            isLoading: false,
            lastFetched: new Date().toISOString(),
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to fetch snapshot',
            isLoading: false,
          });
        }
      },

      fetchVersions: async () => {
        try {
          const response = await apiClient.listVersions();
          set({ versions: response.versions });
        } catch (error) {
          console.error('Failed to fetch versions:', error);
        }
      },

      fetchVersion: async (sk: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await apiClient.getVersion(sk);
          set({
            snapshot: response.snapshot,
            version: response.version,
            isLoading: false,
          });
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to fetch version',
            isLoading: false,
          });
        }
      },

      // ============ Saving ============

      saveSnapshot: async (changeLogEntry?: string) => {
        const { snapshot } = get();
        if (!snapshot) return;

        set({ isSaving: true, error: null });
        try {
          const response = await apiClient.saveSnapshot(snapshot, changeLogEntry);
          set({
            snapshot: response.snapshot,
            version: response.version,
            isSaving: false,
            dirtyFields: {},
          });
          // Refresh versions list
          get().fetchVersions();
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to save snapshot',
            isSaving: false,
          });
        }
      },

      // ============ Optimistic Updates ============

      updateCreditCard: async (id: string, updates: Partial<CreditCard>) => {
        const { snapshot } = get();
        if (!snapshot) return;

        // Optimistic update
        const cardIndex = snapshot.accounts.credit_cards.findIndex((c) => c.id === id);
        if (cardIndex === -1) return;

        const updatedCards = [...snapshot.accounts.credit_cards];
        const existingCard = updatedCards[cardIndex];
        const updatedCard = { ...existingCard, ...updates };

        // Calculate utilization if balance or limit changed
        if (updates.balance_owing !== undefined || updates.credit_limit !== undefined) {
          updatedCard.utilization_pct = updatedCard.credit_limit > 0
            ? Math.round((updatedCard.balance_owing / updatedCard.credit_limit) * 100 * 100) / 100
            : 0;
        }

        updatedCards[cardIndex] = updatedCard;

        set({
          snapshot: {
            ...snapshot,
            accounts: { ...snapshot.accounts, credit_cards: updatedCards },
          },
        });

        // Server update (PATCH, no new version)
        try {
          await apiClient.patchCreditCard(id, updates);
        } catch (error) {
          // Revert on error
          set({
            snapshot,
            error: error instanceof Error ? error.message : 'Failed to update credit card',
          });
        }
      },

      updateLineOfCredit: async (id: string, updates: Partial<LineOfCredit>) => {
        const { snapshot } = get();
        if (!snapshot) return;

        const locIndex = snapshot.accounts.lines_of_credit.findIndex((l) => l.id === id);
        if (locIndex === -1) return;

        const updatedLOCs = [...snapshot.accounts.lines_of_credit];
        updatedLOCs[locIndex] = { ...updatedLOCs[locIndex], ...updates };

        set({
          snapshot: {
            ...snapshot,
            accounts: { ...snapshot.accounts, lines_of_credit: updatedLOCs },
          },
        });

        try {
          await apiClient.patchLineOfCredit(id, updates);
        } catch (error) {
          set({
            snapshot,
            error: error instanceof Error ? error.message : 'Failed to update line of credit',
          });
        }
      },

      updateLoan: async (id: string, updates: Partial<Loan>) => {
        const { snapshot } = get();
        if (!snapshot) return;

        const loanIndex = snapshot.accounts.loans.findIndex((l) => l.id === id);
        if (loanIndex === -1) return;

        const updatedLoans = [...snapshot.accounts.loans];
        updatedLoans[loanIndex] = { ...updatedLoans[loanIndex], ...updates };

        set({
          snapshot: {
            ...snapshot,
            accounts: { ...snapshot.accounts, loans: updatedLoans },
          },
        });

        try {
          await apiClient.patchLoan(id, updates);
        } catch (error) {
          set({
            snapshot,
            error: error instanceof Error ? error.message : 'Failed to update loan',
          });
        }
      },

      updateInvestmentAccount: async (id: string, updates: Partial<InvestmentAccount>) => {
        const { snapshot } = get();
        if (!snapshot) return;

        const accountIndex = snapshot.investment_accounts.findIndex((a) => a.id === id);
        if (accountIndex === -1) return;

        const updatedAccounts = [...snapshot.investment_accounts];
        updatedAccounts[accountIndex] = { ...updatedAccounts[accountIndex], ...updates };

        set({
          snapshot: {
            ...snapshot,
            investment_accounts: updatedAccounts,
          },
        });

        try {
          await apiClient.patchInvestmentAccount(id, updates);
        } catch (error) {
          set({
            snapshot,
            error: error instanceof Error ? error.message : 'Failed to update investment account',
          });
        }
      },

      updateHolding: async (accountId: string, ticker: string, updates: Partial<Holding>) => {
        const { snapshot } = get();
        if (!snapshot) return;

        const accountIndex = snapshot.investment_accounts.findIndex((a) => a.id === accountId);
        if (accountIndex === -1) return;

        const account = snapshot.investment_accounts[accountIndex];
        const holdingIndex = account.holdings.findIndex((h) => h.ticker === ticker);
        if (holdingIndex === -1) return;

        const updatedHoldings = [...account.holdings];
        updatedHoldings[holdingIndex] = {
          ...updatedHoldings[holdingIndex],
          ...updates,
          last_price_update: updates.current_price !== undefined
            ? new Date().toISOString()
            : updatedHoldings[holdingIndex].last_price_update,
        };

        const updatedAccounts = [...snapshot.investment_accounts];
        updatedAccounts[accountIndex] = {
          ...account,
          holdings: updatedHoldings,
        };

        set({
          snapshot: {
            ...snapshot,
            investment_accounts: updatedAccounts,
          },
        });

        try {
          await apiClient.patchHolding(accountId, ticker, updates);
        } catch (error) {
          set({
            snapshot,
            error: error instanceof Error ? error.message : 'Failed to update holding',
          });
        }
      },

      updateCashflow: (updates: Partial<MonthlyCashflow>) => {
        const { snapshot } = get();
        if (!snapshot) return;

        set({
          snapshot: {
            ...snapshot,
            monthly_cashflow: {
              ...snapshot.monthly_cashflow,
              ...updates,
            },
          },
        });
      },

      // ============ Dirty Tracking ============

      markDirty: (path: string) => {
        set((state) => ({
          dirtyFields: { ...state.dirtyFields, [path]: true },
        }));
      },

      markClean: (path: string) => {
        set((state) => {
          const { [path]: _, ...rest } = state.dirtyFields;
          return { dirtyFields: rest };
        });
      },

      isDirty: (path: string) => {
        return get().dirtyFields[path] === true;
      },

      hasUnsavedChanges: () => {
        return Object.keys(get().dirtyFields).length > 0;
      },

      clearDirty: () => {
        set({ dirtyFields: {} });
      },

      // ============ Utilities ============

      reset: () => {
        set(initialState);
      },

      clearError: () => {
        set({ error: null });
      },
    }),
    { name: 'finance-store' }
  )
);

// Selector hooks for common data
export const useSnapshot = () => useFinanceStore((state) => state.snapshot);
export const useVersion = () => useFinanceStore((state) => state.version);
export const useIsLoading = () => useFinanceStore((state) => state.isLoading);
export const useIsSaving = () => useFinanceStore((state) => state.isSaving);
export const useError = () => useFinanceStore((state) => state.error);

// Computed selectors
export const useNetWorth = () => {
  const snapshot = useSnapshot();
  return snapshot?.net_worth_snapshot?.net_worth ?? 0;
};

export const useMonthlySurplus = () => {
  const snapshot = useSnapshot();
  return snapshot?.monthly_cashflow?.monthly_surplus ?? 0;
};

export const useTotalCreditCardDebt = () => {
  const snapshot = useSnapshot();
  return snapshot?.accounts?.credit_cards?.reduce((sum, card) => sum + card.balance_owing, 0) ?? 0;
};

export const useTotalLOCDebt = () => {
  const snapshot = useSnapshot();
  return snapshot?.accounts?.lines_of_credit?.reduce((sum, loc) => sum + loc.balance_owing, 0) ?? 0;
};

export const useTotalLoanDebt = () => {
  const snapshot = useSnapshot();
  return snapshot?.accounts?.loans?.reduce((sum, loan) => sum + loan.current_balance, 0) ?? 0;
};

export const useTotalDebt = () => {
  return useTotalCreditCardDebt() + useTotalLOCDebt() + useTotalLoanDebt();
};
