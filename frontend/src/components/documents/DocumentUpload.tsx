import React, { useRef, useState } from 'react';
import { Upload, CheckCircle2, AlertCircle, Loader2, FileUp } from 'lucide-react';
import { uploadDocument } from '../../api/documents';
import type { GuidelineDocument } from '../../types';

interface DocumentUploadProps {
  onDocumentUploaded: (doc: GuidelineDocument) => void;
}

export const DocumentUpload: React.FC<DocumentUploadProps> = ({ onDocumentUploaded }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setMessage(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setMessage({ text: 'Please select a PDF or DOCX guideline document first.', type: 'info' });
      return;
    }

    setIsUploading(true);
    setMessage(null);
    try {
      const response = await uploadDocument(selectedFile);
      onDocumentUploaded(response.document);
      setMessage({ text: response.message, type: 'success' });
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err: any) {
      setMessage({
        text: err.message || 'Failed to upload guideline document.',
        type: 'error',
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="file-upload-section" id="document-upload-container">
      <div className="file-upload-bar">
        <div className="flex items-center gap-2" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <FileUp size={16} className="text-slate-500" />
          <span className="clinical-label" style={{ margin: 0 }}>
            Select Protocol File:
          </span>
        </div>

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".pdf,.docx"
          disabled={isUploading}
          className="file-input-custom"
          id="guideline-file-input"
        />

        <button
          type="button"
          onClick={handleUpload}
          disabled={isUploading || !selectedFile}
          className="clinical-btn-primary"
          style={{ padding: '8px 18px', fontSize: '13px' }}
          id="upload-guideline-btn"
        >
          {isUploading ? (
            <>
              <Loader2 size={14} className="clinical-spinner" />
              <span>Uploading...</span>
            </>
          ) : (
            <>
              <Upload size={14} />
              <span>Upload Guideline</span>
            </>
          )}
        </button>
      </div>

      {message && (
        <div
          className={`status-badge ${
            message.type === 'success' ? 'online' : message.type === 'error' ? 'offline' : 'primary'
          }`}
          style={{ padding: '8px 14px', borderRadius: '6px', width: '100%', marginBottom: '14px', justifyContent: 'flex-start' }}
          id="upload-status-message"
        >
          {message.type === 'success' ? (
            <CheckCircle2 size={15} className="shrink-0" />
          ) : (
            <AlertCircle size={15} className="shrink-0" />
          )}
          <span>{message.text}</span>
        </div>
      )}
    </div>
  );
};
