import { beforeEach, describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { DatasetHubView } from '@/components/modules/data_management/DatasetHubView';
import { ModelHubView } from '@/components/modules/model/ModelHubView';
import { RuleCatalogView } from '@/components/modules/rule/RuleCatalogView';
import { DetectionJobsHubView } from '@/components/modules/detection/DetectionJobsHubView';
import { PoliciesView } from '@/components/modules/investigation/PoliciesView';
import { InsightReportModule } from '@/components/modules/InsightReportModule';
import { ComplianceReportCenterTab } from '@/components/modules/reports/ComplianceReportCenterTab';
import { AdminUsersPage } from '@/pages/AdminUsersPage';
import { renderWithProviders } from './renderWithProviders';
import { API, server } from './server';

const PROJECT_1_ID = '11111111-1111-1111-1111-111111111111';

const SAMPLE_PROJECT = {
	project_id: PROJECT_1_ID,
	project_name: 'Dự án Module Gate',
	description: 'Test',
	user_id: '22222222-2222-2222-2222-222222222222',
	status: 'ACTIVE',
	is_schema_locked: true,
	raw_schema: { columns: { amount: { logical_type: 'NUMERIC', physical_dtype: 'float64', nullable: false } } },
	datasets_count: 1,
	rules_count: 1,
	detection_jobs_count: 1,
	created_at: new Date().toISOString(),
	updated_at: new Date().toISOString(),
};

function setupRole(
	roleKey: string,
	permissions: Record<string, string[]>,
	systemPermissions: Record<string, string[]> = {}
) {
	server.use(
		http.get(`${API}/v1/auth/mode`, () =>
			HttpResponse.json({ success: true, data: { auth_mode: 'local_auto' } })
		),
		http.get(`${API}/v1/auth/me`, () =>
			HttpResponse.json({
				success: true,
				data: {
					user_id: '22222222-2222-2222-2222-222222222222',
					username: roleKey,
					email: `${roleKey}@usfds.local`,
					full_name: roleKey,
					status: 'ACTIVE',
					last_login_at: null,
					is_system_admin: false,
					system_role_keys: ['system_member'],
					system_permissions: systemPermissions,
					projects: [
						{
							project_id: PROJECT_1_ID,
							role_keys: [roleKey],
							permissions,
						},
					],
				},
			})
		),
		http.get(`${API}/v1/projects`, () =>
			HttpResponse.json({ success: true, data: { items: [SAMPLE_PROJECT], nextCursor: null } })
		),
		http.get(`${API}/v1/datasets`, () =>
			HttpResponse.json({
				success: true,
				data: {
					items: [
						{
							dataset_id: 'ds-1',
							project_id: PROJECT_1_ID,
							user_id: '22222222-2222-2222-2222-222222222222',
							dataset_name: 'raw_tx.csv',
							display_name: 'Raw Tx',
							description: null,
							contains_pii: false,
							data_classification: 'INTERNAL',
							created_at: new Date().toISOString(),
							updated_at: new Date().toISOString(),
							latest_stage: 'RAW',
							latest_validation_status: 'VALID',
							quality_score: 95,
							artifacts_count: 1,
						},
					],
					nextCursor: null,
				},
			})
		),
		http.get(`${API}/v1/rules`, () =>
			HttpResponse.json({
				success: true,
				data: {
					items: [
						{
							rule_id: 'rule-1',
							project_id: PROJECT_1_ID,
							rule_code: 'R-001',
							name: 'High Amount',
							description: 'Desc',
							status: 'DRAFT',
							current_version_id: 'rv-1',
							current_version: {
								rule_version_id: 'rv-1',
								rule_id: 'rule-1',
								version_number: 1,
								condition: { '>': [{ var: 'amount' }, 1000] },
								action: 'REVIEW',
								change_summary: 'v1',
								created_by: 'admin',
								created_at: new Date().toISOString(),
							},
							created_by: 'admin',
							created_at: new Date().toISOString(),
							updated_at: new Date().toISOString(),
						},
					],
					nextCursor: null,
				},
			})
		),
		http.get(`${API}/v1/training/models`, () => HttpResponse.json({ success: true, data: { items: [], nextCursor: null } })),
		http.get(`${API}/v1/training/runs`, () => HttpResponse.json({ success: true, data: { items: [], nextCursor: null } })),
		http.get(`${API}/v1/detection/jobs`, () => HttpResponse.json({ success: true, data: { items: [], nextCursor: null } })),
		http.get(`${API}/v1/cases`, () =>
			HttpResponse.json({ success: true, data: { items: [], total: 0, page: 1, size: 50 } })
		),
		http.get(`${API}/v1/blacklist`, () => HttpResponse.json({ success: true, data: [] })),
		http.get(`${API}/v1/cases/rule-feedback`, () => HttpResponse.json({ success: true, data: [] })),
		http.get(`${API}/v1/reports/overview`, () =>
			HttpResponse.json({
				success: true,
				data: {
					kpis: {},
					trends: [],
					available_jobs: [],
				},
			})
		)
	);
}

describe('M5 Domain Modules Feature Visibility', () => {
	beforeEach(() => {
		localStorage.clear();
		localStorage.setItem('usfds_active_project_id', PROJECT_1_ID);
	});

	it('test_module_actions_hidden_for_insufficient_permissions', async () => {
		// 1. fraud_analyst: dataset read-only, rule read-only (PA-A), blacklist manage allowed
		setupRole('fraud_analyst', {
			'project:read': ['PROJECT'],
			'dataset:read': ['PROJECT'],
			'rule:read': ['PROJECT'],
			'detection:read': ['PROJECT'],
			'detection:export': ['PROJECT'],
			'case:create': ['PROJECT'],
			'case:read': ['PROJECT'],
			'case:manual_review': ['PROJECT'],
			'blacklist:manage': ['PROJECT'],
			'report:read': ['PROJECT'],
			'report:create': ['PROJECT'],
			'report:export': ['PROJECT'],
		});

		const dsRender = renderWithProviders(<DatasetHubView />);
		await waitFor(() => expect(screen.getByText('raw_tx.csv')).toBeInTheDocument());
		expect(screen.queryByText('Nhập tập dữ liệu')).not.toBeInTheDocument();
		expect(screen.queryByTitle('Xóa tập dữ liệu')).not.toBeInTheDocument();
		dsRender.unmount();

		const ruleRender = renderWithProviders(<RuleCatalogView />);
		await waitFor(() => expect(screen.getByText('R-001')).toBeInTheDocument());
		expect(screen.queryByText('Luật nghiệp vụ mới')).not.toBeInTheDocument();
		expect(screen.queryByTitle('Chạy thử (dry run) trên dữ liệu lịch sử')).not.toBeInTheDocument();
		expect(screen.queryByTitle('Chỉnh sửa trong trình thiết kế luật')).not.toBeInTheDocument();
		expect(screen.queryByTitle('Xóa luật')).not.toBeInTheDocument();
		ruleRender.unmount();

		const detRender = renderWithProviders(<DetectionJobsHubView />);
		await waitFor(() => expect(screen.getByText('Làm mới')).toBeInTheDocument());
		expect(screen.queryByText('Phiên phát hiện mới')).not.toBeInTheDocument();
		detRender.unmount();

		const polRender = renderWithProviders(<PoliciesView projectId={PROJECT_1_ID} readOnly={false} />);
		await waitFor(() => expect(screen.getByText('Thêm thực thể vào danh sách đen')).toBeInTheDocument());
		polRender.unmount();

		// 2. data_scientist: compliance report tab hidden (report:read only), model create/train visible
		setupRole('data_scientist', {
			'project:read': ['PROJECT'],
			'dataset:read': ['PROJECT'],
			'model:read': ['PROJECT'],
			'model:create': ['PROJECT'],
			'training:read': ['PROJECT'],
			'training:create': ['PROJECT'],
			'report:read': ['PROJECT'],
		});

		const modelRender = renderWithProviders(<ModelHubView />);
		await waitFor(() => expect(screen.getByText('Nhập mô hình tùy chỉnh')).toBeInTheDocument());
		expect(screen.getByText('Lượt huấn luyện mới')).toBeInTheDocument();
		modelRender.unmount();

		const repRender = renderWithProviders(<InsightReportModule />);
		await waitFor(() =>
			expect(screen.getByRole('button', { name: /Tổng quan điều hành/i })).toBeInTheDocument()
		);
		expect(screen.queryByText('Trung tâm tuân thủ & SAR')).not.toBeInTheDocument();
		repRender.unmount();

		// 3. project_admin: model read-only (no create/train), blacklist add hidden (case:read only)
		setupRole('project_admin', {
			'project:read': ['PROJECT'],
			'model:read': ['PROJECT'],
			'training:read': ['PROJECT'],
			'deployment:deploy': ['PROJECT'],
			'case:read': ['PROJECT'],
		});

		const paModelRender = renderWithProviders(<ModelHubView />);
		await waitFor(() => expect(screen.getByText('Làm mới')).toBeInTheDocument());
		expect(screen.queryByText('Nhập mô hình tùy chỉnh')).not.toBeInTheDocument();
		expect(screen.queryByText('Lượt huấn luyện mới')).not.toBeInTheDocument();
		paModelRender.unmount();

		const paPolRender = renderWithProviders(<PoliciesView projectId={PROJECT_1_ID} readOnly={false} />);
		await waitFor(() =>
			expect(screen.getAllByText(/Danh sách đen thực thể/i).length).toBeGreaterThan(0)
		);
		expect(screen.queryByText('Thêm thực thể vào danh sách đen')).not.toBeInTheDocument();
		paPolRender.unmount();

		// 4. ComplianceReportCenterTab hides export buttons without report:export; AdminUsersPage hides mutations without write perms
		setupRole(
			'compliance_viewer',
			{
				'project:read': ['PROJECT'],
				'report:read': ['PROJECT'],
				'report:create': ['PROJECT'],
				'case:read': ['PROJECT'],
			},
			{
				'user:read': ['SYSTEM'],
				'role:read': ['SYSTEM'],
			}
		);
		server.use(
			http.get(`${API}/v1/users`, () =>
				HttpResponse.json({
					success: true,
					data: [
						{
							user_id: 'u1',
							username: 'analyst_1',
							email: 'a1@usfds.local',
							full_name: 'Analyst One',
							status: 'ACTIVE',
							is_system_admin: false,
							last_login_at: null,
						},
					],
				})
			),
			http.get(`${API}/v1/rbac/roles`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/rbac/permissions`, () => HttpResponse.json({ success: true, data: [] }))
		);

		const compRender = renderWithProviders(
			<ComplianceReportCenterTab projectId={PROJECT_1_ID} scope={{}} />
		);
		await waitFor(() =>
			expect(screen.getByText('Báo cáo kiểm toán gian lận & chính sách điều hành')).toBeInTheDocument()
		);
		expect(screen.queryByText('In / lưu PDF')).not.toBeInTheDocument();
		expect(screen.queryByText('.CSV')).not.toBeInTheDocument();
		compRender.unmount();

		const adminRender = renderWithProviders(<AdminUsersPage />);
		await waitFor(() => expect(screen.getByText('analyst_1')).toBeInTheDocument());
		expect(screen.queryByText('Tạo người dùng')).not.toBeInTheDocument();
		expect(screen.queryByText('Khóa')).not.toBeInTheDocument();
		expect(screen.queryByText('Đặt lại MK')).not.toBeInTheDocument();
		adminRender.unmount();
	});

	it('test_module_views_hide_mutate_actions_for_other_owners_under_own_scope', async () => {
		const ownUserId = '22222222-2222-2222-2222-222222222222';
		const otherUserId = '99999999-9999-9999-9999-999999999999';

		const mockTwoRecords = () => {
			server.use(
				http.get(`${API}/v1/datasets`, () =>
					HttpResponse.json({
						success: true,
						data: {
							items: [
								{
									dataset_id: 'ds-own',
									project_id: PROJECT_1_ID,
									user_id: ownUserId,
									dataset_name: 'own_tx.csv',
									display_name: 'Own Tx',
									description: null,
									contains_pii: false,
									data_classification: 'INTERNAL',
									created_at: new Date().toISOString(),
									updated_at: new Date().toISOString(),
									latest_stage: 'RAW',
									latest_validation_status: 'VALID',
									quality_score: 95,
									artifacts_count: 1,
								},
								{
									dataset_id: 'ds-other',
									project_id: PROJECT_1_ID,
									user_id: otherUserId,
									dataset_name: 'other_tx.csv',
									display_name: 'Other Tx',
									description: null,
									contains_pii: false,
									data_classification: 'INTERNAL',
									created_at: new Date().toISOString(),
									updated_at: new Date().toISOString(),
									latest_stage: 'RAW',
									latest_validation_status: 'VALID',
									quality_score: 92,
									artifacts_count: 1,
								},
							],
							nextCursor: null,
						},
					})
				),
				http.get(`${API}/v1/rules`, () =>
					HttpResponse.json({
						success: true,
						data: {
							items: [
								{
									rule_id: 'rule-own',
									project_id: PROJECT_1_ID,
									user_id: ownUserId,
									rule_code: 'R-OWN',
									name: 'Own Rule',
									description: 'Own',
									status: 'DRAFT',
									current_version_id: 'rv-own',
									current_version: {
										rule_version_id: 'rv-own',
										rule_id: 'rule-own',
										version_number: 1,
										condition: { '>': [{ var: 'amount' }, 100] },
										action: 'REVIEW',
										created_at: new Date().toISOString(),
									},
									created_at: new Date().toISOString(),
									updated_at: new Date().toISOString(),
								},
								{
									rule_id: 'rule-other',
									project_id: PROJECT_1_ID,
									user_id: otherUserId,
									rule_code: 'R-OTHER',
									name: 'Other Rule',
									description: 'Other',
									status: 'DRAFT',
									current_version_id: 'rv-other',
									current_version: {
										rule_version_id: 'rv-other',
										rule_id: 'rule-other',
										version_number: 1,
										condition: { '>': [{ var: 'amount' }, 500] },
										action: 'REJECT',
										created_at: new Date().toISOString(),
									},
									created_at: new Date().toISOString(),
									updated_at: new Date().toISOString(),
								},
							],
							nextCursor: null,
						},
					})
				),
				http.get(`${API}/v1/training/models`, () =>
					HttpResponse.json({
						success: true,
						data: {
							items: [
								{
									model_id: 'm-rf',
									project_id: null,
									user_id: null,
									model_name: 'random_forest',
									display_name: 'Random Forest',
									execution_type: 'BUILTIN',
									created_at: new Date().toISOString(),
								},
							],
							nextCursor: null,
						},
					})
				),
				http.get(`${API}/v1/training/models/m-rf/versions`, () =>
					HttpResponse.json({
						success: true,
						data: {
							items: [
								{
									version_id: 'ver-own',
									model_id: 'm-rf',
									project_id: PROJECT_1_ID,
									user_id: ownUserId,
									run_id: 'run-own',
									semver: 'v1',
									artifact_uri: 'models/v1.joblib',
									decision_threshold: 0.5,
									status: 'CANDIDATE',
									registered_at: new Date().toISOString(),
								},
								{
									version_id: 'ver-other',
									model_id: 'm-rf',
									project_id: PROJECT_1_ID,
									user_id: otherUserId,
									run_id: 'run-other',
									semver: 'v2',
									artifact_uri: 'models/v2.joblib',
									decision_threshold: 0.5,
									status: 'CANDIDATE',
									registered_at: new Date().toISOString(),
								},
							],
							nextCursor: null,
						},
					})
				),
				http.get(`${API}/v1/training/runs`, () =>
					HttpResponse.json({
						success: true,
						data: {
							items: [
								{
									run_id: 'run-own',
									project_id: PROJECT_1_ID,
									user_id: ownUserId,
									model_id: 'm-rf',
									version_id: 'ver-own',
									run_name: 'Own Run',
									status: 'COMPLETED',
									default_threshold: 0.5,
									created_at: new Date().toISOString(),
								},
								{
									run_id: 'run-other',
									project_id: PROJECT_1_ID,
									user_id: otherUserId,
									model_id: 'm-rf',
									version_id: 'ver-other',
									run_name: 'Other Run',
									status: 'COMPLETED',
									default_threshold: 0.5,
									created_at: new Date().toISOString(),
								},
							],
							nextCursor: null,
						},
					})
				)
			);
		};

		// 1. data_scientist with OWN on mutate/delete/deploy, PROJECT on read/dry_run
		setupRole('data_scientist', {
			'project:read': ['PROJECT'],
			'dataset:read': ['PROJECT'],
			'dataset:create': ['OWN'],
			'dataset:update': ['OWN'],
			'dataset:delete': ['OWN'],
			'model:read': ['PROJECT'],
			'training:read': ['PROJECT'],
			'deployment:deploy': ['OWN'],
			'rule:read': ['PROJECT'],
			'rule:create': ['OWN'],
			'rule:update': ['OWN'],
			'rule:delete': ['OWN'],
			'rule:deploy': ['OWN'],
			'rule:undeploy': ['OWN'],
			'rule:dry_run': ['PROJECT'],
		});
		mockTwoRecords();

		const dsRender = renderWithProviders(<DatasetHubView />);
		await waitFor(() => expect(screen.getByText('own_tx.csv')).toBeInTheDocument());
		expect(screen.getByText('other_tx.csv')).toBeInTheDocument();
		expect(screen.getAllByTitle('Xóa tập dữ liệu')).toHaveLength(1);
		dsRender.unmount();

		const ruleRender = renderWithProviders(<RuleCatalogView />);
		await waitFor(() => expect(screen.getByText('R-OWN')).toBeInTheDocument());
		expect(screen.getByText('R-OTHER')).toBeInTheDocument();
		expect(screen.getAllByTitle('Chạy thử (dry run) trên dữ liệu lịch sử')).toHaveLength(2);
		expect(screen.getAllByTitle('Chỉnh sửa trong trình thiết kế luật')).toHaveLength(1);
		expect(screen.getAllByTitle('Xóa luật')).toHaveLength(1);
		expect(screen.getAllByTitle('Nhấn để chuyển đổi trạng thái ACTIVE / INACTIVE')).toHaveLength(1);
		ruleRender.unmount();

		const modelRender = renderWithProviders(<ModelHubView />);
		await waitFor(() => expect(screen.getByText('Own Run')).toBeInTheDocument());
		expect(screen.getByText('Other Run')).toBeInTheDocument();
		await waitFor(() => expect(screen.getAllByText('Activate')).toHaveLength(1));
		modelRender.unmount();

		// 2. project_admin with PROJECT scope on delete/deploy sees actions on BOTH rows
		setupRole('project_admin', {
			'project:read': ['PROJECT'],
			'dataset:read': ['PROJECT'],
			'dataset:delete': ['PROJECT'],
			'model:read': ['PROJECT'],
			'training:read': ['PROJECT'],
			'deployment:deploy': ['PROJECT'],
			'rule:read': ['PROJECT'],
			'rule:deploy': ['PROJECT'],
			'rule:undeploy': ['PROJECT'],
			'rule:delete': ['PROJECT'],
		});
		mockTwoRecords();

		const paDsRender = renderWithProviders(<DatasetHubView />);
		await waitFor(() => expect(screen.getByText('own_tx.csv')).toBeInTheDocument());
		expect(screen.getAllByTitle('Xóa tập dữ liệu')).toHaveLength(2);
		paDsRender.unmount();

		const paRuleRender = renderWithProviders(<RuleCatalogView />);
		await waitFor(() => expect(screen.getByText('R-OWN')).toBeInTheDocument());
		expect(screen.getAllByTitle('Xóa luật')).toHaveLength(2);
		expect(screen.getAllByTitle('Nhấn để chuyển đổi trạng thái ACTIVE / INACTIVE')).toHaveLength(2);
		paRuleRender.unmount();
	});

	it('test_module_views_display_owner_and_load_more_with_cursor', async () => {
		setupRole('data_scientist', {
			'project:read': ['PROJECT'],
			'dataset:read': ['PROJECT'],
			'model:read': ['PROJECT'],
			'training:read': ['PROJECT'],
			'rule:read': ['PROJECT'],
			'detection:read': ['PROJECT'],
		});

		const ownerOne = { user_id: 'user-1', username: 'alice_ds', full_name: 'Alice Nguyen' };
		const ownerTwo = { user_id: 'user-other', username: 'bob_ds', full_name: 'Bob Tran' };

		server.use(
			http.get(`${API}/v1/projects`, () =>
				HttpResponse.json({
					success: true,
					data: {
						items: [
							{
								project_id: PROJECT_1_ID,
								project_name: 'Fraud Proj 1',
								user_id: 'user-1',
								owner: ownerOne,
								status: 'ACTIVE',
								is_schema_locked: false,
								datasets_count: 1,
								rules_count: 1,
								detection_jobs_count: 1,
								created_at: '2026-01-01T00:00:00Z',
								updated_at: '2026-01-01T00:00:00Z',
							},
						],
						nextCursor: null,
					},
				})
			),
			http.get(`${API}/v1/datasets`, ({ request }) => {
				const cursor = new URL(request.url).searchParams.get('cursor');
				if (cursor === 'c1') {
					return HttpResponse.json({
						success: true,
						data: {
							items: [
								{
									dataset_id: 'ds-p2',
									project_id: PROJECT_1_ID,
									user_id: 'user-other',
									owner: ownerTwo,
									dataset_name: 'page2_tx.csv',
									contains_pii: false,
									created_at: '2026-01-02T00:00:00Z',
									artifacts_count: 1,
								},
							],
							nextCursor: null,
						},
					});
				}
				return HttpResponse.json({
					success: true,
					data: {
						items: [
							{
								dataset_id: 'ds-p1',
								project_id: PROJECT_1_ID,
								user_id: 'user-1',
								owner: ownerOne,
								dataset_name: 'page1_tx.csv',
								contains_pii: false,
								created_at: '2026-01-01T00:00:00Z',
								artifacts_count: 1,
							},
						],
						nextCursor: 'c1',
					},
				});
			}),
			http.get(`${API}/v1/training/models`, () =>
				HttpResponse.json({
					success: true,
					data: {
						items: [
							{
								model_id: 'm-builtin',
								project_id: null,
								user_id: null,
								owner: null,
								model_name: 'random_forest',
								display_name: 'Random Forest',
								execution_type: 'BUILTIN',
								created_at: '2026-01-01T00:00:00Z',
							},
							{
								model_id: 'm-custom',
								project_id: PROJECT_1_ID,
								user_id: 'user-1',
								owner: ownerOne,
								model_name: 'custom_lr',
								display_name: 'Custom LR',
								execution_type: 'SCRIPT',
								created_at: '2026-01-01T00:00:00Z',
							},
						],
						nextCursor: null,
					},
				})
			),
			http.get(`${API}/v1/training/models/m-builtin/versions`, () =>
				HttpResponse.json({ success: true, data: { items: [], nextCursor: null } })
			),
			http.get(`${API}/v1/training/models/m-custom/versions`, () =>
				HttpResponse.json({ success: true, data: { items: [], nextCursor: null } })
			),
			http.get(`${API}/v1/training/runs`, () =>
				HttpResponse.json({
					success: true,
					data: {
						items: [
							{
								run_id: 'run-p1',
								project_id: PROJECT_1_ID,
								user_id: 'user-other',
								owner: ownerTwo,
								model_id: 'm-custom',
								run_name: 'Run Bob',
								status: 'COMPLETED',
								default_threshold: 0.5,
								created_at: '2026-01-01T00:00:00Z',
							},
						],
						nextCursor: null,
					},
				})
			),
			http.get(`${API}/v1/rules`, () =>
				HttpResponse.json({
					success: true,
					data: {
						items: [
							{
								rule_id: 'r-p1',
								project_id: PROJECT_1_ID,
								user_id: 'user-1',
								owner: ownerOne,
								rule_code: 'R-OWNER',
								name: 'Rule Alice',
								description: 'Test',
								status: 'ACTIVE',
								created_at: '2026-01-01T00:00:00Z',
								updated_at: '2026-01-01T00:00:00Z',
							},
						],
						nextCursor: null,
					},
				})
			),
			http.get(`${API}/v1/detection/jobs`, () =>
				HttpResponse.json({
					success: true,
					data: {
						items: [
							{
								job_id: 'j-p1',
								project_id: PROJECT_1_ID,
								user_id: 'user-other',
								owner: ownerTwo,
								input_path: 'raw.csv',
								score_threshold: 0.5,
								use_rules: true,
								status: 'COMPLETED',
								created_at: '2026-01-01T00:00:00Z',
							},
						],
						nextCursor: null,
					},
				})
			)
		);

		const dsRender = renderWithProviders(<DatasetHubView />);
		await waitFor(() => expect(screen.getByText('page1_tx.csv')).toBeInTheDocument());
		expect(screen.getByText('Alice Nguyen')).toBeInTheDocument();
		const loadMoreBtn = screen.getByRole('button', { name: /Tải thêm/i });
		loadMoreBtn.click();
		await waitFor(() => expect(screen.getByText('page2_tx.csv')).toBeInTheDocument());
		expect(screen.getByText('Bob Tran')).toBeInTheDocument();
		dsRender.unmount();

		const modelRender = renderWithProviders(<ModelHubView />);
		await waitFor(() => expect(screen.getByText('Run Bob')).toBeInTheDocument());
		expect(screen.getByText('Bob Tran')).toBeInTheDocument();
		screen.getByRole('button', { name: /Model Registry/i }).click();
		await waitFor(() => expect(screen.getByText('Hệ thống')).toBeInTheDocument());
		expect(screen.getByText('Alice Nguyen')).toBeInTheDocument();
		modelRender.unmount();

		const ruleRender = renderWithProviders(<RuleCatalogView />);
		await waitFor(() => expect(screen.getByText('R-OWNER')).toBeInTheDocument());
		expect(screen.getByText('Alice Nguyen')).toBeInTheDocument();
		ruleRender.unmount();

		const detRender = renderWithProviders(<DetectionJobsHubView />);
		await waitFor(() => expect(screen.getByText('raw.csv')).toBeInTheDocument());
		expect(screen.getByText('Bob Tran')).toBeInTheDocument();
		detRender.unmount();
	});
});
