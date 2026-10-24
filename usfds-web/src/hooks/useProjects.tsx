import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useState,
	type ReactNode,
} from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { projectApi } from '../api/projectApi';
import type {
	CreateProjectRequest,
	ProjectResponse,
	UpdateProjectRequest,
} from '../types/project';

export const PROJECTS_QUERY_KEY = ['projects'] as const;
const ACTIVE_PROJECT_STORAGE_KEY = 'usfds_active_project_id';
export const DEFAULT_USER_ID = '00000000-0000-0000-0000-000000000000';

interface ProjectContextValue {
	projects: ProjectResponse[];
	activeProjects: ProjectResponse[];
	currentProject: ProjectResponse | null;
	currentProjectId: string | undefined;
	isLoading: boolean;
	isMutating: boolean;
	error: string | null;
	isCreateModalOpen: boolean;
	openCreateModal: () => void;
	closeCreateModal: () => void;
	selectProject: (projectOrId: ProjectResponse | string) => void;
	refetchProjects: () => Promise<void>;
	createProject: (payload: CreateProjectRequest) => Promise<ProjectResponse>;
	updateProject: (projectId: string, payload: UpdateProjectRequest) => Promise<ProjectResponse>;
	resetProjectSchema: (projectId: string) => Promise<ProjectResponse>;
	deleteProject: (projectId: string) => Promise<boolean>;
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

export function ProjectProvider({ children }: { children: ReactNode }) {
	const queryClient = useQueryClient();
	const [selectedProjectId, setSelectedProjectId] = useState<string | null>(() => {
		if (typeof window !== 'undefined') {
			return window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY);
		}
		return null;
	});
	const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

	const {
		data: projects = [],
		isLoading,
		isFetching,
		error,
		refetch,
	} = useQuery<ProjectResponse[]>({
		queryKey: PROJECTS_QUERY_KEY,
		queryFn: async () => {
			const res = await projectApi.listProjects();
			if (!res.success) {
				throw new Error(res.error || 'Không thể tải danh sách dự án');
			}
			return res.data || [];
		},
	});

	const activeProjects = useMemo(() => {
		return projects.filter((p) => p.status === 'ACTIVE');
	}, [projects]);

	const currentProject = useMemo<ProjectResponse | null>(() => {
		if (projects.length === 0) {
			return null;
		}
		if (selectedProjectId) {
			const matched = projects.find((p) => p.project_id === selectedProjectId);
			if (matched) {
				return matched;
			}
		}
		return activeProjects[0] || projects[0] || null;
	}, [projects, activeProjects, selectedProjectId]);

	useEffect(() => {
		if (currentProject && typeof window !== 'undefined') {
			window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, currentProject.project_id);
		}
	}, [currentProject]);

	const selectProject = useCallback((projectOrId: ProjectResponse | string) => {
		const id = typeof projectOrId === 'string' ? projectOrId : projectOrId.project_id;
		setSelectedProjectId(id);
		if (typeof window !== 'undefined') {
			window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, id);
		}
	}, []);

	const createMutation = useMutation({
		mutationFn: async (payload: CreateProjectRequest) => {
			const res = await projectApi.createProject({
				...payload,
				user_id: payload.user_id || DEFAULT_USER_ID,
			});
			if (!res.success || !res.data) {
				throw new Error(res.error || 'Tạo dự án thất bại');
			}
			return res.data;
		},
		onSuccess: (created) => {
			queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
			selectProject(created.project_id);
		},
	});

	const updateMutation = useMutation({
		mutationFn: async ({
			projectId,
			payload,
		}: {
			projectId: string;
			payload: UpdateProjectRequest;
		}) => {
			const res = await projectApi.updateProject(projectId, payload);
			if (!res.success || !res.data) {
				throw new Error(res.error || 'Cập nhật dự án thất bại');
			}
			return res.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
		},
	});

	const resetSchemaMutation = useMutation({
		mutationFn: async (projectId: string) => {
			const res = await projectApi.resetProjectSchema(projectId);
			if (!res.success || !res.data) {
				throw new Error(res.error || 'Đặt lại RAW schema thất bại');
			}
			return res.data;
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
		},
	});

	const deleteMutation = useMutation({
		mutationFn: async (projectId: string) => {
			const res = await projectApi.deleteProject(projectId);
			if (!res.success) {
				throw new Error(res.error || 'Xóa dự án thất bại');
			}
			return projectId;
		},
		onSuccess: (deletedId) => {
			if (selectedProjectId === deletedId) {
				const remaining = projects.filter((p) => p.project_id !== deletedId);
				const next = remaining.find((p) => p.status === 'ACTIVE') || remaining[0] || null;
				setSelectedProjectId(next ? next.project_id : null);
				if (typeof window !== 'undefined') {
					if (next) {
						window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, next.project_id);
					} else {
						window.localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
					}
				}
			}
			queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
			queryClient.invalidateQueries({ queryKey: ['datasets'] });
		},
	});

	const refetchProjects = useCallback(async () => {
		await refetch();
	}, [refetch]);

	const createProject = useCallback(
		async (payload: CreateProjectRequest) => {
			return createMutation.mutateAsync(payload);
		},
		[createMutation]
	);

	const updateProject = useCallback(
		async (projectId: string, payload: UpdateProjectRequest) => {
			return updateMutation.mutateAsync({ projectId, payload });
		},
		[updateMutation]
	);

	const resetProjectSchema = useCallback(
		async (projectId: string) => {
			return resetSchemaMutation.mutateAsync(projectId);
		},
		[resetSchemaMutation]
	);

	const deleteProject = useCallback(
		async (projectId: string) => {
			await deleteMutation.mutateAsync(projectId);
			return true;
		},
		[deleteMutation]
	);

	const openCreateModal = useCallback(() => {
		setIsCreateModalOpen(true);
	}, []);

	const closeCreateModal = useCallback(() => {
		setIsCreateModalOpen(false);
	}, []);

	const isMutating =
		createMutation.isPending ||
		updateMutation.isPending ||
		resetSchemaMutation.isPending ||
		deleteMutation.isPending;

	const value = useMemo<ProjectContextValue>(
		() => ({
			projects,
			activeProjects,
			currentProject,
			currentProjectId: currentProject?.project_id,
			isLoading: isLoading || isFetching,
			isMutating,
			error: error ? (error as Error).message : null,
			isCreateModalOpen,
			openCreateModal,
			closeCreateModal,
			selectProject,
			refetchProjects,
			createProject,
			updateProject,
			resetProjectSchema,
			deleteProject,
		}),
		[
			projects,
			activeProjects,
			currentProject,
			isLoading,
			isFetching,
			isMutating,
			error,
			isCreateModalOpen,
			openCreateModal,
			closeCreateModal,
			selectProject,
			refetchProjects,
			createProject,
			updateProject,
			resetProjectSchema,
			deleteProject,
		]
	);

	return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectContextValue {
	const context = useContext(ProjectContext);
	if (!context) {
		throw new Error('useProject must be used within a ProjectProvider');
	}
	return context;
}
