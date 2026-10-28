import React from 'react';
import { ShieldCheck, Edit2, CheckCircle, AlertTriangle, Lock, Unlock } from 'lucide-react';
import type {
	RuleGroup,
	RuleAction,
	RuleStatus,
	AvailableFeatureField,
} from '../../../types/rule';
import { RuleGroupCard } from './RuleGroupCard';
import { RuleOutcomeCard } from './RuleOutcomeCard';
import { RuleNaturalLanguageCard } from './RuleNaturalLanguageCard';
import { RuleCompiledJsonCard } from './RuleCompiledJsonCard';

interface RuleStudioWorkspaceProps {
	ruleCode: string;
	setRuleCode: (val: string) => void;
	ruleName: string;
	setRuleName: (val: string) => void;
	status: RuleStatus;
	setStatus: (val: RuleStatus) => void;
	action: RuleAction;
	setAction: (val: RuleAction) => void;
	description: string;
	setDescription: (val: string) => void;
	changeSummary: string;
	setChangeSummary: (val: string) => void;
	conditionGroup: RuleGroup;
	setConditionGroup: (group: RuleGroup) => void;
	saveSuccessNotice: boolean;
	availableFields?: AvailableFeatureField[];
	isSchemaLocked?: boolean;
	isNew?: boolean;
	errorMessage?: string | null;
}

