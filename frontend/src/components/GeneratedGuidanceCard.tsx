import React from 'react';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  RefreshCw,
  Info,
  Clock,
} from 'lucide-react';
import type { GenerationResult } from '../types';

interface GeneratedGuidanceCardProps {
  isLoading: boolean;
  result: GenerationResult | null;
  error: string | null;
  onRetry?: () => void;
}

// Clean helper to render simple markdown text into formatted elements
const FormattedMarkdown: React.FC<{ content: string }> = ({ content }) => {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];

  let inList = false;
  let listItems: React.ReactNode[] = [];

  const flushList = () => {
    if (inList && listItems.length > 0) {
      elements.push(
        <ul key={`list-${elements.length}`} className="list-disc pl-5 my-2 space-y-1 text-slate-700">
          {listItems}
        </ul>
      );
      listItems = [];
      inList = false;
    }
  };

  const formatInline = (text: string): React.ReactNode => {
    // Basic bold parsing: **text**
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-slate-900">{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    if (!trimmed) {
      flushList();
      return;
    }

    if (trimmed.startsWith('### ')) {
      flushList();
      elements.push(
        <h4 key={index} className="text-base font-semibold text-slate-900 mt-4 mb-1">
          {formatInline(trimmed.slice(4))}
        </h4>
      );
    } else if (trimmed.startsWith('## ')) {
      flushList();
      elements.push(
        <h3 key={index} className="text-lg font-bold text-slate-900 mt-5 mb-2 pb-1 border-b border-slate-100">
          {formatInline(trimmed.slice(3))}
        </h3>
      );
    } else if (trimmed.startsWith('# ')) {
      flushList();
      elements.push(
        <h2 key={index} className="text-xl font-bold text-slate-900 mt-6 mb-2">
          {formatInline(trimmed.slice(2))}
        </h2>
      );
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      inList = true;
      listItems.push(
        <li key={`li-${index}`} className="text-sm leading-relaxed">
          {formatInline(trimmed.slice(2))}
        </li>
      );
    } else if (/^\d+\.\s/.test(trimmed)) {
      flushList();
      const text = trimmed.replace(/^\d+\.\s/, '');
      elements.push(
        <div key={index} className="flex gap-2 text-sm text-slate-700 my-1">
          <span className="font-semibold text-blue-700">{trimmed.match(/^\d+\./)?.[0]}</span>
          <span>{formatInline(text)}</span>
        </div>
      );
    } else if (trimmed.startsWith('> ')) {
      flushList();
      elements.push(
        <div key={index} className="border-l-4 border-blue-500 pl-3 py-1 my-2 bg-blue-50/60 rounded-r text-sm text-slate-700 italic">
          {formatInline(trimmed.slice(2))}
        </div>
      );
    } else {
      flushList();
      elements.push(
        <p key={index} className="text-sm text-slate-700 leading-relaxed my-2">
          {formatInline(trimmed)}
        </p>
      );
    }
  });

  flushList();

  return <div className="space-y-1 text-slate-800">{elements}</div>;
};

