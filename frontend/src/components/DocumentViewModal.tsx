import { X, FileText, CheckCircle2, Layers } from 'lucide-react';
import type { GuidelineDocument } from '../types';

interface DocumentViewModalProps {
  document: GuidelineDocument | null;
  onClose: () => void;
}

export const DocumentViewModal: React.FC<DocumentViewModalProps> = ({
  document,
  onClose,
}) => {
  if (!document) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200 bg-slate-50/60">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-blue-100 text-blue-700">
              <FileText size={18} />
            </span>
            <h3 className="font-bold text-slate-900 text-sm">Guideline Document Details</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 space-y-4 text-xs">
          <div>
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Document Name
            </label>
            <p className="font-semibold text-slate-900 text-sm break-all">{document.name}</p>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100">
            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                Disease Category
              </label>
              <span className="inline-block px-2 py-0.5 rounded font-medium bg-blue-50 text-blue-700">
                {document.diseaseCategory}
              </span>
            </div>
            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                Status
              </label>
              <span className="inline-flex items-center gap-1 font-semibold text-emerald-700">
                <CheckCircle2 size={13} />
                {document.status} in Vectorstore
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-100">
            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                Chunks Indexed
              </label>
              <span className="font-mono text-slate-800 font-bold text-sm flex items-center gap-1.5">
                <Layers size={14} className="text-slate-500" />
                {document.chunksIndexed} chunks
              </span>
            </div>
            <div>
              <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                Uploaded At
              </label>
              <span className="text-slate-600 font-medium">{document.uploadedAt}</span>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-100">
            <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Knowledge Base Embedding
            </label>
            <p className="text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-200 leading-relaxed">
              This clinical guideline is vectorized in ChromaDB collection <code className="font-mono text-blue-700">medical_guidelines</code> using Gemini embedding model <code className="font-mono text-blue-700">text-embedding-004</code> for semantic & lexical retrieval.
            </p>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-3 bg-slate-50 border-t border-slate-200 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary py-1.5 px-4 text-xs font-semibold"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
