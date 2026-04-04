import { useEffect } from 'react';
import { useFinanceStore, useSnapshot } from '../store/financeStore';
import { formatCurrency, formatDate } from '../utils/formatters';

export function TaxInsurance() {
  const fetchCurrentSnapshot = useFinanceStore((state) => state.fetchCurrentSnapshot);
  const isLoading = useFinanceStore((state) => state.isLoading);
  const snapshot = useSnapshot();

  useEffect(() => {
    if (!snapshot) {
      fetchCurrentSnapshot();
    }
  }, [snapshot, fetchCurrentSnapshot]);

  if (isLoading && !snapshot) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">No data available.</p>
      </div>
    );
  }

  const { tax, insurance, profile } = snapshot;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-800">Tax & Insurance</h1>

      {/* Tax Summary */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-700 mb-4">Tax Information</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Tax Bracket Info */}
          <div className="space-y-3">
            <h3 className="font-medium text-gray-600">Tax Brackets</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Federal</span>
                <span className="font-medium">{profile.tax_bracket_federal.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Provincial ({snapshot.meta.province})</span>
                <span className="font-medium">{profile.tax_bracket_provincial.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between border-t pt-2">
                <span className="text-gray-500">Marginal Rate</span>
                <span className="font-bold">
                  {(profile.tax_bracket_federal + profile.tax_bracket_provincial).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* RRSP Room */}
          <div className="space-y-3">
            <h3 className="font-medium text-gray-600">RRSP</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Unused Room</span>
                <span className="font-medium text-blue-600">{formatCurrency(tax.unused_rrsp_room)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">YTD Contributions</span>
                <span className="font-medium">{formatCurrency(tax.ytd_rrsp_contributions)}</span>
              </div>
            </div>
          </div>

          {/* TFSA Room */}
          <div className="space-y-3">
            <h3 className="font-medium text-gray-600">TFSA</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Total Room</span>
                <span className="font-medium text-green-600">{formatCurrency(tax.tfsa_total_room)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Used This Year</span>
                <span className="font-medium">{formatCurrency(tax.tfsa_room_used_this_year)}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Additional Tax Info */}
        <div className="mt-6 pt-6 border-t grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-500">Last Year Return</p>
            <div className="flex items-center gap-2 mt-1">
              {tax.last_year_return_filed ? (
                <span className="text-green-600 font-medium">Filed</span>
              ) : (
                <span className="text-red-600 font-medium">Not Filed</span>
              )}
            </div>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-500">Refund/Owing</p>
            <p className={`text-lg font-bold ${tax.last_refund_or_owing >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(Math.abs(tax.last_refund_or_owing), { showSign: tax.last_refund_or_owing > 0 })}
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-500">Capital Gains YTD</p>
            <p className="text-lg font-bold text-gray-800">{formatCurrency(tax.capital_gains_ytd)}</p>
          </div>
        </div>

        {/* Tax Notes */}
        {tax.notes && (
          <div className="mt-4 p-3 bg-yellow-50 rounded-lg">
            <p className="text-sm text-yellow-800">{tax.notes}</p>
          </div>
        )}
      </div>

      {/* Insurance */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-4 py-3 bg-gray-50 border-b">
          <h2 className="font-semibold text-gray-700">
            Insurance Policies ({insurance.length})
          </h2>
        </div>

        {insurance.length === 0 ? (
          <p className="p-6 text-gray-500 text-center">No insurance policies recorded</p>
        ) : (
          <div className="divide-y">
            {insurance.map((policy) => (
              <div key={policy.id} className="p-4">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="font-medium text-gray-800">{policy.type.replace('_', ' ').toUpperCase()}</h3>
                    <p className="text-sm text-gray-500">{policy.provider}</p>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    new Date(policy.renewal_date) < new Date()
                      ? 'bg-red-100 text-red-800'
                      : 'bg-green-100 text-green-800'
                  }`}>
                    Renews: {formatDate(policy.renewal_date, 'short')}
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500">Coverage</p>
                    <p className="font-medium">{formatCurrency(policy.coverage_amount)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Monthly Premium</p>
                    <p className="font-medium">{formatCurrency(policy.monthly_premium)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Deductible</p>
                    <p className="font-medium">{formatCurrency(policy.deductible)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Policy #</p>
                    <p className="font-medium text-xs">{policy.policy_number}</p>
                  </div>
                </div>

                {policy.beneficiaries.length > 0 && (
                  <div className="mt-3 pt-3 border-t text-sm">
                    <p className="text-gray-500">Beneficiaries:</p>
                    <p className="text-gray-700">{policy.beneficiaries.join(', ')}</p>
                  </div>
                )}

                {policy.notes && (
                  <p className="mt-2 text-sm text-gray-500">{policy.notes}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Coverage Gaps */}
      <div className="bg-blue-50 rounded-lg p-4">
        <h3 className="font-medium text-blue-800 mb-2">Coverage Checklist</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          {['life', 'disability', 'critical_illness', 'health', 'travel', 'property', 'auto'].map((type) => {
            const hasPolicy = insurance.some(p => p.type === type);
            return (
              <div key={type} className="flex items-center gap-2">
                <span className={hasPolicy ? 'text-green-600' : 'text-gray-400'}>
                  {hasPolicy ? '✓' : '○'}
                </span>
                <span className={hasPolicy ? 'text-gray-800' : 'text-gray-500 capitalize'}>
                  {type.replace('_', ' ')}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default TaxInsurance;
