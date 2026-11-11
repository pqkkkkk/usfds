import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
	BarChart3,
	FileCheck2,
	Gauge,
	Radar,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/PageHeader';
import { useProject } from '@/hooks/useProjects';
import { detectionApi, insightReportApi } from '@/api';
import type { ReportScopeFilter } from '@/types';
import { ReportScopeToolbar } from './reports/ReportScopeToolbar';
import { ExecutiveOverviewTab } from './reports/ExecutiveOverviewTab';
import { EffectivenessTab } from './reports/EffectivenessTab';
import { TypologiesPatternsTab } from './reports/TypologiesPatternsTab';
import { ComplianceReportCenterTab } from './reports/ComplianceReportCenterTab';

type ReportTabKey = 'overview' | 'effectiveness' | 'patterns' | 'compliance';

const REPORT_TABS: { key: ReportTabKey; label: string; icon: React.ReactNode }[] = [
	{ key: 'overview', label: 'Executive Overview', icon: <BarChart3 size={14} /> },
	{ key: 'effectiveness', label: 'Model & Rule Effectiveness', icon: <Gauge size={14} /> },
	{ key: 'patterns', label: 'Typologies & Patterns', icon: <Radar size={14} /> },
	{ key: 'compliance', label: 'Compliance & SAR Center', icon: <FileCheck2 size={14} /> },
];

export const InsightReportModule: React.FC = () => {
	const { currentProjectId, currentProject, isLoading: isProjectLoading } = useProject();
	const [searchParams, setSearchParams] = useSearchParams();
	const initialTabParam = (searchParams.get('tab') as ReportTabKey) || 'overview';
	const caseIdParam = searchParams.get('caseId') || undefined;

	const [activeTab, setActiveTab] = useState<ReportTabKey>(
		REPORT_TABS.some((t) => t.key === initialTabParam) ? initialTabParam : 'overview'
	);
	const [scope, setScope] = useState<ReportScopeFilter>({
		useDatasetFallback: true,
	});

	useEffect(() => {
		const tabFromUrl = searchParams.get('tab') as ReportTabKey | null;
		if (tabFromUrl && REPORT_TABS.some((t) => t.key === tabFromUrl)) {
			setActiveTab(tabFromUrl);
		}
	}, [searchParams]);

	const handleTabChange = (nextTab: ReportTabKey) => {
		setActiveTab(nextTab);
		const nextParams = new URLSearchParams(searchParams);
		nextParams.set('tab', nextTab);
		if (nextTab !== 'compliance') {
			nextParams.delete('caseId');
		}
		setSearchParams(nextParams, { replace: true });
	};

	// Load project Detection Jobs for scope toolbar
	const { data: detectionJobsRes } = useQuery({
		queryKey: ['detection-jobs', currentProjectId],
		queryFn: () => detectionApi.listJobs({ projectId: currentProjectId! }),
		enabled: Boolean(currentProjectId),
	});

	const detectionJobsList = useMemo(() => {
		if (!detectionJobsRes) {
			return [];
		}
		if (Array.isArray(detectionJobsRes)) {
			return detectionJobsRes;
		}
		if (Array.isArray((detectionJobsRes as any)?.data)) {
			return (detectionJobsRes as any).data;
		}
		return [];
	}, [detectionJobsRes]);

	// Overview query
	const { data: overviewData, isLoading: isOverviewLoading } = useQuery({
		queryKey: ['insight-overview', currentProjectId, scope],
		queryFn: () => insightReportApi.getOverview(currentProjectId!, scope),
		enabled: Boolean(currentProjectId && activeTab === 'overview'),
	});

	// Effectiveness query
	const { data: effectivenessData, isLoading: isEffectivenessLoading } = useQuery({
		queryKey: ['insight-effectiveness', currentProjectId, scope],
		queryFn: () => insightReportApi.getEffectiveness(currentProjectId!, scope),
		enabled: Boolean(currentProjectId && activeTab === 'effectiveness'),
	});

	// Patterns query
	const { data: patternsData, isLoading: isPatternsLoading } = useQuery({
		queryKey: ['insight-patterns', currentProjectId, scope],
		queryFn: () => insightReportApi.getPatterns(currentProjectId!, scope),
		enabled: Boolean(currentProjectId && activeTab === 'patterns'),
	});

	const activeTabMeta = REPORT_TABS.find((t) => t.key === activeTab) || REPORT_TABS[0];

	return (
		<div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-dark-950 text-slate-100">
			<PageHeader
				title="Insight & Compliance Reporting"
				subtitle={
					currentProject
						? `Phân tích hiệu quả tài chính, đối chuẩn mô hình AI/Rule, nhận diện xu hướng gian lận và trích xuất hồ sơ SAR cho dự án "${currentProject.project_name}"`
						: 'Trung tâm phân tích hiệu quả phòng chống gian lận, kiểm định chính sách và báo cáo tuân thủ'
				}
				breadcrumbs={[
					{ label: 'Insight & Report', href: '/reports' },
					{ label: activeTabMeta.label },
				]}
				actions={
					<nav
						className="inline-flex flex-wrap items-center rounded-lg border border-dark-700 bg-dark-900 p-1 text-xs"
						aria-label="Insight & Report tabs"
					>
						{REPORT_TABS.map((tab) => {
							const isActive = activeTab === tab.key;
							return (
								<button
									key={tab.key}
									type="button"
									onClick={() => handleTabChange(tab.key)}
									className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 font-medium transition-colors cursor-pointer ${
										isActive
											? 'bg-brand-600 text-white shadow-sm'
											: 'text-slate-300 hover:text-white'
									}`}
								>
									{tab.icon}
									<span>{tab.label}</span>
								</button>
							);
						})}
					</nav>
				}
			/>

			<main className="min-w-0 flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
				{isProjectLoading ? (
					<div className="rounded-xl border border-dark-700/80 bg-dark-900 p-6 text-sm text-slate-300">
						Loading project context...
					</div>
				) : !currentProjectId ? (
					<div className="rounded-xl border border-dark-700/80 bg-dark-900 p-6 text-sm text-slate-300">
						Select a project from the top navigation bar to view insights and compliance reports.
					</div>
				) : (
					<>
						<ReportScopeToolbar
							scope={scope}
							onChange={setScope}
							detectionJobs={detectionJobsList}
							scannedJobsCount={overviewData?.available_jobs?.length}
						/>

						{activeTab === 'overview' && (
							<ExecutiveOverviewTab data={overviewData} isLoading={isOverviewLoading} />
						)}

						{activeTab === 'effectiveness' && (
							<EffectivenessTab data={effectivenessData} isLoading={isEffectivenessLoading} />
						)}

						{activeTab === 'patterns' && (
							<TypologiesPatternsTab data={patternsData} isLoading={isPatternsLoading} />
						)}

						{activeTab === 'compliance' && (
							<ComplianceReportCenterTab
								projectId={currentProjectId}
								scope={scope}
								initialCaseId={caseIdParam}
							/>
						)}
					</>
				)}
			</main>
		</div>
	);
};
