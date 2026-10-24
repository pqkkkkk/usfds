# Nền tảng Thiết kế Giao diện (UI/UX Design Foundation)

Tài liệu này định nghĩa hệ thống thiết kế cơ sở (**Design System Foundations**), cấu trúc bố cục chuẩn (**Global Layout Architecture**), kiến trúc Design Tokens 3 lớp, và các chuẩn mực tương tác/khả năng tiếp cận (**Accessibility & Interaction Guidelines**) cho toàn bộ hệ thống **USFDS** (Unified System for Fraud Detection & Scoring).

> Tài liệu được xây dựng dựa trên tiêu chuẩn thiết kế Fintech/Data-Dense từ bộ công cụ `ui-ux-pro-max` và kiến trúc `design-system` (Three-Layer Token Architecture).

---

## 1. Triết lý Thiết kế & Định hướng Thị giác (Visual Direction)

### 1.1. Hồ sơ Thiết kế (Design Profile)
- **Phong cách chủ đạo:** **Dark Mode (OLED / Midnight Slate)** kết hợp **Emerald/Blue Accents**.
- **Ngữ cảnh sử dụng:** Nền tảng phân tích tài chính và phát hiện gian lận phức tạp; người dùng (Data Scientist, Fraud Analyst) làm việc liên tục nhiều giờ với bảng dữ liệu lớn, ma trận nhầm lẫn (Confusion Matrix), và cây phả hệ (DAG).
- **Design Dials (Thang đo chuẩn hóa):**
  - **Variance (6/10 - Balanced / Modern):** Cân đối giữa tính tin cậy của doanh nghiệp tài chính (Enterprise Gateway) và giao diện công nghệ AI hiện đại.
  - **Density (8/10 - Dense / Dashboard):** Mật độ dữ liệu cao, khoảng cách gọn gàng (8px/12px padding), giảm thiểu khoảng trắng vô nghĩa, tối ưu không gian hiển thị bảng và đồ thị.
  - **Motion (4/10 - Subtle Micro-interactions):** Chuyển động vi mô nhẹ nhàng (150ms - 250ms), tuyệt đối không lạm dụng hiệu ứng làm chậm thao tác người dùng; tôn trọng thiết lập `prefers-reduced-motion`.

### 1.2. Nguyên tắc Thiết kế Cốt lõi
1. **High Contrast & Low Eye-Strain:** Tối ưu hóa màu nền tối sâu (`#020617` / `#0B0F19`) giúp bảo vệ thị lực và làm nổi bật các điểm dị biệt gian lận (Anomalies).
2. **Dual-Encoding for Safety (Mã hóa kép):** Tuyệt đối không dùng màu sắc làm tín hiệu duy nhất để biểu thị trạng thái (chống mù màu). Mọi trạng thái quan trọng (`PASSED`, `WARNING`, `FAILED`) luôn đi kèm Icon SVG chuẩn hóa và nhãn văn bản.
3. **No Emoji as UI Icons:** Toàn bộ biểu tượng trong giao diện phải sử dụng thư viện Vector SVG chuẩn hóa (`Lucide-React` hoặc `Heroicons`), có `aria-hidden="true"` hoặc nhãn hỗ trợ đọc màn hình.
4. **Predictable & Traceable:** Mọi tác vụ chạy ngầm phải có phản hồi tiến trình rõ ràng (Non-blocking); mọi phiên bản dữ liệu/mô hình đều liên kết với cây Lineage bất biến.

---

## 2. Kiến trúc Design Tokens 3 lớp (Three-Layer Token Architecture)

Áp dụng chuẩn kiến trúc: `Primitive Tokens` $\to$ `Semantic Tokens` $\to$ `Component Tokens`.

