import { useEffect, useMemo, useRef, useState } from 'react';
import { docsDashboardApi, type ParsedPlan } from '@/api/docsDashboardApi';
import { headingSlug } from '@/utils/docsArchitecture';
import { getPlanArchitectureLinks, type PlanArchitectureLink } from '@/utils/planArchitectureLinks';
import type { InspectorTarget } from '@/components/modules/docs_dashboard/ContextInspectorPane';

export function usePlanArchitectureLinks(plan: ParsedPlan, onSelectFileRef: (path: string) => void, inspectorSelection?: InspectorTarget) {
	const links = useMemo(() => getPlanArchitectureLinks(plan), [plan]);
	const [error, setError] = useState<string | null>(null);
	const requestVersion = useRef(0);
	useEffect(() => {
		requestVersion.current += 1;
		setError(null);
		return () => { requestVersion.current += 1; };
	}, [plan.slug, inspectorSelection]);

	const openLink = async (link: PlanArchitectureLink) => {
		const version = ++requestVersion.current;
		setError(null);
		try {
			if (link.error) throw new Error(link.error);
			if (!link.invariantId) {
				onSelectFileRef(link.path);
				return;
			}
			const file = await docsDashboardApi.getFile(link.path);
			if (version !== requestVersion.current) return;
			const headings = file.content.split(/\r?\n/).filter((line) =>
				/^###\s/.test(line) && line.includes(`\`${link.invariantId}\``),
			);
			if (headings.length !== 1) {
				throw new Error(`Không tìm thấy mục duy nhất cho ${link.invariantId} trong ${link.path}.`);
			}
			onSelectFileRef(`${link.path}#${headingSlug(headings[0].replace(/^###\s+/, ''))}`);
		} catch (err) {
			if (version === requestVersion.current) setError(err instanceof Error ? err.message : String(err));
		}
	};
	return { ...links, error, openLink };
}
