import React, { useState } from 'react';
import { CheckCircle2, XCircle, Layers, Eye, BookOpen } from 'lucide-react';
import type { TestCaseResult } from '../types';

interface TestCasesListProps {
  cases: TestCaseResult[];
  onSelectCase: (testCase: TestCaseResult) => void;
}

export const TestCasesList: React.FC<TestCasesListProps> = ({ cases, onSelectCase }) => {
  const [diseaseFilter, setDiseaseFilter] = useState<'all' | 'diabetes' | 'respiratory_viral_infection'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'pass' | 'fail'>('all');

  const filteredCases = cases.filter(c => {
    if (diseaseFilter !== 'all' && c.disease !== diseaseFilter) return false;
    if (statusFilter === 'pass' && !c.metrics.pass) return false;
    if (statusFilter === 'fail' && c.metrics.pass) return false;
    return true;
  });

  return (
    <div className="test-cases-section">
      <div className="section-heading">
        <h2 className="section-title">
          <Layers size={20} color="#3b82f6" />
          Test Cases & Retrieval Results ({filteredCases.length} of {cases.length})
        </h2>

        <div className="filter-bar">
          <div className="filter-group">
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Disease:</span>
            <button
              className={`filter-chip ${diseaseFilter === 'all' ? 'active' : ''}`}
              onClick={() => setDiseaseFilter('all')}
            >
              All (10)
            </button>
            <button
              className={`filter-chip ${diseaseFilter === 'diabetes' ? 'active' : ''}`}
              onClick={() => setDiseaseFilter('diabetes')}
            >
              Diabetes (5)
            </button>
            <button
              className={`filter-chip ${diseaseFilter === 'respiratory_viral_infection' ? 'active' : ''}`}
              onClick={() => setDiseaseFilter('respiratory_viral_infection')}
            >
              Respiratory (5)
            </button>
          </div>

          <div className="filter-group">
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Status:</span>
            <button
              className={`filter-chip ${statusFilter === 'all' ? 'active' : ''}`}
              onClick={() => setStatusFilter('all')}
            >
              All
            </button>
            <button
              className={`filter-chip ${statusFilter === 'pass' ? 'active' : ''}`}
              onClick={() => setStatusFilter('pass')}
            >
              Passed ({cases.filter(c => c.metrics.pass).length})
            </button>
            <button
              className={`filter-chip ${statusFilter === 'fail' ? 'active' : ''}`}
              onClick={() => setStatusFilter('fail')}
            >
              Failed ({cases.filter(c => !c.metrics.pass).length})
            </button>
          </div>
        </div>
      </div>

      <div className="test-cases-container">
        {filteredCases.map(item => {
          const isPass = item.metrics.pass;
          const firstRank = item.metrics.first_relevant_rank;

          return (
            <div
              key={item.test_id}
              className={`test-case-card ${isPass ? 'passed' : 'failed'}`}
              id={`card-${item.test_id}`}
            >
              <div className="case-card-header">
                <div className="case-id-badges">
                  <span className="case-id-badge">{item.test_id}</span>
                  <span className={`disease-tag ${item.disease}`}>
                    {item.disease === 'diabetes' ? 'Diabetes' : 'Respiratory'}
                  </span>
                  {item.verified ? (
                    <span style={{ fontSize: '0.75rem', color: '#34d399', display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <CheckCircle2 size={13} /> Verified
                    </span>
                  ) : (
                    <span style={{ fontSize: '0.75rem', color: '#fbbf24' }}>
                      [DRAFT]
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span className={`pass-fail-badge ${isPass ? 'pass' : 'fail'}`}>
                    {isPass ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                    {isPass ? 'PASS (Hit@5)' : 'FAIL (> Top-5)'}
                  </span>

                  <button
                    className="btn btn-secondary"
                    style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                    onClick={() => onSelectCase(item)}
                    id={`btn-inspect-${item.test_id}`}
                  >
                    <Eye size={14} />
                    Inspect Details
                  </button>
                </div>
              </div>

              <h3 className="case-title">{item.title}</h3>

              <div className="case-question-box">
                <strong style={{ color: '#93c5fd', marginRight: '6px' }}>Question:</strong>
                {item.question}
              </div>

              <div className="case-meta-row">
                <div className="gt-info-pills">
                  <span className="gt-pill">
                    <BookOpen size={13} />
                    Expected Page(s): <strong>{item.expected_pages.join(', ')}</strong>
                  </span>
                  <span className="gt-pill">
                    Ground-Truth Chunks: <strong>{item.relevant_chunk_ids.length}</strong>
                  </span>
                  <span className="gt-pill">
                    First Target Rank: <strong style={{ color: firstRank && firstRank <= 5 ? '#34d399' : '#fbbf24' }}>
                      {firstRank ? `#${firstRank}` : 'Not in top 10'}
                    </strong>
                  </span>
                  <span className="gt-pill">
                    MRR: <strong>{item.metrics.mrr.toFixed(3)}</strong>
                  </span>
                </div>

                <div className="hit-indicators">
                  <span className={`hit-dot ${item.metrics['hit@1'] ? 'hit' : 'miss'}`}>Hit@1</span>
                  <span className={`hit-dot ${item.metrics['hit@3'] ? 'hit' : 'miss'}`}>Hit@3</span>
                  <span className={`hit-dot ${item.metrics['hit@5'] ? 'hit' : 'miss'}`}>Hit@5</span>
                  <span className={`hit-dot ${item.metrics['hit@10'] ? 'hit' : 'miss'}`}>Hit@10</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
