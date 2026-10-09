import { useState, useEffect } from 'react';
import { Header } from './components/common/Header';
import { PrescriptionPage } from './pages/PrescriptionPage';
import { PatientsPage } from './pages/PatientsPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { API_BASE_URL } from './api/client';

export function App() {
  const [backendConnected, setBackendConnected] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'prescription' | 'patients' | 'documents'>('prescription');

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/v1/health`)
      .then((res) => {
        if (res.ok) setBackendConnected(true);
        else setBackendConnected(false);
      })
      .catch(() => {
        setBackendConnected(false);
      });
  }, []);

  return (
    <div className="clinical-app-wrapper min-h-screen bg-slate-50 text-slate-900 pb-12">
      <Header
        backendConnected={backendConnected}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
      />
      {activeTab === 'prescription' && <PrescriptionPage />}
      {activeTab === 'patients' && (
        <PatientsPage onProceedToPrescription={() => setActiveTab('prescription')} />
      )}
      {activeTab === 'documents' && <DocumentsPage />}
    </div>
  );
}

export default App;
