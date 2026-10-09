import type { EvidenceSource, GuidelineDocument, MedicineItem, ResolvedMedicineCitation } from '../types';

/**
 * Registry mapping known internal document IDs and converted markdown names
 * to authoritative original upload filenames.
 */
export const DOCUMENT_ORIGINAL_NAMES: Record<string, string> = {
  'DOC-5FFD839CD910': 'DM RR.docx',
  'DM RR.md': 'DM RR.docx',
  'DM RR.docx': 'DM RR.docx',
  'DOC-FC76496810AB': 'Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).pdf',
  'Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).md':
    'Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).pdf',
  'Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).pdf':
    'Respiratory Viral Infection Management prorocol_FINAL version-converted-1-25 (1).pdf',
};

/**
 * Resolves an internal document ID, chunk ID, or converted markdown name
 * to a clean, human-readable document filename.
 * 
 * Never returns internal IDs (e.g. DOC-5FFD839CD910) as the primary name.
 */
export function resolveDocumentName(
  rawNameOrId?: string | null,
  knownDocs?: GuidelineDocument[]
): string {
  if (!rawNameOrId || !rawNameOrId.trim()) {
    return 'Document name not available';
  }

  const trimmed = rawNameOrId.trim();

  // 1. Direct match in built-in mapping registry
  if (DOCUMENT_ORIGINAL_NAMES[trimmed]) {
    return DOCUMENT_ORIGINAL_NAMES[trimmed];
  }

  // 2. Check if this is a chunk ID starting with a known document ID (e.g. DOC-5FFD839CD910-0017-...)
  const docIdPrefixMatch = trimmed.match(/^(DOC-[A-Z0-9]+)/i);
  if (docIdPrefixMatch) {
    const docId = docIdPrefixMatch[1].toUpperCase();
    if (DOCUMENT_ORIGINAL_NAMES[docId]) {
      return DOCUMENT_ORIGINAL_NAMES[docId];
    }
  }

  // 3. Match against known documents from state or repository
  if (knownDocs && knownDocs.length > 0) {
    // Match by exact ID or doc ID prefix
    const matchedDoc = knownDocs.find((d) => {
      if (d.id && (d.id.toLowerCase() === trimmed.toLowerCase() || (docIdPrefixMatch && d.id.toLowerCase() === docIdPrefixMatch[1].toLowerCase()))) {
        return true;
      }
      return false;
    });

    if (matchedDoc && matchedDoc.name) {
      return resolveDocumentName(matchedDoc.name);
    }

    // Match by base name (e.g. "DM RR" from "DM RR.md")
    const rawStem = trimmed.replace(/\.[^/.]+$/, '').toLowerCase();
    const stemMatch = knownDocs.find((d) => {
      const docStem = d.name.replace(/\.[^/.]+$/, '').toLowerCase();
      return docStem === rawStem;
    });

    if (stemMatch && stemMatch.name) {
      if (stemMatch.name.endsWith('.md') && DOCUMENT_ORIGINAL_NAMES[stemMatch.name]) {
        return DOCUMENT_ORIGINAL_NAMES[stemMatch.name];
      }
      return stemMatch.name;
    }
  }

  // 4. If name ends with .md, convert to candidate original extension if registered
  if (trimmed.toLowerCase().endsWith('.md')) {
    const docxKey = trimmed.replace(/\.md$/i, '.docx');
    if (DOCUMENT_ORIGINAL_NAMES[docxKey]) return DOCUMENT_ORIGINAL_NAMES[docxKey];
    const pdfKey = trimmed.replace(/\.md$/i, '.pdf');
    if (DOCUMENT_ORIGINAL_NAMES[pdfKey]) return DOCUMENT_ORIGINAL_NAMES[pdfKey];
  }

  // 5. If it looks like an unmapped internal ID (e.g. DOC-XXXXX), do not expose raw ID
  if (/^DOC-[A-Z0-9]+/i.test(trimmed)) {
    return 'Guideline Clinical Protocol';
  }

  return trimmed;
}

/**
 * Formats and validates the page citation from retrieved evidence metadata.
 * 
 * Rules:
 * - Preserves actual source page number.
 * - Does NOT use chunk number as page number.
 * - Does NOT invent a page number when missing.
 * - If page cannot be verified, displays 'Page not available'.
 */