export const RuleStudioWorkspace: React.FC<RuleStudioWorkspaceProps> = ({
	ruleCode,
	setRuleCode,
	ruleName,
	setRuleName,
	status,
	setStatus,
	action,
	setAction,
	description,
	setDescription,
	changeSummary,
	setChangeSummary,
	conditionGroup,
	setConditionGroup,
	saveSuccessNotice,
	availableFields,
	isSchemaLocked = false,
	isNew = true,
	errorMessage,
}) => {
	return (
		<div className="flex-1 p-6 overflow-y-auto space-y-5 bg-dark-950">
			{/* Error Banner (BR-PM-04 / BR-PM-05 / Duplicate Code) */}
			{errorMessage && (
				<div className="p-3.5 rounded-xl bg-red-950/40 border border-red-500/50 text-red-300 text-xs flex items-start gap-2.5">
					<AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
					<div className="space-y-0.5">
						<div className="font-semibold text-red-200">Không thể lưu hoặc kích hoạt quy tắc</div>
						<div className="text-red-300/90 font-mono text-[11px]">{errorMessage}</div>
					</div>
				</div>
			)}

			{/* Schema Governance Banner (BR-PM-04) */}
			{!isSchemaLocked && (
				<div className="p-3 rounded-xl bg-amber-950/30 border border-amber-500/40 text-amber-300 text-xs flex items-center justify-between gap-3">
					<div className="flex items-center gap-2">
						<Unlock className="w-4 h-4 text-amber-400 shrink-0" />
						<span>
							Dự án hiện tại chưa khóa <strong>RAW Schema</strong> (chưa tải lên Dataset đầu tiên). Theo quy tắc{' '}
							<code className="font-mono text-amber-200">BR-PM-04</code>, quy tắc chỉ có thể lưu ở trạng thái{' '}
							<strong>DRAFT</strong> hoặc <strong>INACTIVE</strong>.
						</span>
					</div>
				</div>
			)}

			{/* 1. Metadata Bar */}
			<div className="p-4 rounded-xl bg-dark-900 border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4 shadow-sm">
				<div className="flex flex-col sm:flex-row sm:items-center gap-3 w-full">
					{/* Rule Code */}
					<div className="w-40">
						<label className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1">
							Rule Code
						</label>
						<input
							type="text"
							value={ruleCode}
							disabled={!isNew}
							onChange={(e) => setRuleCode(e.target.value.toUpperCase())}
							placeholder="R-XXX"
							className={`w-full bg-dark-950 border border-slate-800 focus:border-brand-500 text-brand-300 text-xs font-mono font-bold rounded-lg px-3 py-2 focus:outline-none ${
								!isNew ? 'opacity-70 cursor-not-allowed' : ''
							}`}
						/>
					</div>

					{/* Rule Name */}
					<div className="flex-1">
						<label className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1">
							Rule Name
						</label>
						<div className="relative">
							<input
								type="text"
								value={ruleName}
								onChange={(e) => setRuleName(e.target.value)}
								className="w-full bg-dark-950 border border-slate-800 focus:border-brand-500 text-slate-100 text-sm font-semibold rounded-lg px-3 py-2 pr-8 focus:outline-none transition-colors"
							/>
							<Edit2 className="w-3.5 h-3.5 absolute right-3 top-2.5 text-slate-500 pointer-events-none" />
						</div>
					</div>

					{/* Status */}
					<div className="w-40">
						<label className="block text-[10px] font-mono uppercase tracking-wider text-slate-400 mb-1">
							Trạng thái
						</label>
						<select
							value={status}
							onChange={(e) => setStatus(e.target.value as RuleStatus)}
							aria-label="Trạng thái"
							className="w-full bg-dark-950 border border-slate-800 focus:border-brand-500 text-slate-200 text-xs font-mono rounded-lg px-3 py-2 appearance-none focus:outline-none cursor-pointer"
						>
							<option value="DRAFT">DRAFT</option>
							<option value="ACTIVE" disabled={!isSchemaLocked}>
								ACTIVE {!isSchemaLocked ? '(Cần RAW Schema)' : ''}
							</option>
							<option value="INACTIVE">INACTIVE</option>
						</select>
					</div>
				</div>

				{saveSuccessNotice && (
					<div className="text-emerald-400 text-xs flex items-center gap-1 font-sans shrink-0 font-medium">
						<CheckCircle className="w-4 h-4" /> Đã lưu thành công!
					</div>
				)}
			</div>

			{/* 2. Split-pane: 60% Left Condition & Outcome vs 40% Right Preview */}
			<div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
				{/* Left Pane (60%) */}
				<div className="lg:col-span-7 bg-dark-900 border border-slate-800 rounded-xl p-5 lg:p-6 space-y-6 shadow-sm">
					{/* Condition Section */}
					<div>
						<div className="flex items-center justify-between pb-3 border-b border-slate-800">
							<div className="flex items-center gap-2">
								<ShieldCheck className="w-4 h-4 text-brand-400" />
								<h2 className="text-xs font-bold tracking-wider uppercase text-slate-200 font-mono">
									LOGICAL EVALUATION CONDITIONS (IF)
								</h2>
							</div>
							<span
								className={`text-[10px] font-mono px-2 py-0.5 rounded border flex items-center gap-1 ${
									isSchemaLocked
										? 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
										: 'bg-slate-800/80 border-slate-700 text-slate-400'
								}`}
							>
								{isSchemaLocked ? (
									<>
										<Lock className="w-2.5 h-2.5" />
										<span>RAW Schema Locked ({availableFields?.length || 0} cols)</span>
									</>
								) : (
									<>
										<Unlock className="w-2.5 h-2.5" />
										<span>Default Template Fields</span>
									</>
								)}
							</span>
						</div>

						<div className="mt-4">
							<RuleGroupCard
								group={conditionGroup}
								availableFields={availableFields}
								onChange={setConditionGroup}
							/>
						</div>
					</div>

					{/* Outcome Section */}
					<RuleOutcomeCard
						action={action}
						description={description}
						changeSummary={changeSummary}
						onChangeAction={setAction}
						onChangeDescription={setDescription}
						onChangeChangeSummary={setChangeSummary}
					/>
				</div>

				{/* Right Pane (40%) */}
				<div className="lg:col-span-5 space-y-5">
					<RuleNaturalLanguageCard group={conditionGroup} action={action} />
					<RuleCompiledJsonCard group={conditionGroup} />
				</div>
			</div>
		</div>
	);
};
