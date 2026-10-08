import React from 'react';
import { Stethoscope, ShieldCheck, Database, CheckCircle2 } from 'lucide-react';

interface HeaderProps {
  backendConnected?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ backendConnected = true }) => {
  return (
    <header className="clinical-header">
      <div className="clinical-header-brand">
        <div className="clinical-logo-icon">
          <Stethoscope size={28} />
        </div>
        <div>
          <h1 className="clinical-header-title">AI-Powered Ayurvedic Clinical RAG</h1>
          <p className="clinical-header-subtitle">
            Guideline-grounded clinical decision support for registered Ayurvedic physicians
          </p>
        </div>
      </div>

      <div className="clinical-header-status">
        <span className="status-badge info">
          <ShieldCheck size={14} />
          <span>Decision Support System</span>
        </span>
        <span className={`status-badge ${backendConnected ? 'online' : 'staged'}`}>
          {backendConnected ? <CheckCircle2 size={14} /> : <Database size={14} />}
          <span>{backendConnected ? 'Knowledge Base Online (131 Chunks)' : 'Connecting to Knowledge Base...'}</span>
        </span>
      </div>
    </header>
  );
};
