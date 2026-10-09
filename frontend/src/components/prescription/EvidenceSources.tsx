import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, FileText, ExternalLink, Hash } from 'lucide-react';
import type { EvidenceSource, GuidelineDocument, ResolvedMedicineCitation } from '../../types';
import { resolveDocumentName, formatPageCitation } from '../../utils/citationResolver';

interface EvidenceSourcesProps {
  sources: EvidenceSource[];
  knownDocs?: GuidelineDocument[];
  onInspectEvidence?: (name: string, citations: ResolvedMedicineCitation[]) => void;
}

export const EvidenceSources: React.FC<EvidenceSourcesProps> = ({
  sources,
  knownDocs = [],
  onInspectEvidence,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden shadow-2xs" id="evidence-sources-section">
      <button
        type="button"
        id="toggle-evidence-sources-btn"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full py-2.5 px-4 bg-slate-50 hover:bg-slate-100 flex items-center justify-between text-left transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <BookOpen size={15} className="text-blue-600" />
          <span className="text-xs font-bold text-slate-800 uppercase tracking-wide">
            Retrieved Guideline Evidence Sources ({sources.length} Chunks Grounded)
          </span>
        </div>
        <div className="flex items-center gap-1 text-slate-500 text-xs font-medium">
          <span>{isOpen ? 'Collapse' : 'Inspect Evidence'}</span>
          {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </div>
      </button>

      {isOpen && (
        <div className="p-4 space-y-3 divide-y divide-slate-100 bg-white" id="evidence-sources-list">
          {sources.map((s, idx) => {
            const resolvedDocName = resolveDocumentName(s.document_name || s.chunk_id, knownDocs);
            const pageInfo = formatPageCitation(s.page);

            const citationObj: ResolvedMedicineCitation = {
              chunk_id: s.chunk_id,
              document_name: resolvedDocName,
              page: pageInfo.pageNumber,
              page_display: pageInfo.display,
              has_verified_page: pageInfo.isAvailable,
              section: s.section || null,
              content: s.content || null,
              rank: s.rank,
              distance: s.distance,
            };

            return (
              <div key={`${s.chunk_id}-${idx}`} className={idx > 0 ? 'pt-3' : ''}>
                <div className="flex flex-wrap items-center justify-between gap-1 text-[11px] mb-1">
                  <div className="flex items-center gap-1.5 font-bold text-slate-900">
                    <span className="px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 text-[10px] font-bold">
                      Rank #{s.rank || idx + 1}
                    </span>
                    <FileText size={13} className="text-blue-600" />
                    <span>{resolvedDocName}</span>
                  </div>

                  <div className="flex items-center gap-2 text-slate-600 text-[11px]">
                    <span className="font-semibold text-slate-800">
                      {pageInfo.isAvailable ? `Page ${pageInfo.display}` : 'Page not available'}
                    </span>
                    <span>•</span>
                    <button
                      type="button"
                      onClick={() => onInspectEvidence?.(resolvedDocName, [citationObj])}
                      className="btn btn-ghost py-0 px-1 text-blue-600 hover:text-blue-800 font-semibold inline-flex items-center gap-0.5 cursor-pointer text-[11px]"
                      title="Inspect full evidence details"
                    >
                      <ExternalLink size={11} />
                      <span>View details</span>
                    </button>
                  </div>
                </div>

                {s.section && (
                  <p className="text-[11px] font-medium text-blue-900 mb-1">
                    Section: {s.section}
                  </p>
                )}

                {s.content && (
                  <div className="p-2.5 rounded bg-slate-50 border border-slate-100 text-[11px] text-slate-700 leading-relaxed font-sans max-h-32 overflow-y-auto">
                    {s.content}
                  </div>
                )}

                <div className="mt-1.5 flex items-center justify-between text-[10px] text-slate-400">
                  <div className="flex items-center gap-1">
                    <Hash size={11} className="text-slate-400" />
                    <span>Internal Chunk ID (Secondary):</span>
                    <code className="font-mono text-slate-500">{s.chunk_id}</code>
                  </div>
                  {s.distance !== undefined && (
                    <span>Distance: {s.distance}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
