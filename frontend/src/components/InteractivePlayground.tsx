import React, { useState } from 'react';
import { Search, Sparkles, Database } from 'lucide-react';
import type { RetrievedChunk, QueryMetrics } from '../types';

interface InteractivePlaygroundProps {
  onRunCustomQuery: (payload: {
    question: string;
    disease?: string;
    top_k: number;
    relevant_chunk_ids: string[];
  }) => Promise<{
    retrieved_chunks: RetrievedChunk[];
    metrics?: QueryMetrics | null;
  } | null>;
}

export const InteractivePlayground: React.FC<InteractivePlaygroundProps> = ({
  onRunCustomQuery
}) => {
  const [question, setQuestion] = useState(
    'A patient with diabetes mellitus has Trushna (polydipsia). Retrieve the treatment information including medicine, Matra, and Sahpaan.'
  );
  const [disease, setDisease] = useState<'diabetes' | 'respiratory_viral_infection' | ''>('diabetes');
  const [topK, setTopK] = useState(10);
  const [groundTruthInput, setGroundTruthInput] = useState('DOC-5FFD839CD910-0021-3901824EC224');
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState<RetrievedChunk[] | null>(null);
  const [metrics, setMetrics] = useState<QueryMetrics | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setIsLoading(true);
    try {
      const gtIds = groundTruthInput
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);

      const resp = await onRunCustomQuery({
        question: question.trim(),
        disease: disease || undefined,
        top_k: topK,
        relevant_chunk_ids: gtIds
      });

      if (resp) {
        setResults(resp.retrieved_chunks);
        setMetrics(resp.metrics || null);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="playground-card" id="interactive-playground">
      <div className="section-heading">
        <h2 className="section-title">
          <Sparkles size={20} color="#fbbf24" />
          Interactive Retrieval Query Playground
        </h2>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Test any clinical question with existing disease-specific ChromaDB retrieval
        </span>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">Clinical Question / Query:</label>
          <textarea
            className="form-textarea"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="Enter clinical question or guideline inquiry..."
            rows={3}
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Disease Constraint Filter:</label>
            <select
              className="form-select"
              value={disease}
              onChange={e => setDisease(e.target.value as any)}
            >
              <option value="diabetes">Diabetes Mellitus (diabetes)</option>
              <option value="respiratory_viral_infection">
                Respiratory Viral Infection (respiratory_viral_infection)
              </option>
              <option value="">Unfiltered (Semantic Only)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Top-K Cutoff:</label>
            <select
              className="form-select"
              value={topK}
              onChange={e => setTopK(Number(e.target.value))}
            >
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
              <option value={15}>Top 15</option>
              <option value={20}>Top 20</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">
            Optional Ground Truth Chunk IDs (comma-separated for instant IR calculation):
          </label>
          <input
            type="text"
            className="form-input"
            value={groundTruthInput}
            onChange={e => setGroundTruthInput(e.target.value)}
            placeholder="e.g. DOC-5FFD839CD910-0021-3901824EC224"
          />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '12px' }}>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isLoading || !question.trim()}
            id="btn-run-custom-query"
          >
            {isLoading ? (
              <>
                <div className="spinner" />
                Querying ChromaDB...
              </>
            ) : (
              <>
                <Search size={16} />
                Execute Disease-Specific Retrieval
              </>
            )}
          </button>
        </div>
      </form>

      {/* Metrics Result If Ground Truth Provided */}
      {metrics && (
        <div style={{ marginTop: '24px' }}>
          <h4 style={{ fontSize: '0.9rem', color: '#cbd5e1', marginBottom: '10px' }}>
            Calculated IR Metrics for Custom Query:
          </h4>
          <div className="stats-table-horizontal">
            <div className="stat-cell">
              <div className="stat-cell-label">First Match Rank</div>
              <div className="stat-cell-val" style={{ color: '#34d399' }}>
                {metrics.first_relevant_rank ? `#${metrics.first_relevant_rank}` : 'None'}
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">MRR</div>
              <div className="stat-cell-val">{metrics.mrr.toFixed(3)}</div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">Hit@1 / Hit@5</div>
              <div className="stat-cell-val">
                {metrics['hit@1'] ? '1' : '0'} / {metrics['hit@5'] ? '1' : '0'}
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">Recall@5 / Recall@10</div>
              <div className="stat-cell-val">
                {Math.round(metrics['recall@5'] * 100)}% / {Math.round(metrics['recall@10'] * 100)}%
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Retrieved Chunks Display */}
      {results && results.length > 0 && (
        <div style={{ marginTop: '24px' }}>
          <h4 style={{ fontSize: '0.95rem', color: '#f8fafc', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Database size={16} color="#3b82f6" />
            Retrieved Chunks ({results.length})
          </h4>

          <div className="retrieved-list">
            {results.map(chunk => (
              <div
                key={`${chunk.chunk_id}-${chunk.rank}`}
                className={`retrieved-card ${chunk.is_relevant ? 'hit-match' : ''}`}
              >
                <div className="retrieved-card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="rank-badge">Rank #{chunk.rank}</span>
                    <span className="distance-badge">
                      Distance: <strong>{chunk.distance}</strong>
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: '#cbd5e1' }}>
                      {chunk.chunk_id}
                    </span>
                  </div>

                  {chunk.is_relevant !== undefined && (
                    <span className={`hit-tag ${chunk.is_relevant ? 'match' : 'miss'}`}>
                      {chunk.is_relevant ? 'GROUND TRUTH HIT' : 'NON-TARGET'}
                    </span>
                  )}
                </div>

                <div className="chunk-meta-info">
                  <span>Doc: <strong>{chunk.document_name}</strong></span>
                  <span>Page: <strong>{chunk.page ?? 'N/A'}</strong></span>
                  <span>Type: <strong>{chunk.content_type}</strong></span>
                  <span>Disease: <strong>{chunk.disease}</strong></span>
                </div>

                <pre className="chunk-content-pre">
                  {chunk.content}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
