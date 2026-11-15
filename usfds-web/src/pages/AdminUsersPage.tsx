import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Shield, ArrowLeft, Plus, Power, KeyRound } from 'lucide-react';
import { userAdminApi } from '@/api/userAdminApi';
import { useAuth } from '@/hooks/useAuth';
import type { AdminUserResponse, PermissionDto, RoleDto } from '@/types/auth';

export function AdminUsersPage() {
	const navigate = useNavigate();
	const { user, hasPermission } = useAuth();
	const [tab, setTab] = useState<'users' | 'roles'>('users');
	const [users, setUsers] = useState<AdminUserResponse[]>([]);
	const [roles, setRoles] = useState<RoleDto[]>([]);
	const [permissions, setPermissions] = useState<PermissionDto[]>([]);
	const [error, setError] = useState<string | null>(null);
	const [loading, setLoading] = useState(true);

	const [newUsername, setNewUsername] = useState('');
	const [newPassword, setNewPassword] = useState('');
	const [newFullName, setNewFullName] = useState('');
	const [newEmail, setNewEmail] = useState('');
	const [newRoleKey, setNewRoleKey] = useState('system_member');

	const canManageUsers = Boolean(user?.is_system_admin || hasPermission('user:read'));

	const loadData = async () => {
		setLoading(true);
		setError(null);
		const [uRes, rRes, pRes] = await Promise.all([
			userAdminApi.listUsers(),
			userAdminApi.listRoles(),
			userAdminApi.listPermissions(),
		]);
		if (uRes.success && uRes.data) {
			setUsers(uRes.data);
		} else {
			setError(uRes.error || 'Không thể tải danh sách người dùng');
		}
		if (rRes.success && rRes.data) {
			setRoles(rRes.data);
		}
		if (pRes.success && pRes.data) {
			setPermissions(pRes.data);
		}
		setLoading(false);
	};

	useEffect(() => {
		if (canManageUsers) {
			void loadData();
		} else {
			setLoading(false);
		}
	}, [canManageUsers]);

	if (!canManageUsers) {
		return (
			<div className="min-h-screen bg-dark-950 text-slate-100 flex flex-col items-center justify-center gap-4 p-6">
				<p className="text-sm text-red-400">Bạn không có quyền truy cập trang quản trị người dùng.</p>
				<button
					type="button"
					onClick={() => navigate('/projects')}
					className="px-4 py-2 rounded-lg bg-dark-800 border border-dark-700 text-xs text-slate-200"
				>
					Quay lại dự án
				</button>
			</div>
		);
	}

	const handleCreateUser = async (e: FormEvent) => {
		e.preventDefault();
		setError(null);
		const res = await userAdminApi.createUser({
			username: newUsername.trim(),
			password: newPassword,
			full_name: newFullName.trim() || null,
			email: newEmail.trim() || null,
			system_roles: [newRoleKey],
		});
		if (res.success) {
			setNewUsername('');
			setNewPassword('');
			setNewFullName('');
			setNewEmail('');
			await loadData();
		} else {
			setError(res.error || 'Không thể tạo người dùng');
		}
	};

	const handleToggleStatus = async (u: AdminUserResponse) => {
		const next = u.status === 'ACTIVE' ? 'DISABLED' : 'ACTIVE';
		const res = await userAdminApi.setUserStatus(u.user_id, next);
		if (res.success) {
			await loadData();
		} else {
			setError(res.error || 'Không thể đổi trạng thái');
		}
	};

	const handleResetPassword = async (userId: string) => {
		const res = await userAdminApi.resetPassword(userId, 'ResetPass123!');
		if (!res.success) {
			setError(res.error || 'Không thể đặt lại mật khẩu');
		}
	};

	return (
		<div className="min-h-screen bg-dark-950 text-slate-100 p-6">
			<div className="max-w-6xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div className="flex items-center gap-3">
						<button
							type="button"
							onClick={() => navigate('/projects')}
							className="p-2 rounded-lg bg-dark-900 border border-dark-700 text-slate-300 hover:text-white"
						>
							<ArrowLeft className="w-4 h-4" />
						</button>
						<div>
							<h1 className="text-lg font-bold text-slate-100">Quản trị người dùng & Phân quyền</h1>
							<p className="text-xs text-slate-400">Quản lý tài khoản hệ thống, vai trò và quyền hạn RBAC</p>
						</div>
					</div>
					<div className="flex gap-2">
						<button
							type="button"
							onClick={() => setTab('users')}
							className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 ${
								tab === 'users'
									? 'bg-brand-600 text-white'
									: 'bg-dark-900 border border-dark-700 text-slate-300'
							}`}
						>
							<Users className="w-3.5 h-3.5" />
							Người dùng ({users.length})
						</button>
						<button
							type="button"
							onClick={() => setTab('roles')}
							className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 ${
								tab === 'roles'
									? 'bg-brand-600 text-white'
									: 'bg-dark-900 border border-dark-700 text-slate-300'
							}`}
						>
							<Shield className="w-3.5 h-3.5" />
							Vai trò & Quyền ({roles.length})
						</button>
					</div>
				</div>

				{error && (
					<div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
						{error}
					</div>
				)}

				{loading ? (
					<div className="text-xs text-slate-400">Đang tải dữ liệu...</div>
				) : tab === 'users' ? (
					<div className="space-y-5">
						<form
							onSubmit={handleCreateUser}
							className="bg-dark-900 border border-dark-700/80 rounded-xl p-4 grid grid-cols-1 md:grid-cols-6 gap-3 items-end"
						>
							<div>
								<label className="block text-xs text-slate-400 mb-1">Tên đăng nhập</label>
								<input
									type="text"
									required
									value={newUsername}
									onChange={(e) => setNewUsername(e.target.value)}
									className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
								/>
							</div>
							<div>
								<label className="block text-xs text-slate-400 mb-1">Mật khẩu</label>
								<input
									type="password"
									required
									minLength={6}
									value={newPassword}
									onChange={(e) => setNewPassword(e.target.value)}
									className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
								/>
							</div>
							<div>
								<label className="block text-xs text-slate-400 mb-1">Họ tên</label>
								<input
									type="text"
									value={newFullName}
									onChange={(e) => setNewFullName(e.target.value)}
									className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
								/>
							</div>
							<div>
								<label className="block text-xs text-slate-400 mb-1">Email</label>
								<input
									type="email"
									value={newEmail}
									onChange={(e) => setNewEmail(e.target.value)}
									className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
								/>
							</div>
							<div>
								<label className="block text-xs text-slate-400 mb-1">Vai trò hệ thống</label>
								<select
									value={newRoleKey}
									onChange={(e) => setNewRoleKey(e.target.value)}
									className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
								>
									<option value="system_member">system_member</option>
									<option value="system_admin">system_admin</option>
								</select>
							</div>
							<button
								type="submit"
								className="px-3 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium flex items-center justify-center gap-1.5"
							>
								<Plus className="w-3.5 h-3.5" />
								Tạo người dùng
							</button>
						</form>

						<div className="bg-dark-900 border border-dark-700/80 rounded-xl overflow-hidden">
							<table className="w-full text-left text-xs">
								<thead className="bg-dark-800/70 text-slate-400 border-b border-dark-700">
									<tr>
										<th className="px-4 py-3">Tên đăng nhập</th>
										<th className="px-4 py-3">Họ tên</th>
										<th className="px-4 py-3">Email</th>
										<th className="px-4 py-3">Trạng thái</th>
										<th className="px-4 py-3 text-right">Thao tác</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-dark-800">
									{users.map((u) => (
										<tr key={u.user_id} className="hover:bg-dark-800/40">
											<td className="px-4 py-3 font-medium text-slate-100">{u.username}</td>
											<td className="px-4 py-3 text-slate-300">{u.full_name || '—'}</td>
											<td className="px-4 py-3 text-slate-400">{u.email || '—'}</td>
											<td className="px-4 py-3">
												<span
													className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${
														u.status === 'ACTIVE'
															? 'bg-emerald-500/15 text-emerald-400'
															: 'bg-red-500/15 text-red-400'
													}`}
												>
													{u.status === 'ACTIVE' ? 'Hoạt động' : 'Đã khóa'}
												</span>
											</td>
											<td className="px-4 py-3 text-right space-x-2">
												<button
													type="button"
													onClick={() => handleToggleStatus(u)}
													className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-dark-800 border border-dark-700 text-slate-300 hover:text-white"
												>
													<Power className="w-3 h-3" />
													{u.status === 'ACTIVE' ? 'Khóa' : 'Mở khóa'}
												</button>
												<button
													type="button"
													onClick={() => handleResetPassword(u.user_id)}
													className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-dark-800 border border-dark-700 text-slate-300 hover:text-white"
												>
													<KeyRound className="w-3 h-3" />
													Đặt lại MK
												</button>
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					</div>
				) : (
					<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
						{roles.map((r) => (
							<div key={r.role_id} className="bg-dark-900 border border-dark-700/80 rounded-xl p-4 space-y-2">
								<div className="flex items-center justify-between">
									<div>
										<h3 className="text-sm font-semibold text-slate-100">{r.display_name}</h3>
										<p className="text-xs font-mono text-slate-400">{r.name}</p>
									</div>
									<span className="px-2 py-0.5 rounded bg-brand-500/10 border border-brand-500/30 text-[11px] text-brand-400">
										{r.scope}
									</span>
								</div>
								<p className="text-xs text-slate-400">{r.description || 'Không có mô tả'}</p>
								<div className="flex flex-wrap gap-1.5 pt-2">
									{r.grants.map((g) => (
										<span
											key={`${r.role_id}-${g.permission_code}-${g.grant_scope}`}
											className="px-2 py-0.5 rounded bg-dark-950 border border-dark-700 text-[11px] font-mono text-slate-300"
										>
											{g.permission_code}:{g.grant_scope}
										</span>
									))}
									{r.grants.length === 0 && (
										<span className="text-[11px] text-slate-500">Chưa gán quyền ({permissions.length} quyền khả dụng)</span>
									)}
								</div>
							</div>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