export function formatPageCitation(page: number | string | null | undefined): {
  pageNumber: number | null;
  display: string;
  isAvailable: boolean;
} {
  if (page === null || page === undefined || page === '' || page === 'N/A') {
    return {
      pageNumber: null,
      display: 'Not available',
      isAvailable: false,
    };
  }

  const parsed = typeof page === 'number' ? page : parseInt(String(page).trim(), 10);
  if (!isNaN(parsed) && parsed > 0) {
    return {
      pageNumber: parsed,
      display: `${parsed}`,
      isAvailable: true,
    };
  }

  return {
    pageNumber: null,
    display: 'Not available',
    isAvailable: false,
  };
}

/**
 * Resolves evidence citations for an individual medicine item.
 * 
 * Maps each supporting_chunk_id to its corresponding EvidenceSource chunk,
 * resolving original document filenames and verifying page provenance.
 */
export function resolveMedicineCitations(
  medicine: MedicineItem,
  evidenceSources: EvidenceSource[] = [],
  knownDocs?: GuidelineDocument[]
): ResolvedMedicineCitation[] {
  const citations: ResolvedMedicineCitation[] = [];
  const chunkIds = medicine.supporting_chunk_ids || [];

  for (const cid of chunkIds) {
    if (!cid || typeof cid !== 'string' || !cid.trim()) continue;
    const cleanId = cid.trim();

    // 1. Find matching source in retrieved evidence chunks
    let matchedSource = evidenceSources.find(
      (s) => s.chunk_id === cleanId || s.chunk_id?.toLowerCase() === cleanId.toLowerCase()
    );

    // 2. Try partial match if model returned full or abbreviated chunk ID
    if (!matchedSource) {
      matchedSource = evidenceSources.find(
        (s) => s.chunk_id && (s.chunk_id.includes(cleanId) || cleanId.includes(s.chunk_id))
      );
    }

    // 3. Fallback: match by chunk rank/number if model returned e.g. "CHUNK 1"
    if (!matchedSource) {
      const chunkNumMatch = cleanId.match(/chunk\s*#?\s*(\d+)/i);
      if (chunkNumMatch) {
        const rank = parseInt(chunkNumMatch[1], 10);
        matchedSource = evidenceSources.find((s) => s.rank === rank) || evidenceSources[rank - 1];
      }
    }

    if (matchedSource) {
      const docName = resolveDocumentName(
        matchedSource.document_name || matchedSource.chunk_id,
        knownDocs
      );
      const pageInfo = formatPageCitation(matchedSource.page);

      citations.push({
        chunk_id: matchedSource.chunk_id,
        document_name: docName,
        page: pageInfo.pageNumber,
        page_display: pageInfo.display,
        has_verified_page: pageInfo.isAvailable,
        section: matchedSource.section || null,
        content: matchedSource.content || null,
        rank: matchedSource.rank,
        distance: matchedSource.distance,
      });
    } else {
      // Chunk ID was cited by the LLM but not present in top-K evidence sources
      const docName = resolveDocumentName(cleanId, knownDocs);
      citations.push({
        chunk_id: cleanId,
        document_name: docName,
        page: null,
        page_display: 'Not available',
        has_verified_page: false,
        section: null,
        content: null,
      });
    }
  }

  return citations;
}

/**
 * Represents a reference cited within clinical guidance paragraphs.
 */
export interface ClinicalGuidanceReference {
  citationNumber: number;
  document_name: string;
  page_display: string;
  has_verified_page: boolean;
  medicines: string[];
  citation: ResolvedMedicineCitation;
}

/**
 * Builds unique references for clinical guidance based on prescribed medicines and their citations.
 */
export function buildClinicalGuidanceReferences(
  medicines: MedicineItem[],
  evidenceSources: EvidenceSource[],
  knownDocs?: GuidelineDocument[]
): ClinicalGuidanceReference[] {
  const references: ClinicalGuidanceReference[] = [];
  const keyMap = new Map<string, ClinicalGuidanceReference>();

  for (const m of medicines) {
    const citations = resolveMedicineCitations(m, evidenceSources, knownDocs);
    for (const c of citations) {
      const key = `${c.document_name}::${c.page_display}::${c.chunk_id}`;
      if (keyMap.has(key)) {
        const existing = keyMap.get(key)!;
        if (!existing.medicines.includes(m.medicine)) {
          existing.medicines.push(m.medicine);
        }
      } else {
        const ref: ClinicalGuidanceReference = {
          citationNumber: references.length + 1,
          document_name: c.document_name,
          page_display: c.page_display,
          has_verified_page: c.has_verified_page,
          medicines: [m.medicine],
          citation: c,
        };
        keyMap.set(key, ref);
        references.push(ref);
      }
    }
  }

  return references;
}
