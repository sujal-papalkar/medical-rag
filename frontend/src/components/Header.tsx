import React from 'react';
import { Activity, Play, FileText, CheckCircle2, AlertTriangle } from 'lucide-react';
import type { EvaluationReport } from '../types';

interface HeaderProps {
  report: EvaluationReport | null;
  isRunning: boolean;
  onRunEvaluation: () => void;
  onOpenReport: () => void;
  datasetStatus: string;
}

export const Header: React.FC<HeaderProps> = ({
  report,
  isRunning,
  onRunEvaluation,
  onOpenReport,
  datasetStatus
}) => {
  const isDraft = datasetStatus === 'DRAFT' || report?.metadata?.is_draft;

  return (
    <header className="dashboard-header">
      <div className="brand-section">
        <div className="badge-row">
          <span className="phase-pill">
            <Activity size={13} />
            Phase 1 Evaluation
          </span>
          <span className={`status-pill ${isDraft ? 'draft' : 'verified'}`}>
            {isDraft ? <AlertTriangle size={13} /> : <CheckCircle2 size={13} />}
            {isDraft ? 'Golden Dataset: DRAFT' : 'Golden Dataset: VERIFIED'}
          </span>
          <span className="phase-pill" style={{ background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.08)', color: '#cbd5e1' }}>
            Exact chunk_id matching (No LLM)
          </span>
        </div>
        <h1 className="dashboard-title">Medical RAG Retrieval Evaluation</h1>
        <p className="dashboard-subtitle">
          Benchmarking disease-specific guideline retrieval against verified ground truth across Diabetes Mellitus and Respiratory Viral Infection protocols.
        </p>
      </div>

      <div className="header-actions">
        <button
          className="btn btn-secondary"
          onClick={onOpenReport}
          title="Inspect raw evaluation JSON report"
          id="btn-view-raw-json"
        >
          <FileText size={16} />
          View JSON Report
        </button>

        <button
          className="btn btn-primary"
          onClick={onRunEvaluation}
          disabled={isRunning}
          id="btn-run-evaluation"
        >
          {isRunning ? (
            <>
              <div className="spinner" />
              Evaluating 10 Test Cases...
            </>
          ) : (
            <>
              <Play size={16} fill="white" />
              Run Full Evaluation
            </>
          )}
        </button>
      </div>
    </header>
  );
};
