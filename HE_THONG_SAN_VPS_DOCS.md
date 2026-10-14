# TÀI LIỆU HỆ THỐNG TỰ ĐỘNG SĂN VPS ORACLE CLOUD ALWAYS FREE (ARM 24/7)

Tài liệu này lưu lại toàn bộ kiến trúc, công cụ và quy trình vận hành hệ thống săn VPS tự động để bạn dễ dàng tra cứu, quản trị và tái sử dụng sau này.

---

## 1. MỤC TIÊU VÀ BỐI CẢNH
- **Mục tiêu:** Tạo máy ảo Oracle Cloud Always Free cấu hình tối đa:
  - **Shape:** `VM.Standard.A1.Flex` (Ampere ARM)
  - **Phần cứng:** 4 OCPU, 24 GB RAM, 200 GB Boot Volume (ổ cứng SSD)
  - **Hệ điều hành:** Ubuntu 24.04 LTS (Minimal ARM64)
  - **Khu vực:** Tokyo (`ap-tokyo-1` / `EhRi:AP-TOKYO-1-AD-1`)
- **Vấn đề gặp phải:** Khi tạo thủ công trên web console bị báo lỗi *'Out of host capacity'* (hết slot phần cứng tạm thời).
- **Giải pháp:** Sử dụng script Python gửi API request liên tục 24/24 trên Cloud cho đến khi có người nhả tài nguyên thì script sẽ lập tức chiếm lấy slot đó.

---

## 2. DANH SÁCH CÁC CÔNG CỤ ĐÃ SỬ DỤNG

| Công cụ / Nền tảng | Vai trò trong hệ thống | Lý do sử dụng & Đường dẫn |
| :--- | :--- | :--- |
| **Python 3 & OCI SDK** | Ngôn ngữ & Thư viện lõi | Kết nối trực tiếp vào API chính thức của Oracle Cloud Infrastructure (OCI). |
| **GitHub** | Lưu trữ mã nguồn & CI/CD | Repository: `https://github.com/son1999tmgl/oracle-freetier-instance-creation`. |
| **Render.com (Web Service)** | Máy chủ chạy script 24/24 | Miễn phí, tự động pull code từ GitHub khi có commit mới. Dashboard: `https://dashboard.render.com`. |
| **Dummy HTTP Server (Port 10000)** | Duy trì trạng thái Live trên Render | Tích hợp sẵn trong `main.py` để Render ping Health Check thành công. |
| **UptimeRobot** | Giữ Render không bị ngủ (Prevent Spin Down) | Ping định kỳ mỗi 5 phút vào URL Render để máy chủ thức vĩnh viễn 24/7. Dashboard: `https://uptimerobot.com`. |

---

## 3. LUỒNG HOẠT ĐỘNG TOÀN HỆ THỐNG (24/24)

1. **Lưu trữ & Triển khai**: GitHub lưu trữ toàn bộ code, OCI config và API key bí mật.
2. **Khởi chạy trên Render**: Render.com tự động build và chạy lệnh `python3 -u main.py`. Cổng HTTP `10000` được mở để tiếp nhận truy cập.
3. **Cơ chế giữ máy thức 24/7 (UptimeRobot)**:
   - Gói Free của Render sẽ tự động ngủ sau 15 phút nếu không ai truy cập.
   - UptimeRobot được cấu hình tự động "gõ cửa" (gửi HTTP GET) vào địa chỉ Render của bạn **mỗi 5 phút một lần**.
   - Server Render nhận tín hiệu, trả về `200 OK` ("OCI Instance Hunter is Running 24/7 on Render!"), nhờ đó duy trì trạng thái thức vĩnh viễn 24/24 mà bạn không cần mở máy tính.
4. **Vòng lặp săn máy**:
   - Cứ mỗi ~60 giây, script gửi một request tạo máy tới cụm Tokyo AD-1 của Oracle.
   - Nếu gặp lỗi hết slot (`HTTP 500`) hoặc gửi quá nhanh (`HTTP 429`), script tự động lùi lại 60-66s rồi tiếp tục kiên trì thử lại.
5. **Khi có máy**:
   - Ngay khi có người nhả slot, máy ảo 4 OCPU / 24GB RAM sẽ được tạo ngay lập tức.
   - Script ghi nhận log `[THANH CONG]`, tạo file `INSTANCE_CREATED` và tự động dừng lại để không tạo thừa máy.

---

## 4. CÁCH KIỂM TRA VÀ TRUY VẤN

1. **Xem nhật ký săn máy**: Vào [Render Dashboard](https://dashboard.render.com/) -> Chọn Web Service -> Tab **Logs**.
2. **Xem trạng thái ping**: Vào [UptimeRobot](https://uptimerobot.com/) -> Kiểm tra Monitor đang ở trạng thái **Up (Xanh)**.
3. **Khi săn thành công**:
   - Vào [Oracle Console](https://cloud.oracle.com/compute/instances) (Region Tokyo) để lấy Public IP.
   - Mở terminal tại thư mục này trên máy tính và SSH:
     ```bash
     ssh -i id_rsa ubuntu@<IP_PUBLIC_CUA_MAY_AO>
     ```
   - Cài đặt môi trường làm việc trên VPS:
     ```bash
     sudo apt update && sudo apt upgrade -y
     ```
