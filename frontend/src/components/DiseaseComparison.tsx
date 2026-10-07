import React from 'react';
import { Activity, Droplet, Wind } from 'lucide-react';
import type { MetricSummary } from '../types';

interface DiseaseComparisonProps {
  byDisease: Record<string, MetricSummary> | null;
}

export const DiseaseComparison: React.FC<DiseaseComparisonProps> = ({ byDisease }) => {
  if (!byDisease) return null;

  const dm = byDisease['diabetes'] || {} as MetricSummary;
  const resp = byDisease['respiratory_viral_infection'] || {} as MetricSummary;

  return (
    <div className="metrics-section">
      <div className="section-heading">
        <h2 className="section-title">
          <Activity size={20} color="#a855f7" />
          Disease-Specific Retrieval Comparison
        </h2>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Diabetes Mellitus vs Respiratory Viral Infection Protocols
        </span>
      </div>

      <div className="comparison-wrapper">
        {/* Diabetes Card */}
        <div className="disease-card diabetes" id="disease-card-diabetes">
          <div className="disease-card-header">
            <div className="disease-title-box">
              <div className="disease-icon-box cyan">
                <Droplet size={20} />
              </div>
              <div>
                <h3>Diabetes Mellitus</h3>
                <p>Document: DM RR.md (79 total chunks)</p>
              </div>
            </div>
            <span className="disease-tag diabetes">
              {dm.passed_count || 0}/{dm.count || 5} Passed
            </span>
          </div>

          <div className="stats-table-horizontal">
            <div className="stat-cell">
              <div className="stat-cell-label">MRR</div>
              <div className="stat-cell-val" style={{ color: '#22d3ee' }}>
                {(dm.mrr || 0).toFixed(3)}
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">Hit@1</div>
              <div className="stat-cell-val">
                {Math.round((dm['hit@1'] || 0) * 100)}%
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">Hit@5</div>
              <div className="stat-cell-val">
                {Math.round((dm['hit@5'] || 0) * 100)}%
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">Recall@5</div>
              <div className="stat-cell-val" style={{ color: '#34d399' }}>
                {Math.round((dm['recall@5'] || 0) * 100)}%
              </div>
            </div>
          </div>

          <div className="k-metrics-row">
            <div className="k-metric-line">
              <span>Hit Rate Progression (@1 → @3 → @5 → @10)</span>
              <span>
                {Math.round((dm['hit@1'] || 0) * 100)}% → {Math.round((dm['hit@3'] || 0) * 100)}% → {Math.round((dm['hit@5'] || 0) * 100)}% → {Math.round((dm['hit@10'] || 0) * 100)}%
              </span>
            </div>
            <div className="k-metric-line">
              <span>Recall Progression (@1 → @3 → @5 → @10)</span>
              <span>
                {Math.round((dm['recall@1'] || 0) * 100)}% → {Math.round((dm['recall@3'] || 0) * 100)}% → {Math.round((dm['recall@5'] || 0) * 100)}% → {Math.round((dm['recall@10'] || 0) * 100)}%
              </span>
            </div>
            <div className="k-metric-line">
              <span>Precision@5 / Precision@10</span>
              <span>
                {((dm['precision@5'] || 0) * 100).toFixed(1)}% / {((dm['precision@10'] || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="k-metric-line">
              <span>F1 Score (F1@5 / F1@10)</span>
              <span>
                {(dm['f1@5'] || 0).toFixed(3)} / {(dm['f1@10'] || 0).toFixed(3)}
              </span>
            </div>
          </div>
        </div>

        {/* Respiratory Card */}
        <div className="disease-card respiratory" id="disease-card-respiratory">
          <div className="disease-card-header">
            <div className="disease-title-box">
              <div className="disease-icon-box purple">
                <Wind size={20} />
              </div>
              <div>
                <h3>Respiratory Viral Infection</h3>
                <p>Document: Respiratory Management (68 chunks)</p>
              </div>
            </div>
            <span className="disease-tag respiratory_viral_infection">
              {resp.passed_count || 0}/{resp.count || 5} Passed
            </span>
          </div>

          <div className="stats-table-horizontal">
            <div className="stat-cell">
              <div className="stat-cell-label">MRR</div>
              <div className="stat-cell-val" style={{ color: '#c084fc' }}>
                {(resp.mrr || 0).toFixed(3)}
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">Hit@1</div>
              <div className="stat-cell-val">
                {Math.round((resp['hit@1'] || 0) * 100)}%
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">Hit@5</div>
              <div className="stat-cell-val">
                {Math.round((resp['hit@5'] || 0) * 100)}%
              </div>
            </div>
            <div className="stat-cell">
              <div className="stat-cell-label">Recall@5</div>
              <div className="stat-cell-val" style={{ color: '#34d399' }}>
                {Math.round((resp['recall@5'] || 0) * 100)}%
              </div>
            </div>
          </div>

          <div className="k-metrics-row">
            <div className="k-metric-line">
              <span>Hit Rate Progression (@1 → @3 → @5 → @10)</span>
              <span>
                {Math.round((resp['hit@1'] || 0) * 100)}% → {Math.round((resp['hit@3'] || 0) * 100)}% → {Math.round((resp['hit@5'] || 0) * 100)}% → {Math.round((resp['hit@10'] || 0) * 100)}%
              </span>
            </div>
            <div className="k-metric-line">
              <span>Recall Progression (@1 → @3 → @5 → @10)</span>
              <span>
                {Math.round((resp['recall@1'] || 0) * 100)}% → {Math.round((resp['recall@3'] || 0) * 100)}% → {Math.round((resp['recall@5'] || 0) * 100)}% → {Math.round((resp['recall@10'] || 0) * 100)}%
              </span>
            </div>
            <div className="k-metric-line">
              <span>Precision@5 / Precision@10</span>
              <span>
                {((resp['precision@5'] || 0) * 100).toFixed(1)}% / {((resp['precision@10'] || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="k-metric-line">
              <span>F1 Score (F1@5 / F1@10)</span>
              <span>
                {(resp['f1@5'] || 0).toFixed(3)} / {(resp['f1@10'] || 0).toFixed(3)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
