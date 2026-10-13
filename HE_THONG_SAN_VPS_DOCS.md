# TÀI LIỆU HỆ THỐNG TỰ ĐỘNG SĂN VPS ORACLE CLOUD ALWAYS FREE (ARM 24/7)

Tài liệu này lưu lại toàn bộ kiến trúc, công cụ và quy trình vận hành hệ thống săn VPS tự động để bạn dễ dàng tra cứu, quản trị và tái sử dụng sau này.

---

## 1. MỤC TIÊU VÀ BỐI CẢNH
- **Mục tiêu:** Tạo máy ảo Oracle Cloud Always Free cấu hình tối đa:
  - **Shape:** VM.Standard.A1.Flex (Ampere ARM)
  - **Phần cứng:** 4 OCPU, 24 GB RAM, 200 GB Boot Volume (ổ cứng SSD)
  - **Hệ điều hành:** Ubuntu 24.04 LTS (Minimal ARM64)
  - **Khu vực:** Tokyo (ap-tokyo-1 / EhRi:AP-TOKYO-1-AD-1)
- **Vấn đề gặp phải:** Khi tạo thủ công trên web console bị báo lỗi 'Out of host capacity' (hết slot phần cứng tạm thời).
- **Giải pháp:** Sử dụng script Python gửi API request liên tục 24/24 trên Cloud cho đến khi có người nhả tài nguyên thì script sẽ lập tức chiếm lấy slot đó.

---

## 2. DANH SÁCH CÁC CÔNG CỤ ĐÃ SỬ DỤNG

| Công cụ / Nền tảng | Vai trò trong hệ thống | Lý do sử dụng |
| :--- | :--- | :--- |
| **Python 3 & OCI SDK** | Ngôn ngữ & Thư viện lõi | Kết nối trực tiếp vào API chính thức của Oracle Cloud Infrastructure (OCI). |
| **GitHub** | Lưu trữ mã nguồn | Quản lý source code, private key, cấu hình và kích hoạt CI/CD. |
| **Render.com (Web Service)** | Máy chủ chạy script 24/24 | Miễn phí, tự động pull code từ GitHub khi có commit mới, tự cài đặt thư viện qua requirements.txt. |
| **Dummy HTTP Server (Port 10000)** | Duy trì trạng thái Live trên Render | Tích hợp sẵn trong main.py bằng thư viện http.server để Render ping Health Check thành công. |
| **UptimeRobot** | Giữ Render không bị ngủ (Prevent Spin Down) | Gói Free Web Service của Render sẽ ngủ sau 15 phút nếu không ai truy cập. UptimeRobot ping mỗi 5 phút giúp Render thức vĩnh viễn 24/7. |

---

## 3. LUỒNG HOẠT ĐỘNG TOÀN HỆ THỐNG

1. GitHub lưu toàn bộ mã nguồn, cấu hình và key API bí mật.
2. Render.com tự động kéo code từ GitHub, mở cổng HTTP 10000 để duy trì trạng thái Live, đồng thời chạy vòng lặp Python săn VPS.
3. Mỗi ~60 giây, script gửi một request tạo máy tới Oracle API cụm Tokyo.
4. Nếu gặp lỗi hết slot (500) hoặc Rate Limit (429), script tự động chờ ~60s và tiếp tục thử lại bền bỉ 24/7.
5. UptimeRobot định kỳ gõ cửa ping Render mỗi 5 phút một lần để giữ cho máy chủ Render thức liên tục không bao giờ ngủ.
6. Ngay khi có slot trống, máy ảo 4 OCPU / 24GB RAM sẽ được tạo ngay lập tức. Script ghi log thành công và tự động dừng.

---

## 4. CÁCH KẾT NỐI VÀO VPS SAU KHI SĂN THÀNH CÔNG

Khi kiểm tra thấy máy đã tạo thành công trên Oracle Console:
1. Mở PowerShell tại thư mục: F:\oracle-freetier-instance-creation
2. Chạy lệnh SSH:
   ssh -i id_rsa ubuntu@<IP_PUBLIC_CUA_MAY_AO>
3. Cài đặt .NET SDK trên VPS ARM:
   sudo apt update && sudo apt install -y dotnet-sdk-8.0
