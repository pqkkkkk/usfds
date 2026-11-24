import { describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import { Sidebar } from '@/components/layout/Sidebar';
import { FeatureManagementModule } from './FeatureManagementModule';
import type { FeatureResponse, FeatureSetResponse } from '@/types/feature';

const PROJECT_ID = '11111111-1111-1111-1111-111111111111';

const MOCK_FEATURES: FeatureResponse[] = [
	{
		feature_id: 'f-001',
		project_id: null,
		user_id: null,
		is_builtin: true,
		feature_key: 'tx_freq_last_1h',
		display_name: 'Tần suất giao dịch 1 giờ qua',
		description: 'Đếm số giao dịch trong 1h của user_id',
		megafamily: 'ORDERS',
		compute_kind: 'VELOCITY',
		output_type: 'NUMERIC',
		is_stateful: false,
		requires_label: false,
		config_json: { entity_key: 'user_id', agg_fn: 'COUNT', window: '1h' },
		source_code: null,
		compiled_sql_preview: 'CAST(COUNT(*) OVER (PARTITION BY "user_id" ORDER BY _ts ASC RANGE BETWEEN INTERVAL \'1 HOUR\' PRECEDING AND CURRENT ROW) AS DOUBLE) AS "tx_freq_last_1h"',
		required_inputs: ['user_id', 'timestamp'],
		depends_on_feature_ids: [],
		status: 'ACTIVE',
		created_at: '2026-11-24T00:00:00Z',
		updated_at: '2026-11-24T00:00:00Z',
	},
	{
		feature_id: 'f-002',
		project_id: null,
		user_id: null,
		is_builtin: true,
		feature_key: 'is_free_email',
		display_name: 'Email nhà cung cấp miễn phí',
		description: 'Kiểm tra domain email miễn phí',
		megafamily: 'IDENTITY',
		compute_kind: 'PYTHON_CODE',
		output_type: 'BOOLEAN',
		is_stateful: false,
		requires_label: false,
		config_json: { params: { col: 'email' } },
		source_code: 'def compute(df, params):\n\treturn df["email"].str.contains("gmail.com")\n',
		compiled_sql_preview: null,
		required_inputs: ['email'],
		depends_on_feature_ids: [],
		status: 'ACTIVE',
		created_at: '2026-11-24T00:00:00Z',
		updated_at: '2026-11-24T00:00:00Z',
	},
];

const MOCK_SETS: FeatureSetResponse[] = [
	{
		feature_set_id: 'fs-001',
		project_id: null,
		user_id: null,
		is_builtin: true,
		set_key: 'pkg_ccfd_standard',
		name: 'Thẻ tín dụng chuẩn (CCFD Standard)',
		description: 'Bộ đặc trưng CCFD chuẩn',
		domain_tag: 'CCFD',
		default_config: {},
		feature_ids: ['f-001'],
		created_at: '2026-11-24T00:00:00Z',
		updated_at: '2026-11-24T00:00:00Z',
	},
];

function mockActorPermissions(perms: Record<string, string[]>) {
	server.use(
		http.get(`${API}/v1/projects`, () =>
			HttpResponse.json({
				success: true,
				statusCode: 200,
				data: {
					items: [
						{
							project_id: PROJECT_ID,
							user_id: 'u-ds-1',
							project_name: 'Fraud Demo',
							status: 'ACTIVE',
							is_schema_locked: true,
							created_at: '2026-11-24T00:00:00Z',
							updated_at: '2026-11-24T00:00:00Z',
						},
					],
					nextCursor: null,
				},
			})
		),
		http.get(`${API}/v1/auth/me`, () =>
			HttpResponse.json({
				success: true,
				statusCode: 200,
				data: {
					user_id: 'u-ds-1',
					username: 'ds1',
					full_name: 'DS One',
					is_system_admin: false,
					system_role_keys: ['system_member'],
					system_permissions: {},
					projects: [
						{
							project_id: PROJECT_ID,
							role_keys: ['data_scientist'],
							permissions: perms,
						},
					],
				},
			})
		)
	);
}

describe('FeatureManagement Module (M3)', () => {
	it('test_feature_management_module_sidebar_catalog_builder_and_sets', async () => {
		const featuresState = [...MOCK_FEATURES];
		const setsState = [...MOCK_SETS];
		const createdPayloads: Array<Record<string, unknown>> = [];

		mockActorPermissions({
			'dataset:read': ['PROJECT'],
			'feature:read': ['PROJECT'],
			'feature:create': ['OWN'],
			'feature:update': ['OWN'],
			'feature:delete': ['OWN'],
		});

		const extraFeaturePage2: FeatureResponse = {
			feature_id: 'f-003',
			project_id: null,
			user_id: null,
			is_builtin: true,
			feature_key: 'geo_distance_km',
			display_name: 'Khoảng cách địa lý',
			description: 'Khoảng cách Haversine giữa chủ thẻ và điểm bán',
			megafamily: 'LOCATIONS',
			compute_kind: 'PYTHON_CODE',
			output_type: 'NUMERIC',
			is_stateful: false,
			requires_label: false,
			config_json: {},
			source_code: 'def compute(df, params):\n\treturn df["lat"]\n',
			required_inputs: ['lat', 'long', 'merch_lat', 'merch_long'],
			depends_on_feature_ids: [],
			status: 'ACTIVE',
			created_at: '2026-11-24T00:00:00Z',
			updated_at: '2026-11-24T00:00:00Z',
		};
		const observedFeatureCursors: Array<string | null> = [];

		server.use(
			http.get(`${API}/v1/datasets`, () =>
				HttpResponse.json({ success: true, statusCode: 200, data: { items: [], nextCursor: null } })
			),
			http.get(`${API}/v1/features`, ({ request }) => {
				const url = new URL(request.url);
				const cursor = url.searchParams.get('cursor');
				observedFeatureCursors.push(cursor);
				if (cursor === 'cursor-p2') {
					return HttpResponse.json({
						success: true,
						statusCode: 200,
						data: { items: [extraFeaturePage2], nextCursor: null },
					});
				}
				return HttpResponse.json({
					success: true,
					statusCode: 200,
					data: { items: featuresState, nextCursor: 'cursor-p2' },
				});
			}),
			http.get(`${API}/v1/features/compatibility`, () =>
				HttpResponse.json({
					success: true,
					statusCode: 200,
					data: {
						available_columns: ['event_id', 'timestamp', 'amount', 'user_id', 'label'],
						available_count: 1,
						unavailable_count: 1,
						items: [
							{
								feature_id: 'f-001',
								feature_key: 'tx_freq_last_1h',
								display_name: 'Tần suất giao dịch 1 giờ qua',
								megafamily: 'ORDERS',
								compute_kind: 'VELOCITY',
								output_type: 'NUMERIC',
								is_builtin: true,
								requires_label: false,
								status: 'AVAILABLE',
								missing_inputs: [],
								missing_dependencies: [],
								missing_packages: [],
							},
							{
								feature_id: 'f-002',
								feature_key: 'is_free_email',
								display_name: 'Email nhà cung cấp miễn phí',
								megafamily: 'IDENTITY',
								compute_kind: 'PYTHON_CODE',
								output_type: 'BOOLEAN',
								is_builtin: true,
								requires_label: false,
								status: 'MISSING_INPUTS',
								missing_inputs: ['email'],
								missing_dependencies: [],
								missing_packages: [],
							},
						],
					},
				})
			),
			http.get(`${API}/v1/feature-sets`, () =>
				HttpResponse.json({
					success: true,
					statusCode: 200,
					data: { items: setsState, nextCursor: null },
				})
			),
			http.post(`${API}/v1/features`, async ({ request }) => {
				const body = (await request.json()) as Record<string, unknown>;
				createdPayloads.push(body);
				const created: FeatureResponse = {
					feature_id: `f-new-${featuresState.length + 1}`,
					project_id: PROJECT_ID,
					user_id: 'u-ds-1',
					is_builtin: false,
					feature_key: String(body.feature_key),
					display_name: String(body.display_name),
					megafamily: (body.megafamily as FeatureResponse['megafamily']) || 'MONETARY',
					compute_kind: (body.compute_kind as FeatureResponse['compute_kind']) || 'EXPRESSION',
					output_type: (body.output_type as FeatureResponse['output_type']) || 'NUMERIC',
					is_stateful: Boolean(body.is_stateful),
					requires_label: Boolean(body.requires_label),
					config_json: (body.config_json as Record<string, unknown>) || {},
					source_code: (body.source_code as string | null) || null,
					required_inputs: (body.required_inputs as string[]) || [],
					depends_on_feature_ids: [],
					status: 'ACTIVE',
					created_at: '2026-11-24T00:00:00Z',
					updated_at: '2026-11-24T00:00:00Z',
				};
				featuresState.push(created);
				return HttpResponse.json({ success: true, statusCode: 201, data: created }, { status: 201 });
			}),
			http.post(`${API}/v1/feature-sets`, async ({ request }) => {
				const body = (await request.json()) as Record<string, unknown>;
				const createdSet: FeatureSetResponse = {
					feature_set_id: 'fs-custom-1',
					project_id: PROJECT_ID,
					user_id: 'u-ds-1',
					is_builtin: false,
					set_key: String(body.set_key),
					name: String(body.name),
					domain_tag: String(body.domain_tag || 'CUSTOM'),
					default_config: {},
					feature_ids: (body.feature_ids as string[]) || [],
					created_at: '2026-11-24T00:00:00Z',
					updated_at: '2026-11-24T00:00:00Z',
				};
				setsState.push(createdSet);
				return HttpResponse.json({ success: true, statusCode: 201, data: createdSet }, { status: 201 });
			})
		);

		// 1. Sidebar displays Quản lý đặc trưng
		renderWithProviders(
			<>
				<Sidebar
					activeModule="feature-management"
					onSelectModule={vi.fn()}
					collapsed={false}
					onToggleCollapse={vi.fn()}
				/>
				<FeatureManagementModule />
			</>
		);

		const featureNavAndTitles = await screen.findAllByText('Quản lý đặc trưng');
		expect(featureNavAndTitles.length).toBeGreaterThanOrEqual(2);
		expect(await screen.findByText('tx_freq_last_1h')).toBeInTheDocument();
		expect(await screen.findByText('is_free_email')).toBeInTheDocument();

		// Compatibility badges displayed
		expect(await screen.findByText('Khả dụng')).toBeInTheDocument();
		expect(await screen.findByText(/Thiếu cột/i)).toBeInTheDocument();

		// Load next cursor page via "Tải thêm" button
		const loadMoreBtn = await screen.findByRole('button', { name: 'Tải thêm' });
		fireEvent.click(loadMoreBtn);
		expect(await screen.findByText('geo_distance_km')).toBeInTheDocument();
		expect(observedFeatureCursors).toContain('cursor-p2');
		expect(screen.queryByRole('button', { name: 'Tải thêm' })).not.toBeInTheDocument();

		// Inspect source_code of PYTHON_CODE built-in
		fireEvent.click(screen.getByText('is_free_email'));
		expect(await screen.findByText(/gmail\.com/)).toBeInTheDocument();

		// Switch to Builder tab and create VELOCITY feature + PYTHON_CODE feature
		fireEvent.click(screen.getByRole('button', { name: 'Trình tạo đặc trưng' }));
		fireEvent.change(screen.getByLabelText(/Mã đặc trưng/i), { target: { value: 'custom_vel_6h' } });
		fireEvent.change(screen.getByLabelText(/Tên hiển thị/i), { target: { value: 'Tần suất 6h' } });
		fireEvent.click(screen.getByRole('button', { name: /Lưu đặc trưng/i }));

		await waitFor(() => {
			expect(createdPayloads.some((p) => p.feature_key === 'custom_vel_6h')).toBe(true);
		});

		// Create PYTHON_CODE custom feature
		fireEvent.click(screen.getByRole('button', { name: /Mã Python/i }));
		fireEvent.change(screen.getByLabelText(/Mã đặc trưng/i), { target: { value: 'custom_py_flag' } });
		fireEvent.change(screen.getByLabelText(/Tên hiển thị/i), { target: { value: 'Cờ Python' } });
		fireEvent.click(screen.getByRole('button', { name: /Lưu đặc trưng/i }));

		await waitFor(() => {
			expect(
				createdPayloads.some((p) => p.feature_key === 'custom_py_flag' && p.compute_kind === 'PYTHON_CODE')
			).toBe(true);
		});

		// Switch to Feature Sets tab and verify built-in set rendered
		fireEvent.click(screen.getByRole('button', { name: /Gói đặc trưng/i }));
		expect(await screen.findByText('pkg_ccfd_standard')).toBeInTheDocument();

		// Verify read-only fraud_analyst hides mutate controls
		cleanup();
		mockActorPermissions({
			'dataset:read': ['PROJECT'],
			'feature:read': ['PROJECT'],
		});
		renderWithProviders(<FeatureManagementModule />);
		await screen.findAllByText('tx_freq_last_1h');
		expect(screen.queryByRole('button', { name: 'Trình tạo đặc trưng' })).not.toBeInTheDocument();
	});
});