```
┌────────────────────────────────────────────────────────┐
│  Component Tokens (Tầng 3: Biến cho từng component)    │
│  --stepper-node-size, --table-row-height, --dag-border │
├────────────────────────────────────────────────────────┤
│  Semantic Tokens (Tầng 2: Ý nghĩa nghiệp vụ & Theme)   │
│  --color-background, --color-surface, --color-accent   │
├────────────────────────────────────────────────────────┤
│  Primitive Tokens (Tầng 1: Giá trị vật lý thô)         │
│  --color-slate-900, --color-blue-500, --space-4        │
└────────────────────────────────────────────────────────┘
```

### 2.1. Tầng 1: Primitive Tokens (Giá trị thô cơ sở)

```css
:root {
  /* Slate Scale (Nền và chữ) */
  --primitives-slate-950: #020617;
  --primitives-slate-900: #0F172A;
  --primitives-slate-850: #111827;
  --primitives-slate-800: #1E293B;
  --primitives-slate-700: #334155;
  --primitives-slate-600: #475569;
  --primitives-slate-500: #64748B;
  --primitives-slate-400: #94A3B8;
  --primitives-slate-300: #CBD5E1;
  --primitives-slate-100: #F1F5F9;
  --primitives-slate-50:  #F8FAFC;

  /* Accent & Functional Colors */
  --primitives-blue-500:    #3B82F6;
  --primitives-blue-600:    #2563EB;
  --primitives-emerald-400: #34D399;
  --primitives-emerald-500: #10B981;
  --primitives-amber-400:   #FBBF24;
  --primitives-amber-500:   #F59E0B;
  --primitives-red-500:     #EF4444;
  --primitives-red-600:     #DC2626;
  --primitives-purple-400:  #A78BFA;
  --primitives-purple-500:  #8B5CF6;

  /* 4px Base Spacing Scale */
  --space-0-5: 0.125rem; /* 2px */
  --space-1:   0.25rem;  /* 4px */
  --space-1-5: 0.375rem; /* 6px */
  --space-2:   0.5rem;   /* 8px */
  --space-3:   0.75rem;  /* 12px */
  --space-4:   1rem;     /* 16px */
  --space-5:   1.25rem;  /* 20px */
  --space-6:   1.5rem;   /* 24px */
  --space-8:   2rem;     /* 32px */
  --space-10:  2.5rem;   /* 40px */
  --space-12:  3rem;     /* 48px */

  /* Border Radii */
  --radius-xs: 2px;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-full: 9999px;

  /* Elevation Shadows (Dark-optimized) */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.5), 0 2px 4px -2px rgba(0, 0, 0, 0.5);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.6), 0 4px 6px -4px rgba(0, 0, 0, 0.6);
  --shadow-glow-blue: 0 0 15px rgba(59, 130, 246, 0.25);
  --shadow-glow-green: 0 0 15px rgba(34, 197, 94, 0.25);

  /* Transitions */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 200ms cubic-bezier(0.4, 0, 0.2, 1);
}
```

---

### 2.2. Tầng 2: Semantic Tokens (Ý nghĩa nghiệp vụ & Theme)

