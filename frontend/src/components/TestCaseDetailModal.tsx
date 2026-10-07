import React, { useState } from 'react';
import { X, CheckCircle2, XCircle, Copy, Check, ShieldCheck, AlertCircle, FileText, Database } from 'lucide-react';
import type { TestCaseResult } from '../types';

interface TestCaseDetailModalProps {
  testCase: TestCaseResult | null;
  onClose: () => void;
  onToggleVerification: (testId: string, verified: boolean) => void;
}

export const TestCaseDetailModal: React.FC<TestCaseDetailModalProps> = ({
  testCase,
  onClose,
  onToggleVerification
}) => {
  const [copiedChunkId, setCopiedChunkId] = useState<string | null>(null);

  if (!testCase) return null;

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedChunkId(id);
    setTimeout(() => setCopiedChunkId(null), 2000);
  };

  const m = testCase.metrics;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="case-id-badge">{testCase.test_id}</span>
            <span className={`disease-tag ${testCase.disease}`}>
              {testCase.disease === 'diabetes' ? 'Diabetes' : 'Respiratory'}
            </span>
            <span className={`pass-fail-badge ${m.pass ? 'pass' : 'fail'}`}>
              {m.pass ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
              {m.pass ? 'PASS (Hit@5)' : 'FAIL'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              className={`btn ${testCase.verified ? 'btn-secondary' : 'btn-outline'}`}
              style={{ fontSize: '0.8rem', padding: '6px 12px' }}
              onClick={() => onToggleVerification(testCase.test_id, !testCase.verified)}
              id="btn-toggle-verify-modal"
            >
              {testCase.verified ? (
                <>
                  <ShieldCheck size={14} color="#10b981" />
                  Verified Ground Truth
                </>
              ) : (
                <>
                  <AlertCircle size={14} color="#f59e0b" />
                  Mark as Verified
                </>
              )}
            </button>

            <button
              className="btn btn-outline"
              style={{ padding: '6px', borderRadius: '50%' }}
              onClick={onClose}
              id="btn-close-modal"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Title and Question */}
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginBottom: '8px' }}>
              {testCase.title}
            </h2>
            <div className="case-question-box">
              <strong style={{ color: '#93c5fd' }}>Clinical Query: </strong>
              {testCase.question}
            </div>
          </div>

          {/* Metrics Overview */}
          <div className="stats-table-horizontal">
            <div className="stat-cell">
              <div className="stat-cell-label">First Relevant Rank</div>
              <div className="stat-cell-val" style={{ color: m.first_relevant_rank && m.first_relevant_rank <= 5 ? '#34d399' : '#fbbf24' }}>
                {m.first_relevant_rank ? `#${m.first_relevant_rank}` : 'None'}
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">MRR</div>
              <div className="stat-cell-val" style={{ color: '#818cf8' }}>
                {m.mrr.toFixed(3)}
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">Recall@5 / Recall@10</div>
              <div className="stat-cell-val">
                {Math.round(m['recall@5'] * 100)}% / {Math.round(m['recall@10'] * 100)}%
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">F1@5 / F1@10</div>
              <div className="stat-cell-val">
                {m['f1@5'].toFixed(3)} / {m['f1@10'].toFixed(3)}
              </div>
            </div>
          </div>

          {/* Ground Truth Status & Comparison Box */}
          <div className="comparison-box">
            <div className="comparison-box-title">
              <Database size={16} color="#38bdf8" />
              Ground Truth Target Chunks ({testCase.relevant_chunk_ids.length})
            </div>

            <div className="gt-chunk-list">
              {testCase.ground_truth_status.map(gt => (
                <div
                  key={gt.chunk_id}
                  className={`gt-chunk-item ${gt.retrieved ? 'retrieved-yes' : 'retrieved-no'}`}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#f8fafc' }}>
                        {gt.chunk_id}
                      </span>
                      {gt.page && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          (Page {gt.page})
                        </span>
                      )}
                    </div>
                    {gt.snippet && (
                      <div style={{ fontSize: '0.775rem', color: '#94a3b8', maxWidth: '600px' }}>
                        {gt.snippet}...
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {gt.retrieved ? (
                      <span className="hit-tag match">
                        <CheckCircle2 size={12} />
                        Retrieved at Rank #{gt.rank} (dist: {gt.distance})
                      </span>
                    ) : (
                      <span className="hit-tag miss">
                        <XCircle size={12} />
                        Not in Top-10
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Retrieved Chunks Full List */}
          <div>
            <div className="comparison-box-title" style={{ marginBottom: '14px' }}>
              <FileText size={16} color="#10b981" />
              Retrieved Chunks in Order of Semantic Proximity (Top {testCase.retrieved_chunks.length})
            </div>

            <div className="retrieved-list">
              {testCase.retrieved_chunks.map(chunk => {
                const isMatch = chunk.is_relevant;

                return (
                  <div
                    key={`${chunk.chunk_id}-${chunk.rank}`}
                    className={`retrieved-card ${isMatch ? 'hit-match' : ''}`}
                  >
                    <div className="retrieved-card-header">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="rank-badge">Rank #{chunk.rank}</span>
                        <span className="distance-badge">
                          Cosine Distance: <strong>{chunk.distance}</strong>
                        </span>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: '#cbd5e1' }}>
                          {chunk.chunk_id}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {isMatch ? (
                          <span className="hit-tag match">
                            <CheckCircle2 size={12} />
                            GROUND TRUTH MATCH
                          </span>
                        ) : (
                          <span className="hit-tag miss">
                            NON-TARGET
                          </span>
                        )}

                        <button
                          className="btn btn-outline"
                          style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                          onClick={() => handleCopy(chunk.content, chunk.chunk_id)}
                          title="Copy chunk content"
                        >
                          {copiedChunkId === chunk.chunk_id ? (
                            <Check size={12} color="#10b981" />
                          ) : (
                            <Copy size={12} />
                          )}
                          Copy
                        </button>
                      </div>
                    </div>

                    <div className="chunk-meta-info">
                      <span>Doc: <strong>{chunk.document_name}</strong></span>
                      <span>Page: <strong>{chunk.page ?? 'N/A'}</strong></span>
                      <span>Content Type: <strong>{chunk.content_type}</strong></span>
                      {chunk.section && (
                        <span>Section: <strong style={{ color: '#94a3b8' }}>{chunk.section.split('\n')[0]}</strong></span>
                      )}
                    </div>

                    <pre className="chunk-content-pre">
                      {chunk.content}
                    </pre>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
