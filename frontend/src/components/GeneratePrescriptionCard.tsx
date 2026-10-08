import { Sparkles, Loader2 } from 'lucide-react';

interface GeneratePrescriptionCardProps {
  onGenerate: () => void;
  isLoading: boolean;
  isPatientSelected: boolean;
}

export const GeneratePrescriptionCard: React.FC<GeneratePrescriptionCardProps> = ({
  onGenerate,
  isLoading,
  isPatientSelected,
}) => {
  return (
    <div className="card" id="generate-prescription-card">
      {/* Card Header */}
      <div className="card-header pb-3 border-b border-slate-200">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <span>💊 3. Generate Prescription</span>
        </h2>
      </div>

      <div className="pt-4 space-y-3">
        <button
          type="button"
          id="generate-prescription-btn"
          onClick={onGenerate}
          disabled={isLoading || !isPatientSelected}
          className={`btn w-full py-3 px-4 rounded-lg font-semibold text-sm flex items-center justify-center gap-2 transition-all ${
            isPatientSelected && !isLoading
              ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm cursor-pointer'
              : 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed'
          }`}
        >
          {isLoading ? (
            <>
              <Loader2 size={16} className="animate-spin text-white" />
              <span>Retrieving guideline evidence and generating clinical guidance...</span>
            </>
          ) : (
            <>
              <Sparkles size={16} />
              <span>Generate Prescription</span>
            </>
          )}
        </button>

        {!isPatientSelected && (
          <p className="text-[11px] text-center text-slate-500">
            Please select a patient in step 2 to enable prescription generation.
          </p>
        )}
      </div>
    </div>
  );
};