```css
:root {
  /* Surface & Background */
  --color-background:         var(--primitives-slate-950); /* #020617 - OLED Black */
  --color-surface:            var(--primitives-slate-900); /* #0F172A - Panel & Card */
  --color-surface-elevated:   var(--primitives-slate-800); /* #1E293B - Modal, Dropdown */
  --color-surface-hover:      rgba(255, 255, 255, 0.04);
  
  /* Borders */
  --color-border:             var(--primitives-slate-700); /* #334155 */
  --color-border-subtle:      rgba(255, 255, 255, 0.08);
  --color-border-focus:       var(--primitives-blue-500);

  /* Typography / Foreground */
  --color-text-primary:       var(--primitives-slate-50);  /* #F8FAFC - Tiêu đề, số liệu */
  --color-text-secondary:     var(--primitives-slate-400); /* #94A3B8 - Nhãn, mô tả */
  --color-text-muted:         var(--primitives-slate-500); /* #64748B - Placeholder */
  --color-text-inverse:       var(--primitives-slate-950);

  /* Brand Accents & Interactive */
  --color-primary:            var(--primitives-blue-500);  /* #3B82F6 - Primary Button / Stepper */
  --color-primary-hover:      var(--primitives-blue-600);
  --color-accent:             var(--primitives-emerald-500);/* #10B981 - Success / Run Action */
  
  /* Status Feedback (WCAG AA Compliant) */
  --color-success:            var(--primitives-emerald-400); /* #34D399 */
  --color-success-bg:         rgba(16, 185, 129, 0.12);
  --color-warning:            var(--primitives-amber-400);   /* #FBBF24 */
  --color-warning-bg:         rgba(245, 158, 11, 0.12);
  --color-danger:             var(--primitives-red-500);     /* #EF4444 */
  --color-danger-bg:          rgba(239, 68, 68, 0.12);

  /* Pipeline Stage Tokens (Nhận diện vòng đời dữ liệu FDS) */
  --stage-raw-color:          var(--primitives-blue-500);
  --stage-raw-bg:             rgba(59, 130, 246, 0.12);
  --stage-mapped-color:       var(--primitives-emerald-400);
  --stage-mapped-bg:          rgba(16, 185, 129, 0.12);
  --stage-preprocessed-color: var(--primitives-purple-400);
  --stage-preprocessed-bg:    rgba(139, 92, 246, 0.12);
  --stage-trained-color:      var(--primitives-amber-400);
  --stage-trained-bg:         rgba(245, 158, 11, 0.12);

  /* Focus Indicator Ring */
  --focus-ring: 0 0 0 2px var(--color-background), 0 0 0 4px var(--color-primary);
}
```

---

### 2.3. Tầng 3: Component Tokens (Tokens định danh thành phần)

```css
:root {
  /* Layout Shell */
  --topbar-height:            56px;
  --sidebar-width:            240px;
  --sidebar-collapsed-width:  64px;
  --bottombar-height:         28px;

  /* Data Table */
  --table-header-height:      38px;
  --table-row-height:         42px;
  --table-row-hover-bg:       rgba(255, 255, 255, 0.03);
  --table-border-color:       var(--color-border-subtle);

  /* Workspace Stepper */
  --stepper-node-size:        28px;
  --stepper-track-thickness:  2px;

  /* DAG Lineage Canvas */
  --dag-canvas-bg:            #050811;
  --dag-node-min-width:       200px;
  --dag-node-radius:          var(--radius-lg);
  --dag-edge-stroke:          var(--primitives-slate-600);
  --dag-edge-active-stroke:   var(--color-primary);
}
```

---

## 3. Hệ thống Typography & Phông chữ Chuyên biệt

Hệ thống kết hợp **2 họ phông chữ bổ trợ nhau**:
1. **Giao diện & Văn bản chung (UI Copy):** `Inter`, `-apple-system`, `sans-serif`.
   - Độ rõ nét vượt trội ở kích thước nhỏ (11px - 13px), hỗ trợ hiển thị tiếng Việt chuẩn UTF-8.
2. **Số liệu tài chính, Checksum, Mã định danh & Schema (Tabular Code Font):** `Fira Code` hoặc `JetBrains Mono`.
   - **Bắt buộc kích hoạt:** `font-variant-numeric: tabular-nums;` để các con số căn thẳng hàng tuyệt đối trong bảng phân tích tài chính.

### Thang kích thước Typography (Type Scale)

