import React from 'react';
import { useDocsArchitecture } from '@/hooks/useDocsArchitecture';
import { ARCHITECTURE_DIAGRAMS, headingSlug } from '@/utils/docsArchitecture';
import { MermaidDiagram } from './MermaidDiagram';

interface ArchitectureReviewViewProps {
	isLight: boolean;
	onSelectFileRef: (path: string) => void;
	initialDiagramId?: string;
}

export const ArchitectureReviewView: React.FC<ArchitectureReviewViewProps> = ({ isLight, onSelectFileRef, initialDiagramId }) => {
	const { diagram, selectDiagram, loading, code, error, retry } = useDocsArchitecture(initialDiagramId);
	const groups = Array.from(new Set(ARCHITECTURE_DIAGRAMS.map((item) => item.group)));
	return (
		<div className="flex-1 min-w-0 flex flex-col md:flex-row overflow-auto">
			<nav aria-label="Danh mục sơ đồ kiến trúc" className={`max-h-48 md:max-h-none md:w-72 shrink-0 border-r p-4 overflow-auto ${isLight ? 'border-zinc-200 bg-white' : 'border-zinc-800 bg-zinc-950'}`}>
				<h1 className="text-sm font-semibold mb-4">Kiến trúc hệ thống</h1>
				{groups.map((group) => (
					<div key={group} className="mb-5">
						<h2 className={`px-2 mb-1 text-xs font-semibold ${isLight ? 'text-zinc-600' : 'text-zinc-400'}`}>{group}</h2>
						{ARCHITECTURE_DIAGRAMS.filter((item) => item.group === group).map((item) => (
							<button
								key={item.id}
								type="button"
								aria-current={item.id === diagram.id ? 'true' : undefined}
								onClick={() => selectDiagram(item.id)}
								className={`block w-full text-left px-2 py-2 rounded-md text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 ${
									item.id === diagram.id
										? isLight ? 'bg-blue-50 text-blue-800' : 'bg-blue-950 text-blue-200'
										: isLight ? 'text-zinc-700 hover:bg-zinc-100' : 'text-zinc-300 hover:bg-zinc-900'
								}`}
							>
								{item.title}
							</button>
						))}
					</div>
				))}
			</nav>
			<section className="flex-1 min-w-0 overflow-auto p-5 md:p-8">
				<div className="max-w-6xl mx-auto">
					<p className={`mb-3 text-sm ${isLight ? 'text-zinc-600' : 'text-zinc-400'}`}>Chọn sơ đồ để đối chiếu với tài liệu kiến trúc nguồn.</p>
					<h2 className="text-xl font-semibold">{diagram.title}</h2>
					<p className={`mt-2 text-xs ${isLight ? 'text-zinc-600' : 'text-zinc-400'}`}>
						Nguồn: <button type="button" className="underline underline-offset-2" onClick={() => onSelectFileRef(`${diagram.path}#${headingSlug(diagram.heading)}`)}>{diagram.path}</button>
					</p>
					<div className="flex flex-wrap gap-3 mt-3 text-xs">
						{diagram.related.map((link) => <button key={link.path} type="button" className="text-blue-500 underline underline-offset-2" onClick={() => onSelectFileRef(link.path)}>{link.label}</button>)}
					</div>
					{loading && <p role="status" className="mt-6 text-sm">Đang tải sơ đồ...</p>}
					{error && <div role="alert" className="mt-6 text-sm"><p>{error}</p><button type="button" className="mt-2 underline" onClick={retry}>Thử lại</button></div>}
					{!loading && !error && <MermaidDiagram code={code} isLight={isLight} />}
				</div>
			</section>
		</div>
	);
};
