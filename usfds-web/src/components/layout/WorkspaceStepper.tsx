import { Fragment } from 'react';
import { Check, Lock, GitFork } from 'lucide-react';

export type StepState = 'completed' | 'active' | 'locked';

export interface PipelineStep {
  id: string;
  stepNumber: number;
  label: string;
  description?: string;
  state: StepState;
}

interface WorkspaceStepperProps {
  steps: PipelineStep[];
  currentStepId: string;
  onSelectStep: (stepId: string) => void;
  branchName?: string;
  forkedFromArtifactId?: string;
}

export const WorkspaceStepper = ({
  steps,
  currentStepId,
  onSelectStep,
  branchName,
  forkedFromArtifactId,
}: WorkspaceStepperProps) => {
  return (
    <div className="bg-dark-900 border-b border-dark-700/80 px-6 py-3 select-none flex flex-col md:flex-row md:items-center justify-between gap-3 shrink-0">
      {/* Steps Track */}
      <div className="flex items-center gap-2 overflow-x-auto py-1">
        {steps.map((step, idx) => {
          const isCurrent = step.id === currentStepId;
          const isCompleted = step.state === 'completed';
          const isLocked = step.state === 'locked';

          return (
            <Fragment key={step.id}>
              {/* Stepper Node Button */}
              <button
                disabled={isLocked}
                onClick={() => onSelectStep(step.id)}
                className={`flex items-center gap-2.5 px-3 py-1.5 rounded-lg border transition text-xs font-medium focus-ring ${
                  isCurrent
                    ? 'bg-brand-500/15 border-brand-500/50 text-white shadow-glow-blue'
                    : isCompleted
                    ? 'bg-dark-850 hover:bg-dark-800 border-emerald-500/30 text-emerald-400'
                    : 'bg-dark-950/60 border-dark-800 text-slate-500 cursor-not-allowed opacity-60'
                }`}
              >
                {/* Node Circle */}
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold font-mono transition ${
                    isCurrent
                      ? 'bg-brand-500 text-white ring-2 ring-brand-400/40'
                      : isCompleted
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                      : 'bg-dark-800 text-slate-500 border border-dark-700'
                  }`}
                >
                  {isCompleted ? (
                    <Check className="w-3 h-3 stroke-[3]" />
                  ) : isLocked ? (
                    <Lock className="w-2.5 h-2.5" />
                  ) : (
                    step.stepNumber
                  )}
                </div>

                <div className="flex flex-col text-left">
                  <span className={`text-[11px] leading-tight font-semibold ${
                    isCurrent ? 'text-slate-100' : isCompleted ? 'text-slate-200' : 'text-slate-500'
                  }`}>
                    {step.label}
                  </span>
                  {step.description && (
                    <span className="text-[10px] text-slate-500 hidden xl:inline">
                      {step.description}
                    </span>
                  )}
                </div>
              </button>

              {/* Connecting Line */}
              {idx < steps.length - 1 && (
                <div className={`h-[2px] w-6 shrink-0 rounded transition ${
                  isCompleted ? 'bg-emerald-500/40' : 'bg-dark-700/60'
                }`} />
              )}
            </Fragment>
          );
        })}
      </div>

      {/* Lineage Branching Indicator (if branched) */}
      {branchName && (
        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-purple-500/10 border border-purple-500/30 text-[11px] text-purple-300 font-mono shrink-0">
          <GitFork className="w-3.5 h-3.5 text-purple-400" />
          <span>Branch: <span className="font-semibold text-purple-200">{branchName}</span></span>
          {forkedFromArtifactId && (
            <span className="text-slate-400 text-[10px]">
              (forked from {forkedFromArtifactId})
            </span>
          )}
        </div>
      )}
    </div>
  );
};
