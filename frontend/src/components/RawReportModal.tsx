import React, { useState } from 'react';
import { X, Download, Copy, Check, FileJson } from 'lucide-react';
import type { EvaluationReport } from '../types';

interface RawReportModalProps {
  report: EvaluationReport | null;
  onClose: () => void;
}

export const RawReportModal: React.FC<RawReportModalProps> = ({ report, onClose }) => {
  const [copied, setCopied] = useState(false);

  if (!report) return null;

  const jsonString = JSON.stringify(report, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `evaluation_report_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <FileJson size={20} color="#60a5fa" />
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc' }}>
              Full Evaluation JSON Report
            </h2>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              className="btn btn-outline"
              onClick={handleCopy}
              style={{ fontSize: '0.8rem', padding: '6px 12px' }}
            >
              {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
              {copied ? 'Copied' : 'Copy JSON'}
            </button>

            <button
              className="btn btn-secondary"
              onClick={handleDownload}
              style={{ fontSize: '0.8rem', padding: '6px 12px' }}
            >
              <Download size={14} />
              Export .json
            </button>

            <button
              className="btn btn-outline"
              style={{ padding: '6px', borderRadius: '50%' }}
              onClick={onClose}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="modal-body">
          <pre
            className="chunk-content-pre"
            style={{
              maxHeight: '65vh',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.8rem',
              color: '#93c5fd',
              background: '#070b14'
            }}
          >
            {jsonString}
          </pre>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
