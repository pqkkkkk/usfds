<!-- [26-11-28] Converted to a thin index pointing to the split authoritative sub-specs (ISS-059). -->
# Đặc tả use case hệ thống phân hệ Detection (Mục lục)

Đặc tả chi tiết phân hệ **Detection** đã được tách thành 3 tài liệu nguồn chuẩn theo từng tiểu phân hệ. Luôn đọc trực tiếp tệp con tương ứng thay vì giữ bản sao trùng lặp tại đây:

| Tiểu phân hệ | Tệp đặc tả chuẩn | Phạm vi SUC |
| --- | --- | --- |
| **Model Training & Registry** | [`training/suc-spec.md`](training/suc-spec.md) | `SUC-08`, `SUC-09`, `SUC-10`, `SUC-17`, `SUC-27` |
| **Rule Management** | [`rule_management/suc-spec.md`](rule_management/suc-spec.md) | `SUC-11`, `SUC-12`, `SUC-13`, `SUC-14`, `SUC-18` |
| **Batch Detection & Inference** | [`inference/suc-spec.md`](inference/suc-spec.md) | `SUC-15`, `SUC-16`, `SUC-19` |

## Tài liệu liên quan

- Thiết kế luồng người dùng & UI/UX: [`user-flow-and-ui-design.md`](user-flow-and-ui-design.md)
- Thiết kế Plugin Mô hình Học máy: [`training/model_plugin/design.md`](training/model_plugin/design.md)
- Kiến trúc as-built: [`../../arch/modules/training-and-models.md`](../../arch/modules/training-and-models.md), [`../../arch/modules/detection-and-rules.md`](../../arch/modules/detection-and-rules.md)
- Notion gốc: [Đặc tả use case hệ thống](https://app.notion.com/p/c-t-use-case-h-th-ng-3f9b99c6a95080989f01e692219f6fe7)
