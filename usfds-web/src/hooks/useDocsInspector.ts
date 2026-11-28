import { useEffect, useRef, useState } from 'react';
import { docsDashboardApi, type FileSnippetResponse } from '@/api/docsDashboardApi';
import type { InspectorTarget } from '@/components/modules/docs_dashboard/ContextInspectorPane';

export function useDocsInspector(
	target: InspectorTarget,
	onRefreshOverview: () => Promise<void>,
	onDirtyChange?: (dirty: boolean) => void,
	onSavingChange?: (saving: boolean) => void,
	refreshVersion = 0,
) {
	const [fileData, setFileData] = useState<FileSnippetResponse | null>(null);
	const [fileLoading, setFileLoading] = useState(false);
	const [fileError, setFileError] = useState<string | null>(null);
	const [showFullFile, setShowFullFile] = useState(false);
	const [isEditingMd, setIsEditingMd] = useState(false);
	const [editBuffer, setEditBuffer] = useState('');
	const [saving, setSaving] = useState(false);
	const [actionError, setActionError] = useState<string | null>(null);
	const currentTarget = useRef(target);
	currentTarget.current = target;
	const dirty = !!fileData && editBuffer !== fileData.content;

	useEffect(() => { onDirtyChange?.(dirty); }, [dirty, onDirtyChange]);

	useEffect(() => {
		setIsEditingMd(false);
		setShowFullFile(false);
		setActionError(null);
		if (!target || target.type !== 'file') {
			setFileData(null);
			setFileError(null);
			return;
		}
		let cancelled = false;
		setFileLoading(true);
		setFileData(null);
		setFileError(null);
		const ref = target.fileRef;
		const fileRef = /#(?!L\d+(?:-L?\d+)?$)/.test(ref) ? ref.split('#', 1)[0] : ref;
		docsDashboardApi.getFile(fileRef).then((data) => {
			if (!cancelled) {
				setFileData(data);
				setEditBuffer(data.content);
			}
		}).catch((err: unknown) => {
			if (!cancelled) setFileError(err instanceof Error ? err.message : String(err));
		}).finally(() => {
			if (!cancelled) setFileLoading(false);
		});
		return () => { cancelled = true; };
	}, [target, refreshVersion]);

	const run = async (action: () => Promise<void>) => {
		const actionTarget = target;
		setSaving(true);
		onSavingChange?.(true);
		setActionError(null);
		try {
			await action();
		} catch (err) {
			if (currentTarget.current === actionTarget) setActionError(err instanceof Error ? err.message : String(err));
		} finally {
			setSaving(false);
			onSavingChange?.(false);
		}
	};

	const updateStatus = (id: string, status: string) => run(async () => {
		await docsDashboardApi.updateIssueStatus(id, status);
		await onRefreshOverview();
	});

	const saveMarkdown = () => run(async () => {
		if (!fileData) throw new Error('Không có tài liệu để lưu.');
		await docsDashboardApi.saveFile(fileData.path, editBuffer);
		if (currentTarget.current === target) {
			setFileData({ ...fileData, content: editBuffer, snippet: editBuffer });
			setIsEditingMd(false);
		}
		await onRefreshOverview();
	});

	return {
		fileData, fileLoading, fileError, showFullFile, setShowFullFile,
		isEditingMd, setIsEditingMd, editBuffer, setEditBuffer, saving, actionError,
		dirty, updateStatus, saveMarkdown,
	};
}
