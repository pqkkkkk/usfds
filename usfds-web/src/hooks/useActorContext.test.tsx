import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { AuthProvider } from '@/hooks/useAuth';
import { useActorContext } from '@/hooks/useActorContext';
import { API, server } from '@/test/server';

const PROJECT_1_ID = '11111111-1111-1111-1111-111111111111';

describe('useActorContext', () => {
	it('test_use_actor_context_resolves_project_features', async () => {
		server.use(
			http.get(`${API}/v1/auth/mode`, () =>
				HttpResponse.json({ success: true, data: { auth_mode: 'local_auto' } })
			),
			http.get(`${API}/v1/auth/me`, () =>
				HttpResponse.json({
					success: true,
					data: {
						user_id: '22222222-2222-2222-2222-222222222222',
						username: 'analyst1',
						email: 'analyst1@usfds.local',
						full_name: 'Analyst One',
						status: 'ACTIVE',
						last_login_at: null,
						is_system_admin: false,
						system_role_keys: ['system_member'],
						system_permissions: {
							'project:create': ['SYSTEM'],
						},
						projects: [
							{
								project_id: PROJECT_1_ID,
								role_keys: ['fraud_analyst'],
								permissions: {
									'project:read': ['PROJECT'],
									'case:read': ['PROJECT'],
									'case:manual_review': ['PROJECT'],
									'rule:read': ['PROJECT'],
								},
							},
						],
					},
				})
			)
		);

		const queryClient = new QueryClient({
			defaultOptions: { queries: { retry: false } },
		});
		function Wrapper({ children }: { children: ReactNode }) {
			return (
				<QueryClientProvider client={queryClient}>
					<AuthProvider>{children}</AuthProvider>
				</QueryClientProvider>
			);
		}

		const { result } = renderHook(() => useActorContext(PROJECT_1_ID), { wrapper: Wrapper });

		await waitFor(() => {
			expect(result.current.loading).toBe(false);
		});

		expect(result.current.actor?.username).toBe('analyst1');
		expect(result.current.features.investigation.allowed).toBe(true);
		expect(result.current.features.investigation.projectIds).toEqual([PROJECT_1_ID]);
		expect(result.current.features.modelManagement.allowed).toBe(false);
		expect(result.current.features.createRule.allowed).toBe(false);
		expect(result.current.features.ruleManagement.allowed).toBe(true);
		expect(result.current.features.adminUsers.allowed).toBe(false);
		expect(result.current.features.createProject.allowed).toBe(true);
	});
});
