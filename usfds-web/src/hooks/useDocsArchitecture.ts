import { useEffect, useState } from 'react';
import { docsDashboardApi } from '@/api/docsDashboardApi';
import { ARCHITECTURE_DIAGRAMS, extractArchitectureDiagram } from '@/utils/docsArchitecture';

export function useDocsArchitecture(initialId?: string) {
	const [selectedId, setSelectedId] = useState(initialId ?? ARCHITECTURE_DIAGRAMS[0].id);
	const [retryCount, setRetryCount] = useState(0);
	const [result, setResult] = useState<{ id: string; version: number; code: string; error: string | null } | null>(null);
	const diagram = ARCHITECTURE_DIAGRAMS.find((item) => item.id === selectedId) ?? ARCHITECTURE_DIAGRAMS[0];

	useEffect(() => {
		let cancelled = false;
		docsDashboardApi.getFile(diagram.path).then((file) => {
			const code = extractArchitectureDiagram(file.content, diagram);
			if (!cancelled) setResult({ id: diagram.id, version: retryCount, code, error: null });
		}).catch((error: unknown) => {
			if (!cancelled) setResult({
				id: diagram.id,
				version: retryCount,
				code: '',
				error: error instanceof Error ? error.message : String(error),
			});
		});
		return () => { cancelled = true; };
	}, [diagram, retryCount]);

	return {
		diagram,
		selectDiagram: (id: string) => {
			setSelectedId(id);
			setRetryCount((count) => count + 1);
		},
		loading: result?.id !== diagram.id || result.version !== retryCount,
		code: result?.id === diagram.id && result.version === retryCount ? result.code : '',
		error: result?.id === diagram.id && result.version === retryCount ? result.error : null,
		retry: () => setRetryCount((count) => count + 1),
	};
}
