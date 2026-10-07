import React from 'react';
import { Target, Award, BarChart3, CheckCircle2, Crosshair, Zap } from 'lucide-react';
import type { MetricSummary } from '../types';

interface MetricCardsProps {
  summary: MetricSummary | null;
}

export const MetricCards: React.FC<MetricCardsProps> = ({ summary }) => {
  if (!summary) return null;

  const hit5Percent = Math.round((summary['hit@5'] || 0) * 100);
  const rec5Percent = Math.round((summary['recall@5'] || 0) * 100);
  const rec10Percent = Math.round((summary['recall@10'] || 0) * 100);
  const mrrScore = (summary.mrr || 0).toFixed(3);
  const passRate = Math.round((summary.pass_rate || 0) * 100);

  return (
    <div className="metrics-section">
      <div className="section-heading">
        <h2 className="section-title">
          <BarChart3 size={20} color="#60a5fa" />
          Overall Retrieval Benchmark Metrics (N={summary.count || 10})
        </h2>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Exact chunk ID matching against ground truth
        </span>
      </div>

      <div className="metrics-grid">
        {/* Pass Rate Card */}
        <div className="metric-card" id="card-pass-rate">
          <div className="metric-card-top">
            <span className="metric-label">Pass Rate (Hit@5)</span>
            <div className="metric-icon-wrap" style={{ color: '#10b981' }}>
              <CheckCircle2 size={18} />
            </div>
          </div>
          <div className="metric-value" style={{ color: passRate >= 80 ? '#34d399' : '#fbbf24' }}>
            {passRate}%
          </div>
          <div className="metric-subtitle">
            {summary.passed_count} of {summary.count} test cases passed
          </div>
          <div className="metric-progress-bg">
            <div
              className="metric-progress-bar bar-emerald"
              style={{ width: `${passRate}%` }}
            />
          </div>
        </div>

        {/* MRR Card */}
        <div className="metric-card" id="card-mrr">
          <div className="metric-card-top">
            <span className="metric-label">Mean Reciprocal Rank</span>
            <div className="metric-icon-wrap" style={{ color: '#6366f1' }}>
              <Zap size={18} />
            </div>
          </div>
          <div className="metric-value" style={{ color: '#818cf8' }}>
            {mrrScore}
          </div>
          <div className="metric-subtitle">
            Target chunks retrieved on average in top positions
          </div>
          <div className="metric-progress-bg">
            <div
              className="metric-progress-bar bar-indigo"
              style={{ width: `${Math.min(100, Math.round(summary.mrr * 100))}%` }}
            />
          </div>
        </div>

        {/* Hit Rate Card */}
        <div className="metric-card" id="card-hit-rate">
          <div className="metric-card-top">
            <span className="metric-label">Hit@5 / Hit@10</span>
            <div className="metric-icon-wrap" style={{ color: '#38bdf8' }}>
              <Target size={18} />
            </div>
          </div>
          <div className="metric-value">
            {hit5Percent}% <span style={{ fontSize: '1.1rem', color: 'var(--text-secondary)' }}>/ {Math.round((summary['hit@10'] || 0) * 100)}%</span>
          </div>
          <div className="metric-subtitle">
            Hit@1: {Math.round((summary['hit@1'] || 0) * 100)}% | Hit@3: {Math.round((summary['hit@3'] || 0) * 100)}%
          </div>
          <div className="metric-progress-bg">
            <div
              className="metric-progress-bar bar-blue"
              style={{ width: `${hit5Percent}%` }}
            />
          </div>
        </div>

        {/* Recall Card */}
        <div className="metric-card" id="card-recall">
          <div className="metric-card-top">
            <span className="metric-label">Recall@5 / Recall@10</span>
            <div className="metric-icon-wrap" style={{ color: '#c084fc' }}>
              <Crosshair size={18} />
            </div>
          </div>
          <div className="metric-value" style={{ color: '#c084fc' }}>
            {rec5Percent}% <span style={{ fontSize: '1.1rem', color: 'var(--text-secondary)' }}>/ {rec10Percent}%</span>
          </div>
          <div className="metric-subtitle">
            Rec@1: {Math.round((summary['recall@1'] || 0) * 100)}% | Rec@3: {Math.round((summary['recall@3'] || 0) * 100)}%
          </div>
          <div className="metric-progress-bg">
            <div
              className="metric-progress-bar bar-purple"
              style={{ width: `${rec5Percent}%` }}
            />
          </div>
        </div>

        {/* F1 Scores Card */}
        <div className="metric-card" id="card-f1">
          <div className="metric-card-top">
            <span className="metric-label">F1@5 & F1@10</span>
            <div className="metric-icon-wrap" style={{ color: '#fbbf24' }}>
              <Award size={18} />
            </div>
          </div>
          <div className="metric-value" style={{ color: '#fbbf24' }}>
            {(summary['f1@5'] || 0).toFixed(3)}
          </div>
          <div className="metric-subtitle">
            F1@10: {(summary['f1@10'] || 0).toFixed(3)} | Prec@5: {Math.round((summary['precision@5'] || 0) * 100)}%
          </div>
          <div className="metric-progress-bg">
            <div
              className="metric-progress-bar bar-amber"
              style={{ width: `${Math.min(100, Math.round((summary['f1@5'] || 0) * 200))}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
