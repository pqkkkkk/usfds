# Context Modeling

Parent item: Literature Review (https://app.notion.com/p/Literature-Review-38ab99c6a950801c836ae79daf6eed0e?pvs=21)
Stage: 2. Research
Status: Not started
Task ID: TASK-67

# Mục tiêu

![image.png](Context%20Modeling/image.png)

Bước quan trọng nhất để giải quyết bài toán phát hiện gian lận thẻ tín dụng chính là “Data Representation”. Mục tiêu cốt lõi là làm giàu dữ liệu giao dịch để giải quyết đặc điểm của gian lận thẻ tín dụng là lệch khỏi hành vi, thói quen của khách hàng [Đặc điểm gian lận](https://app.notion.com/p/c-i-m-gian-l-n-3afb99c6a9508073b3cee5f636460bfa?pvs=21). Bài toán cốt lõi trong CCFD không phải "phân loại A hay B" mà là: trong không gian đặc trưng nào thì deviation trở nên tách biệt (separable)? Một cây quyết định hay SVM hoạt động tốt hay tệ phụ thuộc gần như hoàn toàn vào việc dữ liệu đầu vào đã được biểu diễn tốt hay chưa -  bản thân thuật toán phân lớp chỉ là bước cuối, tương đối "rẻ" so với công đoạn tìm ra representation đúng. “Data Representation” trong CCFD được chia thành 2 phương pháp chính:

- Feature Engineering: là các kỹ thuật tạo thêm các đặc trưng cho bộ dữ liệu thủ công nhằm làm giàu dữ liệu
- Representation Learning: Thường sử dụng các mô hình học sâu, mục tiêu là tự động học các biểu dữ liệu phức tạp trong dữ liệu thô

Tuy nhiên, thuật toán phân lớp **không hoàn toàn trở thành thứ yếu** — nó vẫn đóng vai trò quan trọng ở khâu cuối vì 2 lý do gắn liền với 2 thách thức mất cân bằng dữ liệu và concept drift:

1. **Mất cân bằng dữ liệu:** dù representation có tốt đến đâu, decision boundary/threshold vẫn cần được hiệu chỉnh riêng cho lớp thiểu số (VD: dùng resampling, weighted loss, ensemble).
2. **Concept drift:** representation học tốt tại thời điểm t có thể lỗi thời tại t+1; do đó nhiều bài phải kết hợp representation learning với cơ chế thích ứng động (online/incremental learning) ở tầng quyết định.

# Feature engineering

## Hướng tiếp cận

Manual feature engineering (CC-REF-102,CC-REF-104, CC-REF-105, CC-REF-39, CC-REF-32, CC-REF-28, CC-REF-01)

### Phân tích chuỗi thời gian, sự phụ thuộc về mặt thời gian

**Mục tiêu**: Mô hình hóa thói quen, hành vi người dùng

#### Thủ công

**Các kỹ thuật**

- Dùng kỹ thuật time-window để tính toán các giá trị tần suất
- RFM Analysis (19,39,
- Hidden Markov Model (105,
    - HMM được sử dụng để mô hình hóa chuỗi các giao dịch của chủ thẻ để tìm ra thói quen chi tiêu bình thường. Khi có giao dịch mới, mô hình sẽ tính toán xác suất xảy ra giao dịch đó. Nếu xác suất này không đủ cao (dưới một ngưỡng nhất định), giao dịch sẽ bị coi là gian lận (CC-REF-12, CC-REF-23)
    - Ngoài ra, HMM cũng được dùng để tạo ra các đặc trưng lịch sử (HMM-based features). Các đặc trưng này định lượng mức độ tương đồng giữa một chuỗi giao dịch mới quan sát được với các chuỗi giao dịch hợp lệ hoặc gian lận trong quá khứ của chủ thẻ hoặc thiết bị thanh toán (CC-REF-105)
- ARIMA (Autoregressive Integrated Moving Average) (102,
    - **Học hành vi cơ bản ban đầu:** Đầu tiên, mô hình ARIMA sẽ được tinh chỉnh (calibrated) dựa trên số lượng các giao dịch hợp lệ hàng ngày để học thói quen chi tiêu bình thường của chủ thẻ (CC-REF-23)
    - **Dự đoán liên tục:** Thay vì dùng một mô hình tĩnh (chỉ học một lần trên dữ liệu cũ rồi dùng mãi mãi), hệ thống sẽ sử dụng các "khung thời gian trượt" chứa dữ liệu của các giao dịch gần đây nhất để liên tục dự đoán cho các giao dịch trong tương lai (CC-REF-23)
    - **Đánh giá và cảnh báo:** Mô hình tính toán một điểm chuẩn (gọi là Z-score) cho giao dịch mới dựa trên dự đoán từ khung thời gian trượt. Nếu điểm Z-score này lớn hơn một ngưỡng cho phép (tức là giao dịch thực tế sai lệch quá nhiều so với những gì mô hình dự đoán từ dữ liệu gần đây), giao dịch đó sẽ bị đánh dấu là gian lận (CC-REF-23)
- Các phương pháp thống kê nâng cao

⇒ Tóm tắt và phân tích lịch sử giao dịch thành các "hồ sơ tĩnh" (static profiles) phản ánh thói quen, hành vi của người dùng tại một thời điểm nhất định

#### Tự động

**Các kỹ thuật**

- RNN
    - Mô hình hóa chuỗi thời gian: RNN được thiết kế đặc biệt để xử lý luồng dữ liệu chuỗi (ví dụ: lịch sử giao dịch được sắp xếp theo thời gian với các đặc trưng như số tiền, thời gian, vị trí, loại đơn vị chấp nhận thẻ).
    - Trạng thái ẩn (Hidden State): Tại mỗi bước thời gian, RNN duy trì và cập nhật một trạng thái ẩn chứa thông tin từ các đầu vào trong quá khứ. Kiến trúc đệ quy này cho phép mạng lưới nắm bắt các động lực học theo thời gian của người dùng, giúp nhận diện cả những thay đổi hành vi ngắn hạn lẫn thói quen chi tiêu dài hạn (như một đợt mua hàng giá trị cao đột ngột)
    - Hạn chế: RNN truyền thống gặp phải vấn đề "tiêu biến đạo hàm" (vanishing gradient), khiến chúng bị giới hạn thành mạng lưới có "trí nhớ ngắn hạn". Điều này gây khó khăn cho RNN khi phải học và kết nối các chuỗi giao dịch quá dài để tìm ra các mẫu gian lận sâu
- LSTM
    - Khắc phục nhược điểm của RNN: LSTM là một biến thể tiên tiến của RNN, được tạo ra để giải quyết bài toán tiêu biến đạo hàm nhằm ghi nhớ các thông tin phụ thuộc dài hạn.
    - Tế bào bộ nhớ và Cơ chế cổng (Gating Mechanism): Sức mạnh của LSTM nằm ở cấu trúc trạng thái tế bào (cell state) đóng vai trò như một bộ nhớ dài hạn, và luồng thông tin được điều chỉnh chặt chẽ bởi 3 cơ chế cổng:
        - Cổng quên (Forget Gate): Đánh giá hành vi quá khứ và quyết định những thông tin giao dịch cũ hoặc không còn liên quan nào (như các thói quen tiêu dùng đã thay đổi) nên được loại bỏ khỏi bộ nhớ.
        - Cổng đầu vào (Input Gate): Xác định các đặc trưng giao dịch hiện tại (số tiền, thời gian, địa điểm, v.v.) nào là tín hiệu quan trọng cần được thêm vào và cập nhật cho trạng thái tế bào.
        - Cổng đầu ra (Output Gate): Kiểm soát lượng thông tin từ trạng thái tế bào hiện tại sẽ được truyền đi dưới dạng trạng thái ẩn tiếp theo hoặc trở thành dự đoán cuối cùng để xác định xác suất giao dịch có bị gian lận hay không

⇒ Mô hình hóa tính tuần tự (sequential) và sự phụ thuộc theo thời gian (temporal dependencies) giữa các giao dịch liên tiếp.

### Phân tích quan hệ mạng lưới (graph)

**Mục tiêu**: Gian lận thường không thực hiện riêng lẻ mà có tính tổ chức ⇒ Khai thác các mối quan hệ (relationships), sự liên kết và tương tác phức tạp giữa các thực thể (như khách hàng, thẻ, thiết bị, người bán) để tìm ra các mạng lưới hoặc tổ chức gian lận

#### Thủ công

**Các kỹ thuật**

- Graph database. Viết các câu truy vấn thủ công hoặc các thuật toán đồ thị để tính toán các đặc trưng cụ thể (như PageRank, Community Detection)
    - Một số thuật toán
        - Community Detection (44,110): gom cụm các tài khoản, người dùng liên kết chặt chẽ từ đó phát hiện các nhóm gian lận
        - PageRank (44,108): Đánh giá mức độ quan trọng của một nút (node) trong mạng lưới không chỉ dựa vào số lượng liên kết (edges) trỏ đến nó, mà còn dựa vào *chất lượng* (độ quan trọng) của các nút đang trỏ đến nó.
        - Degree Centrality Algorithm (108)
        - Label Propagation Algorithm (LPA) (108)
    - Một số đặc trưng
        - `Community_Size` (Kích thước cộng đồng)**:** Tổng số lượng thẻ/thiết bị/tài khoản nằm trong cùng một cụm ⇒ Một người dùng bình thường thường chỉ có liên kết với 1-2 thiết bị hoặc địa chỉ. Nếu một cụm có tới 50 thẻ tín dụng cùng chia sẻ một địa chỉ IP hoặc MAC Address, đặc trưng `Community_Size = 50` này sẽ là một tín hiệu cảnh báo đỏ cho mô hình.
        - `Community_Fraud_Ratio` (Tỷ lệ gian lận trong cộng đồng): ****Tỷ lệ phần trăm các thẻ đã bị đánh dấu là "gian lận" (Blacklist) trong cùng một cụm ⇒ Nếu thẻ A mới tinh, chưa có lịch sử xấu, nhưng thuật toán xếp nó vào một cộng đồng có `Community_Fraud_Ratio = 80%`, hệ thống sẽ tự động gán rủi ro cao cho thẻ A.

⇒ Phụ thuộc vào chuyên gia, kiến thức chuyên môn nghiệp vụ để định các logic truy vấn, thuật toán đồ thị để tính toán đặc trưng

#### Tự động

**Các kỹ thuật**

- Sử dụng các thuật toán học máy GNN để tự động học, phân tích mối quan hệ mạng lưới

⇒ Mô hình tự động học mối quan hệ, không cần sự can thiệp của con người

## Danh sách đặc trưng

- CC-REF-01
    - **Mức chi tiêu trung bình của khách hàng mỗi tuần hoặc mỗi tháng** (Average expenditure of the customer every week/month).
    - **Số lượng giao dịch trung bình mỗi ngày** (Average number of transactions per day).
    - **Số lượng giao dịch trung bình trong cùng một cửa hàng/tiệm** (Average number of transactions in the same shop).
    - **Giá trị giao dịch trung bình** (Average transaction amount).
    - **Vị trí của các giao dịch mua hàng trước đó** (Location of the previous purchases).
    - **Các thuộc tính bổ sung được trích xuất từ mạng lưới xã hội** kết nối giữa chủ thẻ và các thương gia hoặc cửa hàng (Informative features extracted from the social networks connecting the cardholders with merchants/shops)
- CC-REF-18
    - **Txn amount over month**: Số tiền chi tiêu trung bình trên mỗi giao dịch trong khoảng thời gian 30 ngày tính đến thời điểm giao dịch hiện tại xảy ra.
    - **Average over 3 months**: Số tiền chi tiêu trung bình trong vòng 1 tuần tính trong suốt 3 tháng gần nhất.
    - **Average daily over month**: Số tiền chi tiêu trung bình mỗi ngày trong vòng 30 ngày trước khi giao dịch diễn ra.
    - **Amount merchant type over month**: Số tiền trung bình chi tiêu mỗi ngày trong vòng 30 ngày tính đến giao dịch hiện tại trên cùng loại loại hình thương mại (merchant type) với giao dịch hiện tại.
    - **Number merchant type over month**: Tổng số lượng giao dịch được thực hiện với cùng một loại hình thương mại trong vòng 30 ngày trước đó.
    - **Amount merchant type over 3 months**: Số tiền chi tiêu trung bình hàng tuần trong vòng 3 tháng trước trên cùng loại loại hình thương mại với giao dịch hiện tại.
    - **Amount same day**: Tổng số tiền đã chi tiêu trong cùng một ngày tính đến trước khi thực hiện giao dịch hiện tại.
    - **Number same day**: Tổng số lượng giao dịch được thực hiện trong cùng một ngày tính đến trước khi xảy ra giao dịch hiện tại.
    - **Amount same merchant**: Số tiền trung bình chi tiêu mỗi ngày trong khoảng thời gian 30 ngày đối với tất cả các giao dịch được thực hiện tại cùng một nhà bán hàng (merchant) cụ thể như giao dịch này.
    - **Number same merchant**: Tổng số lượng giao dịch được thực hiện với cùng một nhà bán hàng đó trong tháng trước.
    - **Amount currency type over month**: Số tiền trung bình chi tiêu mỗi ngày trong vòng 30 ngày đối với tất cả các giao dịch sử dụng cùng loại tiền tệ với giao dịch hiện tại.
    - **Number currency type over month**: Tổng số lượng giao dịch sử dụng cùng một loại tiền tệ trong vòng 30 ngày trước đó.
    - **Amount same country over month**: Số tiền trung bình chi tiêu trong vòng 30 ngày đối với tất cả các giao dịch được thực hiện tại cùng một quốc gia với giao dịch hiện tại.
    - **Number same country over month**: Tổng số lượng giao dịch được thực hiện tại cùng một quốc gia trong vòng 30 ngày trước khi giao dịch này diễn ra.**1**
    - **Amount merchant over 3 months**: Số tiền chi tiêu trung bình hàng tuần trong vòng 3 tháng trước tại cùng một nhà bán hàng cụ thể như giao dịch này.
    - **Number merchant over 3 months**: Tổng số lượng giao dịch được thực hiện với cùng một nhà bán hàng đó trong vòng 3 tháng trước
- CC-REF-19
- CC-REF-28
- CC-REF-39
    - Tổng số tiền giao dịch đối với cùng một quốc gia và cùng một loại giao dịch trong 24 giờ qua.
    - Tổng số tiền giao dịch trong 24 giờ qua.
    - Số lượng giao dịch có cùng quốc gia và cùng loại giao dịch trong 24 giờ qua.
    - Số lượng giao dịch trong 24 giờ qua
    - Số lượng giao dịch có cùng loại thiết bị trong 24 giờ qua.
    - Số lượng giao dịch có cùng mã danh mục người bán - MCC (merchant category code) trong 24 giờ qua.
    - Tổng số tiền giao dịch có cùng loại thiết bị trong 24 giờ qua.
    - Tổng số tiền giao dịch có cùng mã MCC trong 24 giờ qua

# Representation Learning

- LSTM, CNN, GRU để học sự phụ thuộc theo thời gian giữa các giao dịch
- ARIMA, HMM để học các hành vi thói quen của khách hàng
- GNN để học các mối quan hệ phức tạp giữa các thực thể
- Autoencoder, học tự giám sát để tự động học đặc trưng từ dữ liệu thô