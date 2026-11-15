import { useState } from 'react';
import type { FormEvent } from 'react';
import { Users, UserPlus, Trash2, X } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useProjectMembers } from '@/hooks/useProjectMembers';

export function ProjectMembersSection({ projectId }: { projectId: string }) {
	const { hasPermission } = useAuth();
	const canManage = hasPermission('project_member:manage', projectId);
	const { members, projectRoles, isLoading, error, createMember, assignRole, revokeRole, removeMember, mutationError } =
		useProjectMembers(projectId, canManage);

	const [username, setUsername] = useState('');
	const [password, setPassword] = useState('');
	const [fullName, setFullName] = useState('');
	const [email, setEmail] = useState('');
	const [selectedRoleId, setSelectedRoleId] = useState('');

	const handleCreateAndAdd = async (e: FormEvent) => {
		e.preventDefault();
		if (!username.trim() || !password || !selectedRoleId) {
			return;
		}
		await createMember({
			username: username.trim(),
			password,
			full_name: fullName.trim() || null,
			email: email.trim() || null,
			role_id: selectedRoleId,
		});
		setUsername('');
		setPassword('');
		setFullName('');
		setEmail('');
		setSelectedRoleId('');
	};

	return (
		<div className="rounded-2xl bg-dark-900 border border-dark-800 overflow-hidden shadow-xl">
			<div className="p-5 border-b border-dark-800 bg-dark-950/60 flex items-center justify-between">
				<div className="flex items-center gap-2">
					<Users className="w-4 h-4 text-brand-400" />
					<div>
						<h3 className="text-sm font-bold text-slate-100">Thành viên & Phân quyền dự án</h3>
						<p className="text-xs text-slate-400">Tạo tài khoản thành viên mới cho dự án và quản lý các vai trò được gán</p>
					</div>
				</div>
			</div>

			<div className="p-5 space-y-4">
				{(error || mutationError) && (
					<div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
						{mutationError || error}
					</div>
				)}

				{canManage && (
					<form onSubmit={handleCreateAndAdd} className="grid grid-cols-1 md:grid-cols-6 gap-3 items-end">
						<div>
							<label className="block text-xs text-slate-400 mb-1">Tên đăng nhập</label>
							<input
								type="text"
								required
								value={username}
								onChange={(e) => setUsername(e.target.value)}
								placeholder="vd: analyst2"
								className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
							/>
						</div>
						<div>
							<label className="block text-xs text-slate-400 mb-1">Mật khẩu</label>
							<input
								type="password"
								required
								minLength={6}
								value={password}
								onChange={(e) => setPassword(e.target.value)}
								placeholder=">= 6 ký tự"
								className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
							/>
						</div>
						<div>
							<label className="block text-xs text-slate-400 mb-1">Họ tên</label>
							<input
								type="text"
								value={fullName}
								onChange={(e) => setFullName(e.target.value)}
								placeholder="Tùy chọn"
								className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
							/>
						</div>
						<div>
							<label className="block text-xs text-slate-400 mb-1">Email</label>
							<input
								type="email"
								value={email}
								onChange={(e) => setEmail(e.target.value)}
								placeholder="Tùy chọn"
								className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
							/>
						</div>
						<div>
							<label className="block text-xs text-slate-400 mb-1">Vai trò dự án</label>
							<select
								required
								value={selectedRoleId}
								onChange={(e) => setSelectedRoleId(e.target.value)}
								className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-xs text-slate-100"
							>
								<option value="">-- Chọn vai trò --</option>
								{projectRoles.map((r) => (
									<option key={r.role_id} value={r.role_id}>
										{r.display_name} ({r.name})
									</option>
								))}
							</select>
						</div>
						<button
							type="submit"
							className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium flex items-center justify-center gap-1.5"
						>
							<UserPlus className="w-3.5 h-3.5" />
							Tạo & thêm
						</button>
					</form>
				)}

				{isLoading ? (
					<div className="text-xs text-slate-400">Đang tải danh sách thành viên...</div>
				) : (
					<table className="w-full text-left text-xs">
						<thead className="bg-dark-950/60 text-slate-400 border-b border-dark-800">
							<tr>
								<th className="py-2.5 px-3">Người dùng</th>
								<th className="py-2.5 px-3">Vai trò trong dự án</th>
								{canManage && <th className="py-2.5 px-3 text-right">Thao tác</th>}
							</tr>
						</thead>
						<tbody className="divide-y divide-dark-800">
							{members.map((m) => {
								const heldIds = new Set(m.roles.map((r) => r.role_id));
								const availableRoles = projectRoles.filter((r) => !heldIds.has(r.role_id));
								return (
									<tr key={m.user_id}>
										<td className="py-2.5 px-3">
											<div className="text-slate-200 font-medium">{m.full_name || m.username}</div>
											<div className="text-[11px] text-slate-400 font-mono">@{m.username}</div>
										</td>
										<td className="py-2.5 px-3">
											<div className="flex flex-wrap items-center gap-1.5">
												{m.roles.map((r) => (
													<span
														key={r.role_id}
														className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-brand-500/10 border border-brand-500/30 text-brand-300 text-[11px]"
													>
														{r.display_name}
														{canManage && (
															<button
																type="button"
																title={`Gỡ vai trò ${r.display_name}`}
																aria-label={`Gỡ vai trò ${r.display_name}`}
																onClick={() => void revokeRole({ userId: m.user_id, roleId: r.role_id })}
																className="hover:text-red-400 transition"
															>
																<X className="w-3 h-3" />
															</button>
														)}
													</span>
												))}
												{canManage && availableRoles.length > 0 && (
													<select
														aria-label={`Thêm vai trò cho ${m.username}`}
														value=""
														onChange={(e) => {
															const rid = e.target.value;
															if (rid) {
																void assignRole({ userId: m.user_id, roleId: rid });
															}
														}}
														className="px-2 py-0.5 bg-dark-950 border border-dark-700 rounded text-[11px] text-slate-300"
													>
														<option value="">+ Thêm vai trò</option>
														{availableRoles.map((r) => (
															<option key={r.role_id} value={r.role_id}>
																{r.display_name}
															</option>
														))}
													</select>
												)}
											</div>
										</td>
										{canManage && (
											<td className="py-2.5 px-3 text-right">
												<button
													type="button"
													onClick={() => void removeMember(m.user_id)}
													className="inline-flex items-center gap-1 px-2 py-1 rounded bg-dark-800 border border-dark-700 text-red-400 hover:bg-red-500/10"
												>
													<Trash2 className="w-3 h-3" />
													Xóa khỏi dự án
												</button>
											</td>
										)}
									</tr>
								);
							})}
						</tbody>
					</table>
				)}
			</div>
		</div>
	);
}
