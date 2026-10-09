import React from 'react';
import { Eye, FileText, CheckCircle2, Clock } from 'lucide-react';
import type { GuidelineDocument } from '../../types';
import { resolveDocumentName } from '../../utils/citationResolver';

interface DocumentListProps {
  documents: GuidelineDocument[];
  onViewDocument: (doc: GuidelineDocument) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({ documents, onViewDocument }) => {
  return (
    <div className="clinical-table-wrapper" id="guideline-documents-table-wrapper">
      <table className="clinical-table" id="guideline-documents-table">
        <thead>
          <tr>
            <th style={{ width: '45%' }}>Protocol Document</th>
            <th style={{ width: '25%' }}>Disease Category</th>
            <th style={{ width: '12%', textAlign: 'center' }}>Indexed Chunks</th>
            <th style={{ width: '10%', textAlign: 'center' }}>Status</th>
            <th style={{ width: '8%', textAlign: 'right' }}>Action</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc, idx) => {
            const humanDocName = resolveDocumentName(doc.name || doc.id);

            return (
              <tr key={doc.id || idx}>
                {/* 1. Protocol Document Filename */}
                <td>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                    <FileText size={16} className="text-blue-600" style={{ flexShrink: 0, marginTop: '2px', color: '#0284c7' }} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                      <span className="medicine-name" style={{ wordBreak: 'break-word', lineHeight: 1.4 }}>
                        {humanDocName}
                      </span>
                      {doc.description && (
                        <span style={{ fontSize: '12px', color: '#64748b' }}>
                          {doc.description}
                        </span>
                      )}
                    </div>
                  </div>
                </td>

                {/* 2. Disease Category */}
                <td>
                  <span className="medicine-badge" style={{ background: '#f0f9ff', color: '#0369a1', borderColor: '#bae6fd' }}>
                    {doc.disease_category || doc.diseaseCategory || 'Clinical Protocol'}
                  </span>
                </td>

                {/* 3. Chunks Indexed */}
                <td style={{ textAlign: 'center' }}>
                  <span className="dose-tag">
                    {doc.chunks_indexed ?? doc.chunksIndexed ?? 0}
                  </span>
                </td>

                {/* 4. Status */}
                <td style={{ textAlign: 'center' }}>
                  {doc.status === 'Indexed' ? (
                    <span className="status-badge online" style={{ padding: '3px 8px', fontSize: '11px' }}>
                      <CheckCircle2 size={12} />
                      <span>Indexed</span>
                    </span>
                  ) : (
                    <span className="status-badge" style={{ background: '#fffbeb', color: '#d97706', border: '1px solid #fde68a', padding: '3px 8px', fontSize: '11px' }}>
                      <Clock size={12} />
                      <span>Staged</span>
                    </span>
                  )}
                </td>

                {/* 5. Action */}
                <td style={{ textAlign: 'right' }}>
                  <button
                    type="button"
                    onClick={() => onViewDocument(doc)}
                    className="clinical-btn-secondary"
                    style={{ padding: '5px 10px', fontSize: '12px' }}
                    id={`inspect-doc-btn-${idx}`}
                  >
                    <Eye size={13} />
                    <span>Inspect</span>
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