export const GeneratedGuidanceCard: React.FC<GeneratedGuidanceCardProps> = ({
  isLoading,
  result,
  error,
  onRetry,
}) => {
  // 1. Loading State
  if (isLoading) {
    return (
      <div className="card text-center py-16" id="guidance-loading-state">
        <div className="flex flex-col items-center justify-center gap-4">
          <div className="relative">
            <span className="spinner w-10 h-10 border-4 border-blue-100 border-t-blue-600" />
            <BookOpen className="w-4 h-4 text-blue-600 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-slate-900">
              Generating Grounded Clinical Guidance
            </h3>
            <p className="text-sm text-slate-500 max-w-md mx-auto">
              Retrieving guideline evidence and generating clinical guidance...
            </p>
          </div>
        </div>
      </div>
    );
  }

  // 2. Error State
  if (error) {
    return (
      <div className="card border-red-200 bg-red-50/30" id="guidance-error-state">
        <div className="flex items-start gap-3 p-2">
          <div className="p-2 rounded-lg bg-red-100 text-red-700 shrink-0">
            <AlertTriangle size={20} />
          </div>
          <div className="flex-1 space-y-1">
            <h3 className="text-sm font-semibold text-red-900">Generation Error</h3>
            <p className="text-sm text-red-700 leading-relaxed">{error}</p>
            {onRetry && (
              <div className="pt-2">
                <button
                  type="button"
                  onClick={onRetry}
                  className="btn btn-secondary text-xs flex items-center gap-1.5 border-red-300 text-red-800 hover:bg-red-50"
                >
                  <RefreshCw size={13} />
                  Retry Query
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // 3. Not generated yet - hidden per reference layout
  if (!result) {
    return null;
  }

  // 4. Success / Result State
  return (
    <div className="card space-y-6" id="guidance-result-card">
      {/* Result Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <span className="p-1.5 rounded-lg bg-emerald-50 text-emerald-700">
            <CheckCircle2 size={18} />
          </span>
          <div>
            <h2 className="card-title">Generated Clinical Guidance</h2>
            <p className="card-subtitle">
              Ayurvedic treatment protocol synthesized from verified clinical guidelines
            </p>
          </div>
        </div>

        {result.model && (
          <span className="badge badge-neutral text-xs flex items-center gap-1">
            <Clock size={11} />
            {result.model}
          </span>
        )}
      </div>

      {/* Advisory Notice if partial or fallback */}
      {result.notice && (
        <div className="flex items-start gap-2.5 text-xs text-amber-800 bg-amber-50 p-3 rounded-lg border border-amber-200">
          <Info size={16} className="shrink-0 mt-0.5 text-amber-700" />
          <div className="leading-relaxed">
            <span className="font-semibold">Notice: </span>
            {result.notice}
          </div>
        </div>
      )}

      {/* Main Clinical Guidance Answer */}
      <div className="bg-slate-50/60 rounded-xl p-5 border border-slate-100 text-slate-800 leading-relaxed">
        <FormattedMarkdown content={result.answer} />
      </div>

      {/* Evidence & Sources Section */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen size={16} className="text-blue-700" />
            <h3 className="text-sm font-semibold text-slate-900">Evidence & Sources</h3>
          </div>
          <span className="text-xs text-slate-500">
            {result.sources.length} retrieved reference{result.sources.length === 1 ? '' : 's'}
          </span>
        </div>

        {result.sources.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No specific sources cited.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2.5">
            {result.sources.map((source, index) => (
              <div
                key={source.chunk_id || index}
                className="bg-white rounded-lg border border-slate-200 p-3 text-xs shadow-xs hover:border-blue-300 transition-colors"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-semibold text-[11px]">
                      Rank #{source.rank ?? index + 1}
                    </span>
                    <span className="font-semibold text-slate-900 truncate max-w-xs md:max-w-md">
                      {source.document_name || 'Guideline Protocol'}
                    </span>
                  </div>
                  {source.chunk_id && (
                    <span className="font-mono text-slate-400 text-[10px]">
                      {source.chunk_id}
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 text-slate-600 mt-2 pt-2 border-t border-slate-100">
                  <div className="truncate">
                    <span className="text-slate-400">Section: </span>
                    <span className="font-medium text-slate-700">
                      {source.section || 'General Protocol'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Page: </span>
                    <span className="font-medium text-slate-700">
                      {source.page !== null && source.page !== undefined ? `Page ${source.page}` : 'N/A'}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Limitations & Missing Information Section */}
      {result.limitations && (
        <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 space-y-1.5">
          <div className="flex items-center gap-1.5 text-amber-900 font-semibold text-xs">
            <AlertTriangle size={14} className="text-amber-700" />
            <span>Limitations & Missing Information</span>
          </div>
          <p className="text-xs text-amber-800 leading-relaxed">
            {result.limitations}
          </p>
        </div>
      )}
    </div>
  );
};
