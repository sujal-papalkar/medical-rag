import { useState, useEffect } from 'react';
import { getDocuments } from '../api/documents';
import type { GuidelineDocument } from '../types';

const INITIAL_DOCS: GuidelineDocument[] = [
  {
    id: 'DOC-5FFD839CD910',
    name: 'DM RR.docx',
    disease_category: 'Diabetes',
    uploaded_at: 'Indexed',
    chunks_indexed: 50,
    status: 'Indexed',
    description: 'Official Ayurvedic clinical protocol for the management of Diabetes Mellitus (Prameha).'
  },
  {
    id: 'DOC-FC76496810AB',
    name: 'Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).pdf',
    disease_category: 'Respiratory Viral Infection',
    uploaded_at: 'Indexed',
    chunks_indexed: 81,
    status: 'Indexed',
    description: 'National Ayurvedic clinical protocol for the management of Respiratory Viral Infections.'
  }
];

export function useDocuments() {
  const [documents, setDocuments] = useState<GuidelineDocument[]>(INITIAL_DOCS);
  const [isLoading, setIsLoading] = useState(false);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const res = await getDocuments();
      if (res.documents && res.documents.length > 0) {
        setDocuments(res.documents);
      }
    } catch (err: any) {
      // Use fallback initial docs if server error
      console.warn('Could not fetch documents, using initial repository docs:', err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const addDocument = (newDoc: GuidelineDocument) => {
    setDocuments((prev) => [newDoc, ...prev]);
  };

  return { documents, isLoading, addDocument, refreshDocuments: fetchDocuments };
}
