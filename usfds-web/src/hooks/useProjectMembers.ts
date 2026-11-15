import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { projectMemberApi } from '@/api/projectMemberApi';
import { userAdminApi } from '@/api/userAdminApi';

export const PROJECT_MEMBERS_QUERY_KEY = (projectId: string) => ['project-members', projectId] as const;

export function useProjectMembers(projectId: string | undefined, canManageMembers: boolean) {
	const queryClient = useQueryClient();

	const membersQuery = useQuery({
		queryKey: projectId ? PROJECT_MEMBERS_QUERY_KEY(projectId) : ['project-members', 'none'],
		enabled: Boolean(projectId),
		queryFn: async () => {
			const res = await projectMemberApi.listMembers(projectId!);
			if (!res.success || !res.data) {
				throw new Error(res.error || 'Không thể tải danh sách thành viên');
			}
			return res.data;
		},
	});

	const rolesQuery = useQuery({
		queryKey: ['rbac-roles', 'PROJECT'],
		enabled: canManageMembers,
		queryFn: async () => {
			const res = await userAdminApi.listRoles('PROJECT');
			if (!res.success || !res.data) {
				throw new Error(res.error || 'Không thể tải danh sách vai trò');
			}
			return res.data;
		},
	});

	const invalidate = () => {
		if (projectId) {
			void queryClient.invalidateQueries({ queryKey: PROJECT_MEMBERS_QUERY_KEY(projectId) });
		}
	};

	const createMemberMutation = useMutation({
		mutationFn: async (payload: {
			username: string;
			password: string;
			full_name?: string | null;
			email?: string | null;
			role_id: string;
		}) => {
			const res = await projectMemberApi.createMember(projectId!, payload);
			if (!res.success) {
				throw new Error(res.error || 'Không thể tạo người dùng và thêm vào dự án');
			}
			return res.data;
		},
		onSuccess: invalidate,
	});

	const assignRoleMutation = useMutation({
		mutationFn: async ({ userId, roleId }: { userId: string; roleId: string }) => {
			const res = await projectMemberApi.assignRole(projectId!, userId, roleId);
			if (!res.success) {
				throw new Error(res.error || 'Không thể gán thêm vai trò');
			}
			return res.data;
		},
		onSuccess: invalidate,
	});

	const revokeRoleMutation = useMutation({
		mutationFn: async ({ userId, roleId }: { userId: string; roleId: string }) => {
			const res = await projectMemberApi.revokeRole(projectId!, userId, roleId);
			if (!res.success) {
				throw new Error(res.error || 'Không thể gỡ vai trò thành viên');
			}
			return res.data;
		},
		onSuccess: invalidate,
	});

	const removeMemberMutation = useMutation({
		mutationFn: async (userId: string) => {
			const res = await projectMemberApi.removeMember(projectId!, userId);
			if (!res.success) {
				throw new Error(res.error || 'Không thể xóa thành viên khỏi dự án');
			}
			return res.data;
		},
		onSuccess: invalidate,
	});

	return {
		members: membersQuery.data ?? [],
		projectRoles: rolesQuery.data ?? [],
		isLoading: membersQuery.isLoading,
		error: membersQuery.error instanceof Error ? membersQuery.error.message : null,
		createMember: createMemberMutation.mutateAsync,
		assignRole: assignRoleMutation.mutateAsync,
		revokeRole: revokeRoleMutation.mutateAsync,
		removeMember: removeMemberMutation.mutateAsync,
		mutationError:
			(createMemberMutation.error instanceof Error && createMemberMutation.error.message) ||
			(assignRoleMutation.error instanceof Error && assignRoleMutation.error.message) ||
			(revokeRoleMutation.error instanceof Error && revokeRoleMutation.error.message) ||
			(removeMemberMutation.error instanceof Error && removeMemberMutation.error.message) ||
			null,
	};
}
