import React, { useRef, useState } from 'react';
import { Upload, Eye, CheckCircle2, AlertCircle } from 'lucide-react';
import type { GuidelineDocument } from '../types';

interface GuidelineLibraryCardProps {
  documents: GuidelineDocument[];
  onUploadDocument: (file: File) => void;
  onViewDocument: (doc: GuidelineDocument) => void;
}

export const GuidelineLibraryCard: React.FC<GuidelineLibraryCardProps> = ({
  documents,
  onUploadDocument,
  onViewDocument,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadMessage, setUploadMessage] = useState<{ text: string; type: 'success' | 'info' | 'error' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setUploadMessage(null);
    }
  };

  const handleUploadClick = () => {
    if (!selectedFile) {
      setUploadMessage({
        text: 'Please select a guideline file first before clicking upload.',
        type: 'info',
      });
      return;
    }

    onUploadDocument(selectedFile);
    setUploadMessage({
      text: `Document "${selectedFile.name}" added to guideline library. (Backend ingestion endpoint POST /api/documents/upload is pending integration in backend/evaluation/api.py)`,
      type: 'success',
    });
    setSelectedFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="card" id="guideline-library-card">
      {/* Card Header */}
      <div className="card-header flex items-center justify-between pb-3 border-b border-slate-200">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <span>📚 1. Guideline Library</span>
        </h2>
        <span className="badge badge-neutral font-semibold text-xs tracking-wide uppercase px-2.5 py-1">
          {documents.length} DOCUMENTS
        </span>
      </div>

      {/* Upload Area */}
      <div className="pt-4 pb-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
          <label className="text-xs font-bold text-slate-700 uppercase tracking-wider shrink-0">
            GUIDELINE FILE:
          </label>
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              className="text-xs text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border file:border-slate-300 file:text-xs file:font-semibold file:bg-slate-50 file:text-slate-700 hover:file:bg-slate-100 cursor-pointer"
            />
            <button
              type="button"
              onClick={handleUploadClick}
              className="btn btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5 font-medium shrink-0"
            >
              <Upload size={13} />
              <span>Upload Guideline</span>
            </button>
          </div>
        </div>

        {/* Upload feedback note if triggered */}
        {uploadMessage && (
          <div
            className={`mt-3 text-xs p-2.5 rounded-lg border flex items-center gap-2 ${
              uploadMessage.type === 'success'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : uploadMessage.type === 'error'
                ? 'bg-red-50 border-red-200 text-red-800'
                : 'bg-blue-50 border-blue-200 text-blue-800'
            }`}
          >
            {uploadMessage.type === 'success' ? (
              <CheckCircle2 size={14} className="shrink-0 text-emerald-600" />
            ) : (
              <AlertCircle size={14} className="shrink-0 text-blue-600" />
            )}
            <span>{uploadMessage.text}</span>
          </div>
        )}
      </div>

      {/* Guideline Documents Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200 mt-2">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
              <th className="py-2.5 px-3">DOCUMENT NAME</th>
              <th className="py-2.5 px-3">DISEASE CATEGORY</th>
              <th className="py-2.5 px-3">UPLOADED AT</th>
              <th className="py-2.5 px-3 text-center">CHUNKS INDEXED</th>
              <th className="py-2.5 px-3 text-center">STATUS</th>
              <th className="py-2.5 px-3 text-center">ACTIONS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {documents.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500 italic">
                  No guideline documents uploaded yet. Upload a guideline document above.
                </td>
              </tr>
            ) : (
              documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                  <td className="py-2.5 px-3 font-medium text-slate-900 max-w-xs truncate" title={doc.name}>
                    {doc.name}
                  </td>
                  <td className="py-2.5 px-3 text-slate-700">
                    <span className="inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700">
                      {doc.diseaseCategory}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-500 whitespace-nowrap">
                    {doc.uploadedAt}
                  </td>
                  <td className="py-2.5 px-3 text-center font-mono font-semibold text-slate-800">
                    {doc.chunksIndexed}
                  </td>
                  <td className="py-2.5 px-3 text-center whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                        doc.status === 'Indexed'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {doc.status}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <button
                      type="button"
                      onClick={() => onViewDocument(doc)}
                      className="btn btn-secondary py-1 px-2.5 text-[11px] font-medium inline-flex items-center gap-1 hover:border-blue-400 hover:text-blue-700"
                    >
                      <Eye size={12} />
                      View
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