| Token | Size / Line-height | Weight | Ứng dụng |
| :--- | :--- | :--- | :--- |
| `text-display` | 24px / 32px | 700 (Bold) | Tiêu đề trang chính (Page Title) |
| `text-heading-lg`| 18px / 24px | 600 (Semi-bold) | Tiêu đề phân khu, Modal Header |
| `text-heading-md`| 15px / 20px | 600 (Semi-bold) | Tiêu đề Card, Drawer Inspector Header |
| `text-body` | 13px / 18px | 400 (Regular) | Nội dung bảng, mô tả, form text |
| `text-caption` | 11px / 16px | 500 (Medium) | Meta labels, Tag badge, Header bảng (Uppercase) |
| `text-code` | 12px / 16px | 500 (Mono) | UUID, SHA-256 Checksum, Tên cột canonical (`event_id`) |

---

## 4. Kiến trúc Bố cục Toàn cục (Global Shell Architecture)

```
+--------------------------------------------------------------------------------------------------------------------+
| TOPBAR (56px) - Cố định                                                                                            |
| [Shield Logo] USFDS | [Project Selector: "E-Commerce Fraud 2026" v] | [Omnisearch (Ctrl+K)] | [Worker: OK] [Noti] [DS]   |
+---------------+----------------------------------------------------------------------------------------------------+
| SIDEBAR       | MAIN VIEWPORT (Tự động scroll độc lập)                                                             |
| (240px)       |                                                                                                    |
|               | [Breadcrumb / Page Action Toolbar]                                                                 |
| - Data Hub    |----------------------------------------------------------------------------------------------------|
| - Detection   |                                                                                                    |
| - Rules       |  NỘI DUNG WORKSPACE                                                                                |
| - Investigate |                                                                                                    |
| - Reports     |                                                                                                    |
|               |                                                                                                    |
| [Collapse <]  |                                                                                                    |
+---------------+----------------------------------------------------------------------------------------------------+
| BOTTOM STATUS BAR (28px) - Worker Engine: Healthy | Latency: 12ms | Storage: 4.2 GB / 50 GB | Active Jobs: 0           |
+--------------------------------------------------------------------------------------------------------------------+
```

### 4.1. Top Navigation Bar
- **Project Context Switcher:** Chuyển đổi ngữ cảnh làm việc giữa các bài toán khác nhau. Toàn bộ dữ liệu dưới thanh này đều chịu ràng buộc của Project ID được chọn.
- **Global Omnisearch (Phím tắt `Ctrl + K` hoặc `Cmd + K`):** Hỗ trợ tìm kiếm tức thì Dataset, Model, Rule, hoặc Transaction ID.
- **System Health Indicator:** Chấm trạng thái xanh/vàng/đỏ của Engine ngầm (`usfds-core` service).

### 4.2. Side Navigation Bar
- Có khả năng thu gọn (Collapse: 240px $\to$ 64px) để mở rộng diện tích làm việc cho bảng dữ liệu lớn hoặc đồ thị Lineage DAG.
- Phân nhóm chức năng logic rõ ràng theo vòng đời: **Data Preparation** $\to$ **Detection & Modeling** $\to$ **Investigation** $\to$ **Reporting & Insights**.

---

## 5. Quy chuẩn Chi tiết cho các Mẫu Giao diện Dùng chung (Component Specifications)

### 5.1. Workspace Stepper (Điều hướng Pipeline Tuyến tính & Rẽ nhánh)
- **Mục đích:** Hướng dẫn người dùng qua các bước chuẩn bị dữ liệu (`RAW` $\to$ `MAPPED` $\to$ `PRE_PROCESSED`).
- **Các trạng thái (States):**
  - **`Completed`:** Vòng tròn xanh lục với Icon Check (`✓`), click được để xem lại kết quả bước trước.
  - **`Active`:** Vòng tròn viền xanh dương phát sáng (`box-shadow: var(--shadow-glow-blue)`), chứa số bước hiện tại.
  - **`Locked`:** Màu xám mờ (`--primitives-slate-700`), `cursor: not-allowed`.
  - **`Forked Badge`:** Khi người dùng rẽ nhánh từ một node cũ, trên thanh Stepper hiển thị nhãn phụ: *"🌿 Branch: [Branch Name] (Forked from Artifact #X)"*.

