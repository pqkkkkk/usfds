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
			HttpResponse.json({ success: true, data: [SAMPLE_PROJECT] })
		),
		http.get(`${API}/v1/datasets`, () =>
			HttpResponse.json({
				success: true,
				data: [
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
			})
		),
		http.get(`${API}/v1/rules`, () =>
			HttpResponse.json({
				success: true,
				data: [
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
			})
		),
		http.get(`${API}/v1/training/models`, () => HttpResponse.json({ success: true, data: [] })),
		http.get(`${API}/v1/training/runs`, () => HttpResponse.json({ success: true, data: [] })),
		http.get(`${API}/v1/detection/jobs`, () => HttpResponse.json({ success: true, data: [] })),
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
			'case:claim': ['PROJECT'],
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

		// 3. project_admin: model read-only (no create/train), blacklist add hidden (case:read + case:assign only)
		setupRole('project_admin', {
			'project:read': ['PROJECT'],
			'model:read': ['PROJECT'],
			'training:read': ['PROJECT'],
			'deployment:deploy': ['PROJECT'],
			'case:read': ['PROJECT'],
			'case:assign': ['PROJECT'],
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
});
