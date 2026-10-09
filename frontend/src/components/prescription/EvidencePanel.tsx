import React, { useEffect, useState } from 'react';
import { X, FileText, BookOpen, Layers, CheckCircle2, Hash, AlertCircle } from 'lucide-react';
import type { ResolvedMedicineCitation } from '../../types';

interface EvidencePanelProps {
  isOpen: boolean;
  onClose: () => void;
  medicineName?: string;
  citations: ResolvedMedicineCitation[];
  initialCitationIndex?: number;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({
  isOpen,
  onClose,
  medicineName,
  citations,
  initialCitationIndex = 0,
}) => {
  const [selectedIndex, setSelectedIndex] = useState<number>(initialCitationIndex);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const currentCitation = citations[selectedIndex] || citations[0];

  // Helper to highlight medicine name in retrieved chunk content
  const renderHighlightedContent = (content?: string | null, targetMedicine?: string) => {
    if (!content) {
      return (
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-slate-500 italic text-xs">
          No excerpt text available for this citation.
        </div>
      );
    }

    if (!targetMedicine) {
      return (
        <pre className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 font-sans whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
          {content}
        </pre>
      );
    }

    // Clean target medicine name (e.g. remove leading asterisks like *Kansya Rasayan)
    const cleanTerm = targetMedicine.replace(/^[*•\s]+/, '').trim();
    if (!cleanTerm) {
      return (
        <pre className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 font-sans whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
          {content}
        </pre>
      );
    }

    try {
      const escaped = cleanTerm.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
      const regex = new RegExp(`(${escaped})`, 'gi');
      const parts = content.split(regex);

      return (
        <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 font-sans whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
          {parts.map((part, i) =>
            regex.test(part) ? (
              <mark
                key={i}
                className="bg-amber-100 text-amber-950 font-bold px-1 py-0.5 rounded border border-amber-300 shadow-2xs"
              >
                {part}
              </mark>
            ) : (
              <span key={i}>{part}</span>
            )
          )}
        </div>
      );
    } catch {
      return (
        <pre className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 font-sans whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto">
          {content}
        </pre>
      );
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150"
      id="evidence-details-modal"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-2xl overflow-hidden animate-in zoom-in-95 duration-150 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Panel Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <span className="p-2 rounded-lg bg-blue-100 text-blue-700 shadow-2xs">
              <BookOpen size={18} />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-900 text-sm">
                  Clinical Evidence Details
                </h3>
                {medicineName && (
                  <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-800 border border-blue-200">
                    {medicineName}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-500">
                Authoritative Ayurvedic guideline provenance and supporting excerpt
              </p>
            </div>
          </div>
          <button
            type="button"
            id="close-evidence-panel-btn"
            onClick={onClose}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
            title="Close evidence panel"
          >
            <X size={18} />
          </button>
        </div>

        {/* Multiple Sources Selector (if more than 1 citation) */}
        {citations.length > 1 && (
          <div className="px-4 py-2 bg-slate-100/70 border-b border-slate-200 flex items-center gap-2 overflow-x-auto text-xs">
            <span className="text-[11px] font-semibold text-slate-600 shrink-0">
              Supporting Sources ({citations.length}):
            </span>
            {citations.map((c, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setSelectedIndex(idx)}
                className={`py-1 px-2.5 rounded-md font-medium text-xs whitespace-nowrap transition-all cursor-pointer flex items-center gap-1 ${
                  selectedIndex === idx
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'bg-white text-slate-700 hover:bg-slate-200 border border-slate-200'
                }`}
              >
                <span>Source #{idx + 1}</span>
                <span className="opacity-80 text-[10px]">
                  ({c.has_verified_page ? `p. ${c.page_display}` : 'p. N/A'})
                </span>
              </button>
            ))}
          </div>
        )}

        {/* Panel Content Body */}
        <div className="p-5 space-y-4 overflow-y-auto flex-1 text-xs">
          {currentCitation ? (
            <>
              {/* Document & Page Summary Bar */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 rounded-lg bg-blue-50/50 border border-blue-200/60">
                {/* 1. Document Filename */}
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                    Source Document Filename
                  </label>
                  <div className="flex items-center gap-1.5 font-bold text-slate-900 text-xs break-all">
                    <FileText size={15} className="text-blue-600 shrink-0" />
                    <span>{currentCitation.document_name}</span>
                  </div>
                </div>

                {/* 2. Source Page */}
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                    Verified Source Page
                  </label>
                  {currentCitation.has_verified_page ? (
                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded font-bold text-xs bg-emerald-100 text-emerald-800 border border-emerald-300">
                        Page {currentCitation.page_display}
                      </span>
                      <span className="text-[11px] text-emerald-700 flex items-center gap-0.5">
                        <CheckCircle2 size={12} /> Verified page provenance
                      </span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded font-semibold text-xs bg-amber-100 text-amber-800 border border-amber-300">
                        Page not available
                      </span>
                      <span className="text-[11px] text-amber-700">
                        Page not indexed in metadata
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Guideline Section Heading */}
              {currentCitation.section ? (
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                    Guideline Section / Protocol Heading
                  </label>
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-800 font-semibold text-xs flex items-start gap-1.5">
                    <Layers size={14} className="text-blue-600 shrink-0 mt-0.5" />
                    <span>{currentCitation.section}</span>
                  </div>
                </div>
              ) : null}

              {/* Relevant Supporting Text */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                    Relevant Supporting Guideline Text
                  </label>
                  {medicineName && (
                    <span className="text-[10px] text-slate-500">
                      Highlighted matches for <strong className="text-amber-800">{medicineName}</strong>
                    </span>
                  )}
                </div>
                {renderHighlightedContent(currentCitation.content, medicineName)}
              </div>

              {/* Secondary Debug Metadata */}
              <div className="pt-3 border-t border-slate-100">
                <div className="p-2.5 rounded bg-slate-100/70 border border-slate-200 text-[11px] text-slate-500 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <Hash size={12} className="text-slate-400" />
                    <span>Internal Chunk ID (Secondary / Debug):</span>
                    <code className="font-mono text-slate-700 bg-white px-1.5 py-0.5 rounded border border-slate-200 text-[10px]">
                      {currentCitation.chunk_id}
                    </code>
                  </div>
                  {currentCitation.rank && (
                    <span className="font-medium text-slate-600">
                      Rerank Rank #{currentCitation.rank}
                      {currentCitation.distance !== undefined && (
                        <span> • Distance: {currentCitation.distance}</span>
                      )}
                    </span>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="p-6 text-center text-slate-500 space-y-2">
              <AlertCircle size={24} className="mx-auto text-amber-500" />
              <p className="font-semibold text-slate-700 text-sm">
                No verified evidence source found
              </p>
              <p className="text-xs text-slate-500">
                The selected formulation was not directly mapped to a retrieved chunk in this response.
              </p>
            </div>
          )}
        </div>

        {/* Panel Footer */}
        <div className="p-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <span className="text-[11px] text-slate-500 flex items-center gap-1">
            <CheckCircle2 size={12} className="text-emerald-600" />
            <span>Strictly grounded Ayurvedic guideline repository</span>
          </span>
          <button
            type="button"
            id="evidence-panel-done-btn"
            onClick={onClose}
            className="btn btn-secondary py-1 px-4 text-xs font-semibold cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