### 5.2. Interactive High-Density Data Grid (Bảng dữ liệu mật độ cao)
- **Sticky Column:** Cột đầu tiên (Transaction ID hoặc Dataset Name) luôn cố định khi cuộn ngang màn hình.
- **Column Header Health Bar:** Phía dưới tên mỗi cột trong bảng có một thanh mini bar cao 3px:
  - Màu xanh lục: Tỷ lệ giá trị hợp lệ (`100% - null%`).
  - Màu xám/đỏ: Tỷ lệ ô trống khuyết thiếu (`null%`).
- **Virtual Scrolling:** Bắt buộc áp dụng để render mượt mà danh sách hàng nghìn dòng dữ liệu.

### 5.3. Interactive Lineage Canvas (Sơ đồ phả hệ DAG)
- Dựng trên Canvas/SVG tương tác:
  - Hỗ trợ chuột: Zoom in/out bằng con lăn, kéo rê (Pan) vùng hiển thị, phím tắt `Space + Drag`.
  - **Node Selection:** Khi click vào một node, node đó nhận viền sáng (`--border-focus`), đồng thời kích hoạt Drawer Inspector bên phải.
  - **Edge Styling:** Đường nối cong mượt (Bézier curves) có hướng mũi tên chỉ rõ dòng chảy dữ liệu.

### 5.4. Slide-over Inspector Drawer (Bảng chi tiết bên phải)
- Chiều rộng: 480px - 560px, trượt ra từ bên phải màn hình.
- Không che lấp toàn màn hình giúp người dùng vừa quan sát cây phả hệ/bảng dữ liệu vừa đối chiếu thông số chi tiết.
- Chia thành các Tab chuẩn hóa: `Overview`, `Data Profiling`, `Validation Report`, `Configuration JSON`.

### 5.5. Async Task Progress & Toast Feedback
- **Non-blocking UX:** Khi thực hiện tác vụ nặng (Feature Engineering hoặc Huấn luyện mô hình), hệ thống hiển thị thanh tiến trình nhỏ cố định ở góc dưới bên phải màn hình.
- Người dùng có thể chuyển sang màn hình khác làm việc mà không bị gián đoạn.
- Khi tác vụ hoàn tất: Bắn thông báo Toast kèm nút hành động **`[ View Result ➔ ]`**.

---

## 6. Hướng dẫn Khả năng Tiếp cận (Accessibility & WCAG 2.1 AA)

Để đảm bảo hệ thống đạt chuẩn doanh nghiệp và vượt qua các bài kiểm thử UX:

1. **Tỷ lệ Tương phản Màu (Contrast Ratio):**
   - Văn bản chuẩn (`--color-text-primary` trên `--color-surface`): Đạt tỷ lệ tối thiểu **7:1** (vượt chuẩn AAA).
   - Văn bản phụ (`--color-text-secondary` trên `--color-surface`): Đạt tỷ lệ tối thiểu **4.5:1** (chuẩn AA).
2. **Keyboard Navigation (Điều hướng bằng bàn phím):**
   - Mọi nút, liên kết, ô nhập liệu, và node trên DAG phải có thể truy cập bằng phím `Tab`.
   - Vòng chỉ thị tiêu điểm (`:focus-visible`): Sử dụng `--focus-ring` viền kép rõ ràng, không được dùng `outline: none` mà không có viền thay thế.
3. **Giảm thiểu Chuyển động (Motion Safety):**
   ```css
   @media (prefers-reduced-motion: reduce) {
     *, ::before, ::after {
       animation-duration: 0.01ms !important;
       transition-duration: 0.01ms !important;
     }
   }
   ```
4. **Hỗ trợ Screen Reader:**
   - Các bảng dữ liệu phức tạp phải có `caption`, các cột có thuộc tính `scope="col"`.
   - Các thanh tiến trình phải gắn `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`.
