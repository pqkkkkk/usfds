import { useState } from 'react';
import type { FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ShieldAlert, LogIn } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';

export function LoginPage() {
	const { isAuthenticated, isLoading, login } = useAuth();
	const navigate = useNavigate();
	const [username, setUsername] = useState('');
	const [password, setPassword] = useState('');
	const [error, setError] = useState<string | null>(null);
	const [submitting, setSubmitting] = useState(false);

	if (!isLoading && isAuthenticated) {
		return <Navigate to="/projects" replace />;
	}

	const handleSubmit = async (e: FormEvent) => {
		e.preventDefault();
		setError(null);
		setSubmitting(true);
		const res = await login(username.trim(), password);
		setSubmitting(false);
		if (res.ok) {
			navigate('/projects', { replace: true });
		} else {
			setError(res.error || 'Tên đăng nhập hoặc mật khẩu không đúng');
		}
	};

	return (
		<div className="min-h-screen w-screen bg-dark-950 text-slate-100 flex items-center justify-center p-4">
			<div className="w-full max-w-md bg-dark-900 border border-dark-700/80 rounded-xl p-6 shadow-xl">
				<div className="flex items-center gap-3 mb-6">
					<div className="w-10 h-10 rounded-lg bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400">
						<ShieldAlert className="w-6 h-6" />
					</div>
					<div>
						<h1 className="text-lg font-bold tracking-wide font-mono text-slate-100">USFDS</h1>
						<p className="text-xs text-slate-400">Hệ thống phát hiện gian lận tài chính</p>
					</div>
				</div>

				<form onSubmit={handleSubmit} className="space-y-4">
					<div>
						<label htmlFor="login-username" className="block text-xs font-medium text-slate-300 mb-1.5">
							Tên đăng nhập
						</label>
						<input
							id="login-username"
							type="text"
							value={username}
							onChange={(e) => setUsername(e.target.value)}
							required
							autoFocus
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-brand-500"
							placeholder="Nhập tên đăng nhập"
						/>
					</div>

					<div>
						<label htmlFor="login-password" className="block text-xs font-medium text-slate-300 mb-1.5">
							Mật khẩu
						</label>
						<input
							id="login-password"
							type="password"
							value={password}
							onChange={(e) => setPassword(e.target.value)}
							required
							className="w-full px-3 py-2 bg-dark-950 border border-dark-700 rounded-lg text-sm text-slate-100 focus:outline-none focus:border-brand-500"
							placeholder="Nhập mật khẩu"
						/>
					</div>

					{error && (
						<div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
							{error}
						</div>
					)}

					<button
						type="submit"
						disabled={submitting}
						className="w-full py-2.5 px-4 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white text-sm font-medium flex items-center justify-center gap-2 transition"
					>
						<LogIn className="w-4 h-4" />
						{submitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
					</button>
				</form>
			</div>
		</div>
	);
}
