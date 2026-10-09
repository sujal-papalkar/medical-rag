import React from 'react';
import { Pill, FileText, Info, ExternalLink } from 'lucide-react';
import type { MedicineItem, EvidenceSource, GuidelineDocument, ResolvedMedicineCitation } from '../../types';
import { resolveMedicineCitations } from '../../utils/citationResolver';

interface MedicineTableProps {
  medicines: MedicineItem[];
  evidenceSources?: EvidenceSource[];
  knownDocs?: GuidelineDocument[];
  onInspectEvidence?: (medicineName: string, citations: ResolvedMedicineCitation[], citationIndex?: number) => void;
}

export const MedicineTable: React.FC<MedicineTableProps> = ({
  medicines,
  evidenceSources = [],
  knownDocs = [],
  onInspectEvidence,
}) => {
  if (!medicines || medicines.length === 0) {
    return (
      <div
        className="clinical-form-group"
        style={{
          background: '#fffbeb',
          border: '1px solid #fde68a',
          borderRadius: '8px',
          padding: '18px 20px',
          color: '#92400e',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-start',
          gap: '12px',
        }}
        id="empty-medicines-alert"
      >
        <Info size={18} style={{ color: '#d97706', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong style={{ fontSize: '14px', display: 'block', marginBottom: '2px' }}>
            No specific compound formulations prescribed in retrieved guideline context.
          </strong>
          <span style={{ fontSize: '13px', color: '#b45309' }}>
            The retrieved Ayurvedic guidelines for this stage or presentation may recommend lifestyle (Vihar) or diet (Ahar) protocols rather than specific drug formulations.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="clinical-table-wrapper" id="prescription-medicines-table-wrapper">
      <table className="clinical-table" id="prescription-medicines-table">
        <thead>
          <tr>
            <th style={{ width: '22%' }}>Medicine / Formulation</th>
            <th style={{ width: '10%' }}>Dose / Matra</th>
            <th style={{ width: '13%' }}>Frequency</th>
            <th style={{ width: '14%' }}>Timing / Aushadh Kal</th>
            <th style={{ width: '9%' }}>Duration</th>
            <th style={{ width: '12%' }}>Anupana / Sahapaan</th>
            <th style={{ width: '12%' }}>Source Document</th>
            <th style={{ width: '8%', textAlign: 'center' }}>Page</th>
          </tr>
        </thead>
        <tbody>
          {medicines.map((m, medIdx) => {
            const citations = resolveMedicineCitations(m, evidenceSources, knownDocs);
            const hasCitations = citations.length > 0;

            return (
              <tr key={`${m.medicine}-${medIdx}`} id={`medicine-row-${medIdx}`}>
                {/* 1. Medicine / Formulation */}
                <td>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <Pill size={16} style={{ color: '#0284c7', flexShrink: 0, marginTop: '3px' }} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span className="medicine-name" style={{ fontSize: '15px' }}>
                          {m.medicine}
                        </span>
                        {m.dosage_form && (
                          <span className="medicine-badge">
                            {m.dosage_form}
                          </span>
                        )}
                        {m.route && (
                          <span className="medicine-badge" style={{ background: '#f0f9ff', color: '#0284c7', borderColor: '#bae6fd' }}>
                            {m.route}
                          </span>
                        )}
                      </div>
                      {m.special_instructions && (
                        <span style={{ fontSize: '12px', color: '#64748b', fontStyle: 'italic' }}>
                          Instructions: {m.special_instructions}
                        </span>
                      )}
                    </div>
                  </div>
                </td>

                {/* 2. Dose / Matra */}
                <td>
                  {m.dose ? (
                    <span className="dose-tag">
                      {m.dose}
                    </span>
                  ) : (
                    <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '13px' }}>
                      Not specified
                    </span>
                  )}
                </td>

                {/* 3. Frequency */}
                <td>
                  {m.frequency ? (
                    <span style={{ color: '#1e293b', fontWeight: 500 }}>
                      {m.frequency}
                    </span>
                  ) : (
                    <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '13px' }}>
                      Not specified
                    </span>
                  )}
                </td>

                {/* 4. Timing / Aushadh Kal */}
                <td>
                  {m.timing ? (
                    <span style={{ color: '#0f172a', fontWeight: 500 }}>
                      {m.timing}
                    </span>
                  ) : (
                    <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '13px' }}>
                      Not specified
                    </span>
                  )}
                </td>

                {/* 5. Duration */}
                <td>
                  {m.duration ? (
                    <span style={{ color: '#1e293b' }}>
                      {m.duration}
                    </span>
                  ) : (
                    <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '13px' }}>
                      Not specified
                    </span>
                  )}
                </td>

                {/* 6. Anupana / Sahapaan */}
                <td>
                  {m.anupana ? (
                    <span className="anupana-tag">
                      {m.anupana}
                    </span>
                  ) : (
                    <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '13px' }}>
                      Not specified
                    </span>
                  )}
                </td>

                {/* 7. Source Document */}
                <td>
                  {hasCitations ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {citations.map((cit, citIdx) => (
                        <div
                          key={`${cit.chunk_id}-${citIdx}`}
                          className="citation-doc-line"
                          id={`source-doc-line-${medIdx}-${citIdx}`}
                        >
                          <FileText size={14} style={{ color: '#0284c7', flexShrink: 0 }} />
                          <button
                            type="button"
                            onClick={() => onInspectEvidence?.(m.medicine, citations, citIdx)}
                            className="clinical-btn-ghost"
                            style={{
                              padding: 0,
                              textAlign: 'left',
                              fontSize: '13px',
                              fontWeight: 600,
                              color: '#0f172a',
                              cursor: 'pointer',
                              textDecoration: 'none',
                              lineHeight: 1.3,
                            }}
                            title={`Inspect evidence from ${cit.document_name}`}
                            id={`source-doc-btn-${medIdx}-${citIdx}`}
                          >
                            <span style={{ textDecoration: 'underline', textDecorationColor: '#cbd5e1' }}>
                              {cit.document_name}
                            </span>
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '13px' }}>
                      Source not linked
                    </span>
                  )}
                </td>

                {/* 8. Page */}
                <td style={{ textAlign: 'center' }}>
                  {hasCitations ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                      {citations.map((cit, citIdx) => (
                        <div
                          key={`page-${cit.chunk_id}-${citIdx}`}
                          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
                        >
                          <span
                            className={`citation-page-badge ${
                              cit.has_verified_page ? 'verified' : 'unverified'
                            }`}
                            id={`page-badge-${medIdx}-${citIdx}`}
                          >
                            {cit.has_verified_page ? cit.page_display : 'Not available'}
                          </span>

                          <button
                            type="button"
                            onClick={() => onInspectEvidence?.(m.medicine, citations, citIdx)}
                            className="clinical-btn-ghost"
                            style={{ padding: '2px 4px', fontSize: '11px', color: '#0284c7' }}
                            title={`View supporting evidence for ${m.medicine}`}
                            id={`view-source-btn-${medIdx}-${citIdx}`}
                          >
                            <ExternalLink size={12} />
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: '13px' }}>
                      Not available
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
