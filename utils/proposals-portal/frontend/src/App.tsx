import { Routes, Route } from 'react-router-dom';
import Board from './pages/Board';
import ProposalDetail from './pages/ProposalDetail';

function App() {
  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <h1 className="text-2xl font-bold text-gray-900">Proposals Portal</h1>
          <p className="text-sm text-gray-500 mt-1">
            Review, approve, and submit system improvement proposals
          </p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        <Routes>
          <Route path="/" element={<Board />} />
          <Route path="/proposal/:sk" element={<ProposalDetail />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
