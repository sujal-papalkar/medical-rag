import React from 'react';
import { AlertTriangle, CheckCircle, ShieldCheck } from 'lucide-react';
import type { TestCaseResult } from '../types';

interface DraftBannerProps {
  cases: TestCaseResult[];
  datasetStatus: string;
  onVerifyAll?: () => void;
}

export const DraftBanner: React.FC<DraftBannerProps> = ({
  cases,
  datasetStatus,
  onVerifyAll
}) => {
  const verifiedCount = cases.filter(c => c.verified).length;
  const totalCount = cases.length;
  const isDraft = datasetStatus === 'DRAFT' || verifiedCount < totalCount;

  return (
    <div className="draft-banner" id="draft-golden-dataset-banner">
      <div className="draft-banner-content">
        <div className="draft-banner-icon">
          {isDraft ? <AlertTriangle size={20} /> : <ShieldCheck size={20} />}
        </div>
        <div className="draft-banner-text">
          <h4>
            {isDraft
              ? 'Notice: Golden Dataset is in DRAFT Mode (Verification Pending)'
              : 'Golden Dataset Fully Verified by Expert Reviewer'}
          </h4>
          <p>
            {isDraft
              ? `Questions are derived from actual chunks in chunks.json. You can manually inspect and verify each question-to-chunk mapping (${verifiedCount}/${totalCount} verified) before using for benchmark sign-off.`
              : `All 10 question-to-chunk mappings have been manually verified against actual guidelines in chunks.json.`}
          </p>
        </div>
      </div>

      {isDraft && onVerifyAll && (
        <button
          className="btn btn-secondary"
          onClick={onVerifyAll}
          style={{ fontSize: '0.8rem', padding: '6px 14px', whiteSpace: 'nowrap' }}
          id="btn-mark-all-verified"
        >
          <CheckCircle size={14} />
          Mark All 10 Verified
        </button>
      )}
    </div>
  );
};
