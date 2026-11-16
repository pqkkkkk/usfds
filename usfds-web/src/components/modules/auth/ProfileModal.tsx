import { useState } from 'react';
import type { FormEvent } from 'react';
import { X, User as UserIcon, KeyRound } from 'lucide-react';
import { authApi } from '@/api/authApi';
import { useAuth } from '@/hooks/useAuth';

interface ProfileModalProps {
	isOpen: boolean;
	onClose: () => void;
}

export function ProfileModal({ isOpen, onClose }: ProfileModalProps) {
	const { user, refreshMe } = useAuth();
	const [fullName, setFullName] = useState(user?.full_name || '');
	const [email, setEmail] = useState(user?.email || '');
	const [currentPassword, setCurrentPassword] = useState('');
	const [newPassword, setNewPassword] = useState('');
	const [message, setMessage] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [saving, setSaving] = useState(false);

	if (!isOpen || !user) {
		return null;
	}

	const handleSaveProfile = async (e: FormEvent) => {
		e.preventDefault();
		setError(null);
		setMessage(null);
		setSaving(true);
		try {
			await authApi.updateProfile({
				full_name: fullName.trim() || null,
				email: email.trim() || null,
			});
			await refreshMe();
			setMessage('Đã cập nhật thông tin cá nhân');
		} catch (err: any) {
			setError(err?.message || 'Không thể cập nhật thông tin');
		} finally {
			setSaving(false);
		}
	};

	const handleChangePassword = async (e: FormEvent) => {
		e.preventDefault();
		setError(null);
		setMessage(null);
		setSaving(true);
		try {
			await authApi.changePassword(currentPassword, newPassword);
			setCurrentPassword('');
			setNewPassword('');
			setMessage('Đã đổi mật khẩu thành công');
		} catch (err: any) {
			setError(err?.message || 'Không thể đổi mật khẩu');
		} finally {
			setSaving(false);
		}
	};

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
			<div className="w-full max-w-lg bg-dark-900 border border-dark-700 rounded-xl p-5 shadow-2xl space-y-5">
				<div className="flex items-center justify-between border-b border-dark-700/80 pb-3">
					<div className="flex items-center gap-2 text-slate-100 font-semibold text-sm">
						<UserIcon className="w-4 h-4 text-brand-400" />
						Hồ sơ cá nhân ({user.username})
					</div>
					<button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-200">
						<X className="w-4 h-4" />
					</button>
				</div>

				{message && (
					<div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-400">
						{message}
					</div>
				)}
				{error && (
					<div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
						{error}
					</div>
				)}

				<form onSubmit={handleSaveProfile} className="space-y-3">
					<div>
						<label className="block text-xs text-slate-400 mb-1">Họ và tên</label>
						<input
							type="text"
							value={fullName}
							onChange={(e) => setFullName(e.target.value)}
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-sm text-slate-100"
						/>
					</div>
					<div>
						<label className="block text-xs text-slate-400 mb-1">Email</label>
						<input
							type="email"
							value={email}
							onChange={(e) => setEmail(e.target.value)}
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-sm text-slate-100"
						/>
					</div>
					<button
						type="submit"
						disabled={saving}
						className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium"
					>
						Lưu hồ sơ
					</button>
				</form>

				<form onSubmit={handleChangePassword} className="space-y-3 border-t border-dark-700/80 pt-4">
					<div className="flex items-center gap-1.5 text-xs font-medium text-slate-300">
						<KeyRound className="w-3.5 h-3.5 text-brand-400" />
						Đổi mật khẩu
					</div>
					<div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
						<input
							type="password"
							value={currentPassword}
							onChange={(e) => setCurrentPassword(e.target.value)}
							placeholder="Mật khẩu hiện tại"
							required
							className="px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-sm text-slate-100"
						/>
						<input
							type="password"
							value={newPassword}
							onChange={(e) => setNewPassword(e.target.value)}
							placeholder="Mật khẩu mới (>= 6 ký tự)"
							required
							minLength={6}
							className="px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-sm text-slate-100"
						/>
					</div>
					<button
						type="submit"
						disabled={saving}
						className="px-4 py-2 rounded-lg bg-dark-800 hover:bg-dark-700 border border-dark-600 text-slate-200 text-xs font-medium"
					>
						Cập nhật mật khẩu
					</button>
				</form>
			</div>
		</div>
	);
}
