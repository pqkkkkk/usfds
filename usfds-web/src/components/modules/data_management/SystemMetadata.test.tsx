import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import { AdminUsersPage } from '@/pages/AdminUsersPage';
import { SchemaMappingWorkspace } from './SchemaMappingWorkspace';
import type { DatasetArtifactResponse, DataMappingConfig } from '@/types/dataset';
import type { SystemColumnMetadata } from '@/types/systemMetadata';

const BASE_COLUMNS: SystemColumnMetadata[] = [
	{
		metadata_id: 'col-1',
		column_key: 'event_id',
		display_name: 'Mã giao dịch',
		category: 'CORE',
		logical_type: 'STRING',
		is_required: true,
		ml_role: 'IDENTIFIER',
		aliases: ['event_id', 'transaction_id', 'tx_id'],
		description: 'Mã định danh giao dịch duy nhất',
		is_active: true,
		display_order: 1,
	},
	{
		metadata_id: 'col-2',
		column_key: 'timestamp',
		display_name: 'Thời gian giao dịch',
		category: 'CORE',
		logical_type: 'DATETIME',
		is_required: true,
		ml_role: 'TIMESTAMP',
		aliases: ['timestamp', 'tx_time', 'trans_date_time'],
		description: 'Dấu thời gian sự kiện giao dịch',
		is_active: true,
		display_order: 2,
	},
	{
		metadata_id: 'col-3',
		column_key: 'amount',
		display_name: 'Số tiền giao dịch',
		category: 'CORE',
		logical_type: 'NUMERIC',
		is_required: true,
		ml_role: 'FEATURE',
		aliases: ['amount', 'amt'],
		description: 'Giá trị tiền tệ giao dịch',
		is_active: true,
		display_order: 3,
	},
	{
		metadata_id: 'col-4',
		column_key: 'user_id',
		display_name: 'Mã người dùng',
		category: 'CORE',
		logical_type: 'STRING',
		is_required: true,
		ml_role: 'IDENTIFIER',
		aliases: ['user_id', 'cc_num', 'account_id'],
		description: 'Định danh khách hàng / tài khoản',
		is_active: true,
		display_order: 4,
	},
	{
		metadata_id: 'col-5',
		column_key: 'label',
		display_name: 'Nhãn gian lận',
		category: 'CORE',
		logical_type: 'NUMERIC',
		is_required: true,
		ml_role: 'LABEL',
		aliases: ['label', 'is_fraud', 'class'],
		description: 'Nhãn gian lận thực tế',
		is_active: true,
		display_order: 5,
	},
	{
		metadata_id: 'col-6',
		column_key: 'merchant',
		display_name: 'Đơn vị chấp nhận thẻ',
		category: 'DOMAIN',
		logical_type: 'STRING',
		is_required: false,
		ml_role: 'FEATURE',
		aliases: ['merchant', 'merch_name'],
		description: 'Tên đơn vị kinh doanh',
		is_active: true,
		display_order: 10,
	},
];

