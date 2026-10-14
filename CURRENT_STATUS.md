# BẢN ĐỒ VẬN HÀNH HỆ THỐNG SĂN VPS ORACLE CLOUD 24/24

Tài liệu này giải thích chi tiết toàn bộ luồng chạy ngầm của hệ thống: **Chạy ở đâu, tự động ping ở đâu, cách kiểm tra và truy vấn khi cần**.

---

## 1. Hệ thống đang chạy ngầm ở đâu?
Hệ thống **KHÔNG chạy trên máy tính cá nhân của bạn** (máy tính của bạn có thể tắt thoải mái). Toàn bộ tiến trình đang chạy trên đám mây:

* **Nơi chạy script chính:** [Render.com](https://dashboard.render.com/)
  * **Loại dịch vụ:** Web Service (Gói Free Tier 750 giờ/tháng).
  * **Nguồn code:** Tự động đồng bộ từ repository GitHub: [`https://github.com/son1999tmgl/oracle-freetier-instance-creation`](https://github.com/son1999tmgl/oracle-freetier-instance-creation).
  * **Lệnh khởi chạy ngầm:** `python3 -u main.py`
  * **Mục đích:** Gửi API request liên tục mỗi ~60 giây đến cụm máy chủ Oracle Tokyo (`ap-tokyo-1`) để săn máy ảo ARM 4 OCPU / 24 GB RAM / 200 GB SSD.

---

## 2. Cơ chế tự động "click" ping mỗi 5 phút 1 lần ở đâu?

* **Nơi thực hiện ping:** [UptimeRobot.com](https://uptimerobot.com/)
* **Tại sao cần ping mỗi 5 phút?**
  * Gói Free Web Service của Render có cơ chế: **Nếu sau 15 phút không có ai truy cập web, Render sẽ tự động cho máy chủ "ngủ" (Spin down)** để tiết kiệm tài nguyên.
  * Trong file `main.py`, đã được tích hợp sẵn một **Dummy HTTP Server mở tại cổng 10000** trả về phản hồi `200 OK`.
  * **UptimeRobot** được thiết lập để cứ đúng **5 phút một lần** tự động gửi 1 HTTP GET request ("gõ cửa") vào URL của Render (dạng `https://<ten-service>.onrender.com`).
  * Nhờ có UptimeRobot gõ cửa liên tục, Render luôn nhận diện là web đang có khách truy cập và **giữ cho máy chủ thức liên tục 24/7/365, không bao giờ bị tắt**.

---

## 3. Sơ đồ luồng hoạt động tổng thể (Workflow)

```
[Máy tính của bạn] 
   └── (Đã tắt máy, không tốn điện, không tốn RAM)

[GitHub] (son1999tmgl/oracle-freetier-instance-creation)
   └── Lưu trữ code, OCI API Key, Subnet ID.
   └── Khi có commit mới -> Tự động kích hoạt Render kéo code về.

[UptimeRobot] (https://uptimerobot.com)
   │
   └── (Cứ mỗi 5 phút) Gửi 1 HTTP request ping vào Render
         │
         ▼
[Render.com Server] (https://dashboard.render.com)
   ├── Cổng 10000: Tiếp nhận ping từ UptimeRobot -> Trả về 200 OK (Thức 24/24)
   └── Luồng Python ngầm:
         └── Mỗi ~60 giây gửi 1 lệnh tạo VPS tới Oracle API
               │
               ▼
   [Oracle Cloud Tokyo API] (cloud.oracle.com)
      ├── Hết slot (500) hoặc Gửi nhanh (429) -> Script tự lùi lại 60-66s rồi thử lại
      └── Khi có người nhả máy -> TẠO THÀNH CÔNG!
```

---

## 4. Cách kiểm tra và truy vấn khi cần

### A. Kiểm tra nhật ký chạy (Logs) thời gian thực:
1. Đăng nhập vào: [https://dashboard.render.com](https://dashboard.render.com)
2. Chọn Web Service: `oracle-freetier-instance-creation`.
3. Bấm vào tab **Logs**: Bạn sẽ thấy các lượt thử `[Thu lan #...]`, thời gian chờ `[*] Nghi ... giay`, mã phản hồi `[!] [Het Slot / Rate Limit]`.

### B. Kiểm tra trạng thái ping giữ máy thức:
1. Đăng nhập vào: [https://uptimerobot.com](https://uptimerobot.com)
2. Xem mục Monitor: Trạng thái hiển thị màu xanh **Up 100%**, chu kỳ kiểm tra là **Every 5 mins**.

### C. Kiểm tra khi săn VPS thành công:
1. Đăng nhập vào Oracle Console: [https://cloud.oracle.com/compute/instances](https://cloud.oracle.com/compute/instances) (Region: Tokyo).
2. Khi thấy máy ảo có tên `Tokyo-ARM-AlwaysFree` ở trạng thái màu xanh **RUNNING**:
   * Sao chép **Public IP** của máy ảo.
   * Mở terminal tại thư mục này trên máy tính của bạn và chạy lệnh SSH:
     ```bash
     ssh -i id_rsa ubuntu@<PUBLIC_IP>
     ```
   *(File private key `id_rsa` đã có sẵn ngay trong thư mục này).*
