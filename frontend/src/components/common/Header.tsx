import React from 'react';
import { Activity, Wifi, WifiOff } from 'lucide-react';

interface HeaderProps {
  backendConnected: boolean;
  activeTab?: 'prescription' | 'patients' | 'documents';
  onSelectTab?: (tab: 'prescription' | 'patients' | 'documents') => void;
}

export const Header: React.FC<HeaderProps> = ({
  backendConnected,
  activeTab = 'prescription',
  onSelectTab,
}) => {
  return (
    <header className="clinical-header" id="clinical-header">
      <div className="clinical-header-inner">
        {/* Brand & App Title */}
        <div className="clinical-brand">
          <div className="clinical-logo-icon">
            <Activity size={24} />
          </div>
          <div className="clinical-brand-text">
            <div className="clinical-title-row">
              <h1 className="clinical-app-title">
                AyurRAG Clinical Prescription
              </h1>
              <span className="status-badge primary">
                Production
              </span>
            </div>
            <p className="clinical-app-subtitle">
              Grounded Ayurvedic Guideline Decision Support
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        {onSelectTab && (
          <nav className="clinical-nav" aria-label="Clinical Navigation">
            <button
              type="button"
              onClick={() => onSelectTab('prescription')}
              className={`clinical-nav-tab ${activeTab === 'prescription' ? 'active' : ''}`}
              id="nav-tab-prescription"
            >
              Prescription
            </button>
            <button
              type="button"
              onClick={() => onSelectTab('patients')}
              className={`clinical-nav-tab ${activeTab === 'patients' ? 'active' : ''}`}
              id="nav-tab-patients"
            >
              Patients
            </button>
            <button
              type="button"
              onClick={() => onSelectTab('documents')}
              className={`clinical-nav-tab ${activeTab === 'documents' ? 'active' : ''}`}
              id="nav-tab-documents"
            >
              Documents
            </button>
          </nav>
        )}

        {/* Backend Connection Status Badge */}
        <div className="clinical-header-status">
          <div
            className={`status-badge ${backendConnected ? 'online' : 'offline'}`}
            id="backend-connection-badge"
          >
            {backendConnected ? (
              <>
                <Wifi size={14} className="text-emerald-600" />
                <span>Backend Connected</span>
              </>
            ) : (
              <>
                <WifiOff size={14} className="text-red-600" />
                <span>Backend Offline</span>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
