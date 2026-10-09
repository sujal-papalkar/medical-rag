import React from 'react';
import { AlertCircle } from 'lucide-react';

interface LimitationsCardProps {
  limitations: string[];
}

export const LimitationsCard: React.FC<LimitationsCardProps> = ({ limitations }) => {
  if (!limitations || limitations.length === 0) {
    return null;
  }

  return (
    <div className="bg-amber-50/70 border border-amber-200 rounded-lg p-3 space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs font-bold text-amber-900">
        <AlertCircle size={14} className="text-amber-700 shrink-0" />
        <span>Limitations & Missing Guideline Information:</span>
      </div>
      <ul className="list-disc pl-5 space-y-0.5 text-xs text-amber-800">
        {limitations.map((lim, idx) => (
          <li key={idx} className="leading-relaxed">
            {lim}
          </li>
        ))}
      </ul>
    </div>
  );
};
