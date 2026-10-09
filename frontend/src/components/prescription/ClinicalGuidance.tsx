import React from 'react';
import { Activity, CheckCircle, FileText, ExternalLink, Bookmark } from 'lucide-react';
import type { ClinicalGuidance as ClinicalGuidanceType, MedicineItem, EvidenceSource, GuidelineDocument, ResolvedMedicineCitation } from '../../types';
import { buildClinicalGuidanceReferences, type ClinicalGuidanceReference } from '../../utils/citationResolver';

interface ClinicalGuidanceProps {
  guidance: ClinicalGuidanceType;
  medicines?: MedicineItem[];
  evidenceSources?: EvidenceSource[];
  knownDocs?: GuidelineDocument[];
  onInspectEvidence?: (medicineName: string, citations: ResolvedMedicineCitation[], citationIndex?: number) => void;
}

export const ClinicalGuidance: React.FC<ClinicalGuidanceProps> = ({
  guidance,
  medicines = [],
  evidenceSources = [],
  knownDocs = [],
  onInspectEvidence,
}) => {
  const references = buildClinicalGuidanceReferences(medicines, evidenceSources, knownDocs);

  // Map each clean medicine name to its reference
  const medicineToRefMap = new Map<string, ClinicalGuidanceReference>();
  for (const ref of references) {
    for (const med of ref.medicines) {
      const clean = med.replace(/^[*•\s]+/, '').trim().toLowerCase();
      if (clean) {
        medicineToRefMap.set(clean, ref);
      }
    }
  }

  // Helper to render text with clean [1] superscript citations when medicines are mentioned
  const renderTextWithCitations = (text: string) => {
    if (!text || medicineToRefMap.size === 0) {
      return <span>{text}</span>;
    }

    // Build regex of medicine names (sorted longest first to avoid substring collision)
    const terms = Array.from(medicineToRefMap.keys()).sort((a, b) => b.length - a.length);
    if (terms.length === 0) return <span>{text}</span>;

    const pattern = new RegExp(`\\b(${terms.map((t) => t.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')).join('|')})\\b`, 'gi');
    const parts = text.split(pattern);

    return (
      <span>
        {parts.map((part, i) => {
          const lower = part.toLowerCase();
          const ref = medicineToRefMap.get(lower);

          if (ref) {
            return (
              <span key={i} className="inline-flex items-baseline">
                <span className="font-semibold text-slate-900">{part}</span>
                <sup className="ml-0.5">
                  <button
                    type="button"
                    onClick={() => onInspectEvidence?.(part, [ref.citation], 0)}
                    className="text-blue-600 hover:text-blue-800 font-bold hover:underline cursor-pointer text-[10px] bg-blue-50 hover:bg-blue-100 px-1 py-0.2 rounded border border-blue-200 transition-colors"
                    title={`${ref.document_name} — Page ${ref.page_display}`}
                  >
                    [{ref.citationNumber}]
                  </button>
                </sup>
              </span>
            );
          }
          return <span key={i}>{part}</span>;
        })}
      </span>
    );
  };

  return (
    <div className="bg-slate-50/90 rounded-lg p-4 border border-slate-200 space-y-3.5" id="clinical-guidance-card">
      {/* Condition & Stage Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-blue-600" />
          <h3 className="text-sm font-bold text-slate-900">
            {guidance.condition}
          </h3>
        </div>
        {guidance.severity_or_stage && (
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 border border-blue-200">
            {guidance.severity_or_stage}
          </span>
        )}
      </div>

      {/* Summary with medicine citations */}
      <div className="text-xs text-slate-700 leading-relaxed font-normal">
        {renderTextWithCitations(guidance.guidance_summary)}
      </div>

      {/* Key Recommendations */}
      {guidance.key_recommendations && guidance.key_recommendations.length > 0 && (
        <div className="pt-2 space-y-1.5 border-t border-slate-200/60">
          <h4 className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
            Key Clinical Recommendations:
          </h4>
          <ul className="space-y-1.5">
            {guidance.key_recommendations.map((rec: string, idx: number) => (
              <li key={idx} className="flex items-start gap-1.5 text-xs text-slate-700">
                <CheckCircle size={13} className="text-emerald-600 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{renderTextWithCitations(rec)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Clean Cited Clinical References List */}
      {references.length > 0 && (
        <div className="pt-3 border-t border-slate-200/80 space-y-1.5" id="guidance-references-list">
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-600">
            <Bookmark size={12} className="text-blue-600" />
            <span>Clinical Guidance Citations</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
            {references.map((ref) => (
              <div
                key={ref.citationNumber}
                className="flex items-center justify-between p-2 rounded bg-white border border-slate-200 text-xs shadow-2xs"
              >
                <div className="flex items-center gap-1.5 truncate mr-2">
                  <span className="font-bold text-blue-700 text-[11px]">
                    [{ref.citationNumber}]
                  </span>
                  <FileText size={12} className="text-slate-500 shrink-0" />
                  <span className="font-medium text-slate-800 truncate" title={ref.document_name}>
                    {ref.document_name}
                  </span>
                  <span className="text-slate-400">•</span>
                  <span className="font-semibold text-slate-600 shrink-0">
                    {ref.has_verified_page ? `Page ${ref.page_display}` : 'Page not available'}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => onInspectEvidence?.(ref.medicines[0], [ref.citation], 0)}
                  className="btn btn-ghost py-0.5 px-1.5 text-blue-600 hover:text-blue-800 text-[11px] font-semibold inline-flex items-center gap-0.5 shrink-0 cursor-pointer"
                  title={`View source for citation [${ref.citationNumber}]`}
                >
                  <ExternalLink size={11} />
                  <span>View</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
