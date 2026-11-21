import { useEffect, useRef, useState } from 'react';
import { ChevronDown, LogOut, Shield, User as UserIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { useActorContext } from '@/hooks/useActorContext';
import { ProfileModal } from '../modules/auth/ProfileModal';

export const UserAccountMenu = () => {
	const [userMenuOpen, setUserMenuOpen] = useState(false);
	const [isProfileOpen, setIsProfileOpen] = useState(false);
	const userMenuRef = useRef<HTMLDivElement>(null);
	const { user, authMode, logout } = useAuth();
	const { features } = useActorContext();
	const navigate = useNavigate();

	const canAccessAdmin = features.adminUsers.allowed;
	const displayName = user?.full_name || user?.username || 'Người dùng';
	const initials = displayName.slice(0, 2).toUpperCase();
	const roleSubtitle = user?.is_system_admin
		? 'Quản trị hệ thống'
		: user?.system_role_keys?.join(', ') || 'Thành viên';

	useEffect(() => {
		if (!userMenuOpen) {
			return;
		}
		const handleClickOutside = (event: MouseEvent) => {
			if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
				setUserMenuOpen(false);
			}
		};
		const handleEscape = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				setUserMenuOpen(false);
			}
		};
		document.addEventListener('mousedown', handleClickOutside);
		document.addEventListener('keydown', handleEscape);
		return () => {
			document.removeEventListener('mousedown', handleClickOutside);
			document.removeEventListener('keydown', handleEscape);
		};
	}, [userMenuOpen]);

	return (
		<>
			<div className="relative pl-2 border-l border-dark-700/80" ref={userMenuRef}>
				<button
					type="button"
					onClick={() => setUserMenuOpen((prev) => !prev)}
					className="flex items-center gap-2 hover:opacity-90 transition"
					aria-label="Tài khoản người dùng"
					aria-expanded={userMenuOpen}
				>
					<div className="w-7 h-7 rounded-full bg-gradient-to-tr from-brand-600 to-emerald-500 flex items-center justify-center text-xs font-bold text-white shadow-sm ring-1 ring-white/10">
						{initials}
					</div>
					<div className="hidden xl:flex flex-col text-left">
						<span className="text-xs font-medium text-slate-200 leading-tight">{displayName}</span>
						<span className="text-[10px] text-slate-400">{roleSubtitle}</span>
					</div>
					<ChevronDown className="w-3.5 h-3.5 text-slate-400" />
				</button>

				{userMenuOpen && (
					<div className="absolute right-0 mt-2 w-52 bg-dark-900 border border-dark-700 rounded-lg shadow-xl py-1 z-50">
						<button
							type="button"
							onClick={() => {
								setUserMenuOpen(false);
								setIsProfileOpen(true);
							}}
							className="w-full px-3 py-2 text-left text-xs text-slate-200 hover:bg-dark-800 flex items-center gap-2"
						>
							<UserIcon className="w-3.5 h-3.5 text-slate-400" />
							Hồ sơ cá nhân
						</button>
						{canAccessAdmin && (
							<button
								type="button"
								onClick={() => {
									setUserMenuOpen(false);
									navigate('/admin');
								}}
								className="w-full px-3 py-2 text-left text-xs text-slate-200 hover:bg-dark-800 flex items-center gap-2"
							>
								<Shield className="w-3.5 h-3.5 text-brand-400" />
								Quản trị hệ thống
							</button>
						)}
						{authMode === 'required' && (
							<button
								type="button"
								onClick={async () => {
									setUserMenuOpen(false);
									await logout();
									navigate('/login', { replace: true });
								}}
								className="w-full px-3 py-2 text-left text-xs text-red-400 hover:bg-dark-800 flex items-center gap-2 border-t border-dark-800"
							>
								<LogOut className="w-3.5 h-3.5" />
								Đăng xuất
							</button>
						)}
					</div>
				)}
			</div>
			<ProfileModal isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
		</>
	);
};
