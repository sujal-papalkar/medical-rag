import React, { useState } from 'react';
import { useDocuments } from '../hooks/useDocuments';
import { DocumentUpload } from '../components/documents/DocumentUpload';
import { DocumentList } from '../components/documents/DocumentList';
import { DocumentViewModal } from '../components/documents/DocumentViewModal';
import type { GuidelineDocument } from '../types';

export const DocumentsPage: React.FC = () => {
  const { documents, addDocument } = useDocuments();
  const [viewingDocument, setViewingDocument] = useState<GuidelineDocument | null>(null);

  return (
    <main className="clinical-main-container" id="documents-main-page">
      <div className="flex flex-col gap-1">
        <h1 className="clinical-card-title" style={{ fontSize: '24px' }}>
          <span>📚 Clinical Guideline Documents</span>
        </h1>
        <p className="clinical-card-subtitle">
          Upload and manage official Ayurvedic clinical guidelines for grounded evidence retrieval.
        </p>
      </div>

      {/* Upload and Documents section */}
      <section className="clinical-card" id="guideline-library-section">
        <div className="clinical-card-header">
          <h2 className="clinical-card-title" style={{ fontSize: '18px' }}>
            <span>Knowledge Base Repository</span>
          </h2>
          <span className="status-badge neutral" id="doc-count-badge">
            {documents.length} DOCUMENTS
          </span>
        </div>

        <DocumentUpload onDocumentUploaded={addDocument} />
        <DocumentList documents={documents} onViewDocument={setViewingDocument} />
      </section>

      {/* Document View Modal */}
      <DocumentViewModal
        document={viewingDocument}
        onClose={() => setViewingDocument(null)}
      />
    </main>
  );
};

export default DocumentsPage;
