import { useState, useEffect } from 'react';
import { useFinanceStore } from './store/financeStore';
import {
  Dashboard,
  Accounts,
  Investments,
  Cashflow,
  Goals,
  TaxInsurance,
  VersionHistory,
} from './pages';

type Page = 'dashboard' | 'accounts' | 'investments' | 'cashflow' | 'goals' | 'tax-insurance' | 'versions';

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const fetchCurrentSnapshot = useFinanceStore((state) => state.fetchCurrentSnapshot);
  const saveSnapshot = useFinanceStore((state) => state.saveSnapshot);
  const isSaving = useFinanceStore((state) => state.isSaving);
  const version = useFinanceStore((state) => state.version);

  useEffect(() => {
    fetchCurrentSnapshot();
  }, [fetchCurrentSnapshot]);

  const handleNewVersion = async () => {
    const reason = prompt('Enter a description for this version:');
    if (reason) {
      await saveSnapshot(reason);
    }
  };

  const navItems: { id: Page; label: string; icon: string }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'accounts', label: 'Accounts', icon: '💳' },
    { id: 'investments', label: 'Investments', icon: '📈' },
    { id: 'cashflow', label: 'Cashflow', icon: '💸' },
    { id: 'goals', label: 'Goals', icon: '🎯' },
    { id: 'tax-insurance', label: 'Tax & Insurance', icon: '🧾' },
    { id: 'versions', label: 'History', icon: '🕓' },
  ];

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />;
      case 'accounts':
        return <Accounts />;
      case 'investments':
        return <Investments />;
      case 'cashflow':
        return <Cashflow />;
      case 'goals':
        return <Goals />;
      case 'tax-insurance':
        return <TaxInsurance />;
      case 'versions':
        return <VersionHistory />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-xl font-bold text-gray-800">Finance Portal</h1>
            {version && (
              <p className="text-xs text-gray-500">v{version.label}</p>
            )}
          </div>
          <button
            onClick={handleNewVersion}
            disabled={isSaving}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-sm font-medium"
          >
            {isSaving ? 'Saving...' : 'New Version'}
          </button>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4">
          <ul className="flex space-x-1">
            {navItems.map((item) => (
              <li key={item.id}>
                <button
                  onClick={() => setCurrentPage(item.id)}
                  className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                    currentPage === item.id
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300'
                  }`}
                >
                  <span className="mr-1">{item.icon}</span>
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto">
        {renderPage()}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-8 py-4">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
          Finance Portal • UI layer for if-finance DynamoDB table
        </div>
      </footer>
    </div>
  );
}

export default App;
