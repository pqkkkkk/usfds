# Thiết kế kiến trúc mức cài đặt

# Nguyên lý thiết kế

Áp dụng nguyên lý thiết kế **“Clean Architecture”.** Tách biệt các layer cốt lõi:

- Core Engine (`usfds-core`): Logic nghiệp vụ cốt lõi của ứng dụng. Ở layer này, cần thiết kế, các interface để định nghĩa rõ các hàm xử lý, cấu trúc input, output của từng hàm
- Presentation Layer: tầng giao diện người dùng của ứng dụng
    - Front-end (`usfds-web`): Phiên bản giao diện người dùng trên web. Tập trung vào xử lý UI/UX, gọi đến REST APIs cung cấp bởi server để yêu cầu thực hiện các chức năng cốt lõi
    - Back-end (`usfds-server`): Server back-end cho client-server version. Import trực tiếp core engine để xử lý các chức năng. Cung cấp các REST APIs cho web client
- Infrastructure Layer (`usfds-infra`): Là các logic cài đặt cấu hình kết nối, tương tác với hạ tầng của ứng dụng như database, file storage, model registry

# Cấu trúc source code

Sử dụng dependency management Poetry

Thay vì chỉ có 1 file quản lý dependency `requirements.txt` nằm ở thư mục gốc chứa chung mọi thứ, mỗi module sẽ là một project độc lập có file cấu hình `pyproject.toml` riêng và một **Môi trường ảo (Virtualenv) độc lập**

```
usfds/
│
├── usfds-core/
│   ├── pyproject.toml  (Khai báo: pydantic, xgboost, pandas)
│   └── src/
│
├── usfds-adapter/
│   ├── pyproject.toml  (Khai báo: psycopg2, boto3. Import usfds-core)
│   └── src/
│
└── usfds-server/
    ├── pyproject.toml  (Khai báo: fastapi, uvicorn. Import usfds-core, usfds-infra)
    └── src/
```

# Core Engine (`usfds-core`)

> *Định nghĩa, cài đặt các logic nghiệp vụ cho các chức năng cốt lõi của hệ thống*
> 

## Entity Layer

Các entity ở module `usfds-core` nên là các **“pure entity”** nghĩa là nó không phụ thuộc vào bất kì thư viện bên thứ 3 nào.

Sử dụng `dataclasses` để định nghĩa các entity

# REST API (`usfds-server`)
> *Cung cấp các API endpoint cho client. Import trực tiếp các hàm service ở `usfds-core` và expose nó ra từng endpoint tương ứng. Cộng thêm các logic ở tầng HTTP là định nghĩa schema cho từng endpoint (route, request, response)*

# UI (`usfds-web`)
> Ứng dụng React

# Infrastructure (`usfds-infra`)

> *Cài đặt các logic tương tác với các dịch vụ hạ tầng (chủ yếu là database và storage engine)*
> 

Implement các interface đã được nghĩa ở `usfds-core`. 

## Database

- Định nghĩa các Data Model**,** là các class kế thừa từ ORM (như SQLAlchemy). Chứa cấu trúc bảng, khóa ngoại, index.
- Sử dụng Repository Pattern làm cầu nối (Data Mapper): Để entity (ở core) và data model không trực tiếp dính líu đến nhau, chúng ta tạo ra một tầng trung gian là `Repository`. Tầng này có trách nhiệm chuyển đổi dữ liệu từ ORM Model sang Domain Entity (khi đọc từ DB) và ngược lại (khi ghi xuống DB)

```python
from typing import Optional

class UserRepository:
    def __init__(self, db_session):
        self.db_session = db_session

    def get_by_id(self, user_id: int) -> Optional[UserEntity]:
        # 1. Truy vấn bằng ORM Model
        user_model = self.db_session.query(UserModel).filter_by(id=user_id).first()
        
        if not user_model:
            return None
            
        # 2. Ánh xạ (Map) sang Domain Entity và trả về cho Use Case
        return UserEntity(
            id=user_model.id,
            username=user_model.username,
            email=user_model.email,
            is_active=user_model.is_active
        )

    def save(self, user_entity: UserEntity) -> None:
        # 1. Ánh xạ từ Domain Entity sang ORM Model
        user_model = UserModel(
            id=user_entity.id,
            username=user_entity.username,
            email=user_entity.email,
            is_active=user_entity.is_active
        )
        
        # 2. Lưu xuống Database
        self.db_session.merge(user_model) # Dùng merge để update hoặc insert
        self.db_session.commit()
```