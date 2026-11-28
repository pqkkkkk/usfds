import { describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { API, server } from '@/test/server';
import { renderWithProviders } from '@/test/renderWithProviders';
import { SchemaMappingWorkspace } from './SchemaMappingWorkspace';
import { FeatureEngineeringWorkspace } from './FeatureEngineeringWorkspace';
import { RuleClauseRow } from '../rule/RuleClauseRow';
import { buildAvailableFieldsWithEnrichedFeatures, groupToJsonLogic } from '@/utils/jsonLogicParser';
import type { DatasetArtifactResponse, DataMappingConfig, FeatureEngineeringConfig } from '@/types/dataset';
import type { FeatureResponse, FeatureSetResponse } from '@/types/feature';
import type { RuleClause } from '@/types/rule';

const PROJECT_ID = '11111111-1111-1111-1111-111111111111';

const MOCK_FEATURES: FeatureResponse[] = [
	{
		feature_id: 'f-001',
		project_id: null,
		user_id: null,
		is_builtin: true,
		feature_key: 'tx_freq_last_1h',
		display_name: 'Tần suất giao dịch 1 giờ qua',
		description: 'Đếm giao dịch 1h',
		megafamily: 'ORDERS',
		compute_kind: 'VELOCITY',
		output_type: 'NUMERIC',
		is_stateful: false,
		requires_label: false,
		config_json: { entity_key: 'user_id', agg_fn: 'COUNT', window: '1h' },
		source_code: null,
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
		display_name: 'Email miễn phí',
		description: 'Kiểm tra email domain miễn phí',
		megafamily: 'IDENTITY',
		compute_kind: 'PYTHON_CODE',
		output_type: 'BOOLEAN',
		is_stateful: false,
		requires_label: false,
		config_json: {},
		source_code: 'def compute(df, params):\n\treturn df["email"].str.contains("gmail.com")\n',
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
		description: 'Gói chuẩn CCFD',
		domain_tag: 'CCFD',
		default_config: {},
		feature_ids: ['f-001'],
		created_at: '2026-11-24T00:00:00Z',
		updated_at: '2026-11-24T00:00:00Z',
	},
];

describe('Cross-Module Feature Integration (M4)', () => {
	it('test_bulk_schema_mapping_picker_fe_feature_set_and_rule_enriched_picker', async () => {
		const rawSnapshot: Record<string, string> = {
			event_id: 'object',
			timestamp: 'datetime64[ns]',
			amount: 'float64',
			user_id: 'object',
			label: 'int64',
		};
		for (let i = 1; i <= 25; i++) {
			rawSnapshot[`V${i}`] = 'float64';
		}

		const rawArtifact: DatasetArtifactResponse = {
			artifact_id: 'art-raw-30',
			dataset_id: 'ds-1',
			pipeline_stage: 'RAW',
			storage_path: '/tmp/raw.parquet',
			output_paths: {},
			row_count: 1000,
			column_count: 30,
			schema_snapshot: rawSnapshot,
			created_at: '2026-11-24T00:00:00Z',
		};

		const mappedArtifact: DatasetArtifactResponse = {
			...rawArtifact,
			artifact_id: 'art-mapped-1',
			pipeline_stage: 'MAPPED',
		};

		server.use(
			http.get(`${API}/v1/system-metadata/columns`, () =>
				HttpResponse.json({
					success: true,
					data: [
						{ metadata_id: 'm1', column_key: 'event_id', display_name: 'Mã GD', category: 'CORE', logical_type: 'STRING', is_required: true, ml_role: 'IDENTIFIER', aliases: ['event_id'], is_active: true, display_order: 1 },
						{ metadata_id: 'm2', column_key: 'timestamp', display_name: 'Thời gian', category: 'CORE', logical_type: 'DATETIME', is_required: true, ml_role: 'TIMESTAMP', aliases: ['timestamp'], is_active: true, display_order: 2 },
						{ metadata_id: 'm3', column_key: 'amount', display_name: 'Số tiền', category: 'CORE', logical_type: 'NUMERIC', is_required: true, ml_role: 'FEATURE', aliases: ['amount'], is_active: true, display_order: 3 },
						{ metadata_id: 'm4', column_key: 'user_id', display_name: 'Người dùng', category: 'CORE', logical_type: 'STRING', is_required: true, ml_role: 'IDENTIFIER', aliases: ['user_id'], is_active: true, display_order: 4 },
						{ metadata_id: 'm5', column_key: 'label', display_name: 'Nhãn', category: 'CORE', logical_type: 'NUMERIC', is_required: true, ml_role: 'LABEL', aliases: ['label'], is_active: true, display_order: 5 },
					],
				})
			),
			http.get(`${API}/v1/features`, () =>
				HttpResponse.json({
					success: true,
					data: { items: MOCK_FEATURES, nextCursor: null },
				})
			),
			http.get(`${API}/v1/feature-sets`, () =>
				HttpResponse.json({
					success: true,
					data: { items: MOCK_SETS, nextCursor: null },
				})
			),
			http.get(`${API}/v1/features/compatibility`, () =>
				HttpResponse.json({
					success: true,
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
								display_name: 'Email miễn phí',
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
			)
		);

		// 1. Bulk Column Picker in SchemaMappingWorkspace
		let latestMappingConfig: DataMappingConfig | null = null;
		renderWithProviders(
			<SchemaMappingWorkspace
				rawArtifact={rawArtifact}
				mappedArtifact={null}
				onConfigChange={(cfg) => {
					latestMappingConfig = cfg;
				}}
			/>
		);

		expect(await screen.findByText(/Giữ 5 \/ 30 cột nguồn/i)).toBeInTheDocument();

		fireEvent.click(screen.getByRole('button', { name: /Chọn nhiều cột tùy chọn/i }));
		fireEvent.change(screen.getByPlaceholderText(/Tìm tên cột/i), { target: { value: 'V' } });
		fireEvent.click(screen.getByRole('button', { name: /Chọn tất cả kết quả lọc/i }));
		fireEvent.click(screen.getByRole('button', { name: /Áp dụng lựa chọn/i }));

		expect(await screen.findByText(/Giữ 30 \/ 30 cột nguồn/i)).toBeInTheDocument();
		await waitFor(() => {
			expect(Object.keys(latestMappingConfig?.optional_columns || {}).length).toBe(25);
			expect(latestMappingConfig?.optional_columns?.['V1']).toBe('V1');
			expect(latestMappingConfig?.optional_columns?.['V25']).toBe('V25');
		});

		// 2. Step 3 FE FeatureSet & Feature picker
		cleanup();
		let latestFeConfig: FeatureEngineeringConfig | null = null;
		renderWithProviders(
			<FeatureEngineeringWorkspace
				projectId={PROJECT_ID}
				datasetId="ds-1"
				mappedArtifact={mappedArtifact}
				feArtifact={null}
				onConfigChange={(cfg) => {
					latestFeConfig = cfg;
				}}
			/>
		);

		expect(await screen.findByText(/pkg_ccfd_standard/i)).toBeInTheDocument();
		expect(await screen.findByText(/tx_freq_last_1h/i)).toBeInTheDocument();
		expect(await screen.findByText(/Thiếu cột/i)).toBeInTheDocument();

		fireEvent.click(screen.getByLabelText(/Chọn gói pkg_ccfd_standard/i));
		fireEvent.click(screen.getByLabelText(/Chọn đặc trưng tx_freq_last_1h/i));

		await waitFor(() => {
			expect(latestFeConfig?.feature_set_ids).toEqual(['fs-001']);
			expect(latestFeConfig?.feature_ids).toEqual(['f-001']);
		});

		// 3. Rule Studio enriched.* picker + JsonLogic compile
		cleanup();
		const availableFields = buildAvailableFieldsWithEnrichedFeatures(
			{
				version: 1,
				locked_at: '2026-11-24T00:00:00Z',
				columns: {
					amount: { logical_type: 'NUMERIC', physical_dtype: 'float64', nullable: false },
				},
			},
			MOCK_FEATURES
		);
		const onClauseChange = vi.fn();
		const initialClause: RuleClause = {
			id: 'c1',
			field: 'amount',
			operator: '>',
			value: 100,
		};

		renderWithProviders(
			<RuleClauseRow
				clause={initialClause}
				indexLabel="1.1"
				availableFields={availableFields}
				onChange={onClauseChange}
				onDelete={vi.fn()}
			/>
		);

		const select = screen.getByDisplayValue(/amount/i);
		expect(select.innerHTML).toContain('Đặc trưng làm giàu');
		fireEvent.change(select, { target: { value: 'enriched.tx_freq_last_1h' } });

		expect(onClauseChange).toHaveBeenCalled();
		const updatedClause = onClauseChange.mock.calls[0][0] as RuleClause;
		expect(updatedClause.field).toBe('enriched.tx_freq_last_1h');

		const compiled = groupToJsonLogic({
			id: 'g1',
			combinator: 'ALL',
			clauses: [updatedClause],
		});
		expect(JSON.stringify(compiled)).toContain('"var":"enriched.tx_freq_last_1h"');
	});

	it('SchemaMappingWorkspace: auto-suggests label value mapping from default list and lets user customize 0/1 mapping', async () => {
		server.use(
			http.get(`${API}/v1/system-metadata/columns`, () =>
				HttpResponse.json({
					success: true,
					data: [
						{ metadata_id: 'm1', column_key: 'event_id', display_name: 'Mã GD', category: 'CORE', logical_type: 'STRING', is_required: true, ml_role: 'IDENTIFIER', aliases: ['tx_id'], is_active: true, display_order: 1 },
						{ metadata_id: 'm2', column_key: 'timestamp', display_name: 'Thời gian', category: 'CORE', logical_type: 'DATETIME', is_required: true, ml_role: 'TIMESTAMP', aliases: ['tx_time'], is_active: true, display_order: 2 },
						{ metadata_id: 'm3', column_key: 'amount', display_name: 'Số tiền', category: 'CORE', logical_type: 'NUMERIC', is_required: true, ml_role: 'FEATURE', aliases: ['tx_amt'], is_active: true, display_order: 3 },
						{ metadata_id: 'm4', column_key: 'user_id', display_name: 'Người dùng', category: 'CORE', logical_type: 'STRING', is_required: true, ml_role: 'IDENTIFIER', aliases: ['cust_id'], is_active: true, display_order: 4 },
						{ metadata_id: 'm5', column_key: 'label', display_name: 'Nhãn', category: 'CORE', logical_type: 'NUMERIC', is_required: true, ml_role: 'LABEL', aliases: ['is_fraud'], is_active: true, display_order: 5 },
					],
				})
			)
		);

		// Case 1: distinct_values = ['fraud', 'legit'] -> auto-suggests { fraud: 1, legit: 0 } and isValid = true
		const rawArtifactStr: DatasetArtifactResponse = {
			artifact_id: 'art-raw-str',
			dataset_id: 'ds-str',
			pipeline_stage: 'RAW',
			storage_path: '/tmp/raw_str.csv',
			output_paths: {},
			row_count: 100,
			column_count: 5,
			schema_snapshot: {
				tx_id: 'object',
				tx_time: 'object',
				tx_amt: 'float64',
				cust_id: 'object',
				is_fraud: 'object',
			},
			validation_report: {
				profiling: {
					row_count: 100,
					field_count: 5,
					field_names: ['tx_id', 'tx_time', 'tx_amt', 'cust_id', 'is_fraud'],
					fields: [
						{ name: 'is_fraud', dtype: 'object', unique_count: 2, null_count: 0, null_percentage: 0, distinct_values: ['fraud', 'legit'] },
					],
				},
			},
			created_at: '2026-11-28T00:00:00Z',
		};

		let latestConfig1: DataMappingConfig | null = null;
		let latestValid1 = false;
		renderWithProviders(
			<SchemaMappingWorkspace
				rawArtifact={rawArtifactStr}
				mappedArtifact={null}
				onConfigChange={(cfg, valid) => {
					latestConfig1 = cfg;
					latestValid1 = valid;
				}}
			/>
		);

		await waitFor(() => {
			expect(latestValid1).toBe(true);
			expect(latestConfig1?.label_value_mapping).toEqual({ fraud: 1, legit: 0 });
		});

		// Case 2: distinct_values = ['1', '2'] -> '1' -> 1 suggested, '2' unassigned (isValid = false) until user assigns '2' -> 0 (or edits 1 -> 0, 2 -> 1)
		cleanup();
		const rawArtifactNum: DatasetArtifactResponse = {
			...rawArtifactStr,
			artifact_id: 'art-raw-num',
			schema_snapshot: {
				tx_id: 'object',
				tx_time: 'object',
				tx_amt: 'float64',
				cust_id: 'object',
				is_fraud: 'int64',
			},
			validation_report: {
				profiling: {
					row_count: 100,
					field_count: 5,
					field_names: ['tx_id', 'tx_time', 'tx_amt', 'cust_id', 'is_fraud'],
					fields: [
						{ name: 'is_fraud', dtype: 'int64', unique_count: 2, null_count: 0, null_percentage: 0, distinct_values: ['1', '2'] },
					],
				},
			},
		};

		let latestConfig2: DataMappingConfig | null = null;
		let latestValid2 = true;
		renderWithProviders(
			<SchemaMappingWorkspace
				rawArtifact={rawArtifactNum}
				mappedArtifact={null}
				onConfigChange={(cfg, valid) => {
					latestConfig2 = cfg;
					latestValid2 = valid;
				}}
			/>
		);

		const select1 = await screen.findByLabelText(/Ánh xạ giá trị nhãn 1/i) as HTMLSelectElement;
		const select2 = await screen.findByLabelText(/Ánh xạ giá trị nhãn 2/i) as HTMLSelectElement;
		expect(select1.value).toBe('1');
		expect(select2.value).toBe('');
		await waitFor(() => {
			expect(latestValid2).toBe(false);
		});

		fireEvent.change(select1, { target: { value: '0' } });
		fireEvent.change(select2, { target: { value: '1' } });

		await waitFor(() => {
			expect(latestValid2).toBe(true);
			expect(latestConfig2?.label_value_mapping).toEqual({ '1': 0, '2': 1 });
		});

		// Case 3: legacy RAW artifact without distinct_values supports manual mapping entry
		cleanup();
		const rawArtifactLegacy: DatasetArtifactResponse = {
			...rawArtifactStr,
			artifact_id: 'art-raw-legacy',
			validation_report: {},
		};
		let latestConfig3: DataMappingConfig | null = null;
		let latestValid3 = false;
		renderWithProviders(
			<SchemaMappingWorkspace
				rawArtifact={rawArtifactLegacy}
				mappedArtifact={null}
				onConfigChange={(cfg, valid) => {
					latestConfig3 = cfg;
					latestValid3 = valid;
				}}
			/>
		);

		const addManualBtn = await screen.findByRole('button', { name: /Thêm giá trị nhãn/i });
		expect(latestValid3).toBe(true);
		fireEvent.click(addManualBtn);
		const rawInput = await screen.findByPlaceholderText(/Giá trị nguồn/i);
		const targetSelect = await screen.findByLabelText(/Giá trị nhị phân thủ công/i);
		fireEvent.change(rawInput, { target: { value: 'Y' } });
		fireEvent.change(targetSelect, { target: { value: '1' } });
		await waitFor(() => {
			expect(latestValid3).toBe(true);
			expect(latestConfig3?.label_value_mapping).toEqual({ Y: 1 });
		});
	});
});