describe('System Metadata Management (ISS-007, ISS-027)', () => {
	it('test_admin_system_metadata_tab_renders_and_manages_columns', async () => {
		let store: SystemColumnMetadata[] = [...BASE_COLUMNS];
		const captured: {
			posted: Record<string, unknown> | null;
			patched: Record<string, unknown> | null;
		} = { posted: null, patched: null };

		server.use(
			http.get(`${API}/v1/users`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/rbac/roles`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/rbac/permissions`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/system-metadata/columns`, () =>
				HttpResponse.json({ success: true, data: store })
			),
			http.post(`${API}/v1/system-metadata/columns`, async ({ request }) => {
				const body = (await request.json()) as Record<string, unknown>;
				captured.posted = body;
				const created: SystemColumnMetadata = {
					metadata_id: 'col-new',
					column_key: String(body.column_key),
					display_name: String(body.display_name),
					category: 'DOMAIN',
					logical_type: (body.logical_type as SystemColumnMetadata['logical_type']) || 'STRING',
					is_required: Boolean(body.is_required),
					ml_role: (body.ml_role as SystemColumnMetadata['ml_role']) || 'FEATURE',
					aliases: Array.isArray(body.aliases) ? (body.aliases as string[]) : [],
					description: (body.description as string | null) ?? null,
					is_active: true,
					display_order: 100,
				};
				store = [...store, created];
				return HttpResponse.json({ success: true, data: created }, { status: 201 });
			}),
			http.patch(`${API}/v1/system-metadata/columns/:id`, async ({ params, request }) => {
				const body = (await request.json()) as Record<string, unknown>;
				captured.patched = body;
				store = store.map((c) =>
					c.metadata_id === params.id
						? {
							...c,
							aliases: Array.isArray(body.aliases) ? (body.aliases as string[]) : c.aliases,
							description: body.description !== undefined ? (body.description as string) : c.description,
						}
						: c
				);
				const updated = store.find((c) => c.metadata_id === params.id)!;
				return HttpResponse.json({ success: true, data: updated });
			})
		);

		renderWithProviders(<AdminUsersPage />);

		const metadataTabBtn = await screen.findByRole('button', { name: /Siêu dữ liệu hệ thống/i });
		fireEvent.click(metadataTabBtn);

		// Shows 5 CORE columns with delete button disabled/locked
		expect((await screen.findAllByText('event_id')).length).toBeGreaterThan(0);
		expect(screen.getAllByText('timestamp').length).toBeGreaterThan(0);
		expect(screen.getAllByText('amount').length).toBeGreaterThan(0);
		expect(screen.getAllByText('user_id').length).toBeGreaterThan(0);
		expect(screen.getAllByText('label').length).toBeGreaterThan(0);
		expect(screen.getAllByText('merchant').length).toBeGreaterThan(0);

		const lockedDeleteBtn = screen.getByTestId('delete-column-event_id');
		expect(lockedDeleteBtn).toBeDisabled();

		// Add a new required IDENTIFIER DOMAIN column: device_id
		fireEvent.change(screen.getByLabelText(/Mã cột chuẩn/i), { target: { value: 'device_id' } });
		fireEvent.change(screen.getByLabelText(/Tên hiển thị/i), { target: { value: 'Mã thiết bị' } });
		fireEvent.change(screen.getByLabelText(/Vai trò ML/i), { target: { value: 'IDENTIFIER' } });
		fireEvent.click(screen.getByLabelText(/Bắt buộc ánh xạ/i));
		fireEvent.change(screen.getByLabelText(/Danh sách alias gợi ý/i), { target: { value: 'dev_hash, device_fp' } });

		fireEvent.click(screen.getByRole('button', { name: /Thêm cột nghiệp vụ/i }));

		await waitFor(() => expect(captured.posted).not.toBeNull());
		expect(captured.posted).toMatchObject({
			column_key: 'device_id',
			display_name: 'Mã thiết bị',
			ml_role: 'IDENTIFIER',
			is_required: true,
			aliases: ['dev_hash', 'device_fp'],
		});
		expect((await screen.findAllByText('device_id')).length).toBeGreaterThan(0);

		// Update alias for CORE column event_id
		fireEvent.click(screen.getByTestId('edit-column-event_id'));
		const editAliasesInput = await screen.findByTestId('edit-aliases-input');
		fireEvent.change(editAliasesInput, { target: { value: 'event_id, ma_giao_dich' } });
		fireEvent.click(screen.getByRole('button', { name: /Lưu thay đổi/i }));

		await waitFor(() => expect(captured.patched).not.toBeNull());
		expect(captured.patched?.aliases).toEqual(['event_id', 'ma_giao_dich']);
	});

	it('test_schema_mapping_workspace_uses_dynamic_metadata_and_aliases', async () => {
		const dynamicColumns: SystemColumnMetadata[] = [
			...BASE_COLUMNS.map((c) =>
				c.column_key === 'event_id'
					? { ...c, aliases: ['event_id', 'ma_giao_dich'] }
					: c
			),
			{
				metadata_id: 'col-dev',
				column_key: 'device_id',
				display_name: 'Mã thiết bị',
				category: 'DOMAIN',
				logical_type: 'STRING',
				is_required: true,
				ml_role: 'IDENTIFIER',
				aliases: ['device_id', 'dev_hash'],
				description: 'Định danh thiết bị',
				is_active: true,
				display_order: 12,
			},
		];

		server.use(
			http.get(`${API}/v1/system-metadata/columns`, () =>
				HttpResponse.json({ success: true, data: dynamicColumns })
			)
		);

		const rawArtifact: DatasetArtifactResponse = {
			artifact_id: 'art-raw-1',
			dataset_id: 'ds-1',
			pipeline_stage: 'RAW',
			storage_path: 'datasets/ds-1/raw/raw.parquet',
			output_paths: { raw: 'datasets/ds-1/raw/raw.parquet' },
			schema_snapshot: {
				ma_giao_dich: 'object',
				trans_date_time: 'object',
				amt: 'float64',
				cc_num: 'object',
				is_fraud: 'int64',
				dev_hash: 'object',
				merch_name: 'object',
			},
			created_at: '2026-11-21T00:00:00Z',
		};

		const onConfigChange = vi.fn<(cfg: DataMappingConfig, valid: boolean) => void>();

		renderWithProviders(
			<SchemaMappingWorkspace
				rawArtifact={rawArtifact}
				mappedArtifact={null}
				onConfigChange={onConfigChange}
			/>
		);

		// Required DOMAIN column device_id renders in mandatory section
		expect((await screen.findAllByText('device_id')).length).toBeGreaterThan(0);

		// Auto-matched event_id -> ma_giao_dich and device_id -> dev_hash
		await waitFor(() => {
			const calls = onConfigChange.mock.calls;
			expect(calls.length).toBeGreaterThan(0);
			const [latestConfig, isValid] = calls[calls.length - 1];
			expect(latestConfig.event_id_column).toBe('ma_giao_dich');
			expect(latestConfig.optional_columns.dev_hash).toBe('device_id');
			expect(isValid).toBe(true);
		});
	});

	it('renders error banner when system metadata API fails in admin tab', async () => {
		server.use(
			http.get(`${API}/v1/users`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/rbac/roles`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/rbac/permissions`, () => HttpResponse.json({ success: true, data: [] })),
			http.get(`${API}/v1/system-metadata/columns`, () =>
				HttpResponse.json({ success: false, error: 'Lỗi máy chủ siêu dữ liệu' }, { status: 500 })
			)
		);

		renderWithProviders(<AdminUsersPage />);
		const metadataTabBtn = await screen.findByRole('button', { name: /Siêu dữ liệu hệ thống/i });
		fireEvent.click(metadataTabBtn);

		expect(await screen.findByText(/Lỗi máy chủ siêu dữ liệu/i)).toBeInTheDocument();
	});
});
