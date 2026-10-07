import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { DraftBanner } from './components/DraftBanner';
import { MetricCards } from './components/MetricCards';
import { DiseaseComparison } from './components/DiseaseComparison';
import { TestCasesList } from './components/TestCasesList';
import { TestCaseDetailModal } from './components/TestCaseDetailModal';
import { InteractivePlayground } from './components/InteractivePlayground';
import { RawReportModal } from './components/RawReportModal';
import type { EvaluationReport, TestCaseResult, RetrievedChunk, QueryMetrics } from './types';
import { LayoutDashboard, Sparkles, AlertCircle, RefreshCw } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

export function App() {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [datasetStatus, setDatasetStatus] = useState<string>('DRAFT');
  const [selectedCase, setSelectedCase] = useState<TestCaseResult | null>(null);
  const [isReportModalOpen, setIsReportModalOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'playground'>('dashboard');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load latest evaluation results and dataset status on mount
  useEffect(() => {
    fetchLatestReport();
  }, []);

  const fetchLatestReport = async () => {
    try {
      setErrorMessage(null);
      const res = await fetch(`${API_BASE}/api/evaluate/latest`);
      if (!res.ok) {
        throw new Error(`Backend error (${res.status}): ${res.statusText}`);
      }
      const data: EvaluationReport = await res.json();
      setReport(data);
      setDatasetStatus(data.metadata?.status || 'DRAFT');
    } catch (err: any) {
      console.warn('Initial fetch error:', err.message);
      setErrorMessage(
        'Backend server not detected at http://localhost:8000. Start it with: python -m uvicorn evaluation.api:app --reload'
      );
    }
  };

  const handleRunEvaluation = async () => {
    setIsRunning(true);
    setErrorMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/evaluate/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ top_k: 10, pass_k_threshold: 5 })
      });
      if (!res.ok) {
        throw new Error(`Failed to run evaluation: ${res.statusText}`);
      }
      const data: EvaluationReport = await res.json();
      setReport(data);
      setDatasetStatus(data.metadata?.status || 'DRAFT');
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to connect to backend evaluation API');
    } finally {
      setIsRunning(false);
    }
  };

  const handleToggleVerification = async (testId: string, verified: boolean) => {
    try {
      const res = await fetch(`${API_BASE}/api/dataset/verify`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ test_id: testId, verified })
      });
      if (!res.ok) throw new Error('Failed to update verification status');
      const respData = await res.json();

      // Update in state
      if (report) {
        const updatedCases = report.case_results.map(c =>
          c.test_id === testId ? { ...c, verified } : c
        );
        const newStatus = respData.dataset_status || (updatedCases.every(c => c.verified) ? 'VERIFIED' : 'DRAFT');
        setReport({
          ...report,
          metadata: {
            ...report.metadata,
            status: newStatus,
            is_draft: newStatus === 'DRAFT'
          },
          case_results: updatedCases
        });
        setDatasetStatus(newStatus);
        if (selectedCase && selectedCase.test_id === testId) {
          setSelectedCase({ ...selectedCase, verified });
        }
      }
    } catch (err: any) {
      alert(`Error updating verification: ${err.message}`);
    }
  };

  const handleVerifyAll = async () => {
    if (!report) return;
    const cases = report.case_results;
    for (const c of cases) {
      if (!c.verified) {
        await handleToggleVerification(c.test_id, true);
      }
    }
  };

  const handleRunCustomQuery = async (payload: {
    question: string;
    disease?: string;
    top_k: number;
    relevant_chunk_ids: string[];
  }): Promise<{ retrieved_chunks: RetrievedChunk[]; metrics?: QueryMetrics | null } | null> => {
    try {
      const res = await fetch(`${API_BASE}/api/evaluate/custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error('Custom query evaluation failed');
      const data = await res.json();
      return {
        retrieved_chunks: data.retrieved_chunks,
        metrics: data.metrics
      };
    } catch (err: any) {
      alert(`Error running query: ${err.message}`);
      return null;
    }
  };

  return (
    <div className="app-wrapper">
      <Header
        report={report}
        isRunning={isRunning}
        onRunEvaluation={handleRunEvaluation}
        onOpenReport={() => setIsReportModalOpen(true)}
        datasetStatus={datasetStatus}
      />

      {errorMessage && (
        <div className="draft-banner" style={{ borderColor: 'var(--rose-border)', background: 'rgba(239, 68, 68, 0.12)' }}>
          <div className="draft-banner-content">
            <div className="draft-banner-icon" style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171' }}>
              <AlertCircle size={20} />
            </div>
            <div className="draft-banner-text">
              <h4 style={{ color: '#fecaca' }}>Backend Connection Note</h4>
              <p style={{ color: '#fca5a5' }}>{errorMessage}</p>
            </div>
          </div>
          <button
            className="btn btn-secondary"
            onClick={fetchLatestReport}
            style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          >
            <RefreshCw size={14} /> Retry Connection
          </button>
        </div>
      )}

      {report && (
        <DraftBanner
          cases={report.case_results}
          datasetStatus={datasetStatus}
          onVerifyAll={handleVerifyAll}
        />
      )}

      {/* Tabs */}
      <div className="nav-tabs">
        <button
          className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
          id="tab-btn-dashboard"
        >
          <LayoutDashboard size={16} />
          Evaluation Benchmark Dashboard
        </button>
        <button
          className={`tab-btn ${activeTab === 'playground' ? 'active' : ''}`}
          onClick={() => setActiveTab('playground')}
          id="tab-btn-playground"
        >
          <Sparkles size={16} />
          Interactive Query Playground
        </button>
      </div>

      {activeTab === 'dashboard' ? (
        <>
          {/* Summary Metric Cards */}
          <MetricCards summary={report?.summary?.overall || null} />

          {/* Disease Comparison */}
          <DiseaseComparison byDisease={report?.summary?.by_disease || null} />

          {/* All 10 Test Cases */}
          {report && (
            <TestCasesList
              cases={report.case_results}
              onSelectCase={c => setSelectedCase(c)}
            />
          )}
        </>
      ) : (
        <InteractivePlayground onRunCustomQuery={handleRunCustomQuery} />
      )}

      {/* Test Case Detail Modal */}
      {selectedCase && (
        <TestCaseDetailModal
          testCase={selectedCase}
          onClose={() => setSelectedCase(null)}
          onToggleVerification={handleToggleVerification}
        />
      )}

      {/* Raw JSON Report Modal */}
      {isReportModalOpen && (
        <RawReportModal
          report={report}
          onClose={() => setIsReportModalOpen(false)}
        />
      )}
    </div>
  );
}

export default App;
