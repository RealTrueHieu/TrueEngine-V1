# Hướng Dẫn Tích Hợp TrueEngine V1 Vào En Croissant Chess GUI
Dành cho: **Antigravity Local** và Người Dùng

---

## 1. Tổng Quan Kiến Trúc
* **Tên Engine:** `TrueEngine V1 (RTX 6000 Blackwell Edition)`
* **Giao thức:** Chuẩn quốc tế UCI (Universal Chess Interface).
* **Endpoint Remote:** `https://trueengine.truehieu.qzz.io`
* **Cơ chế:** Cầu nối UCI (`trueengine_uci.py` / `trueengine_uci.bat`) chuyển tiếp các nước cờ từ giao diện **En Croissant** lên máy chủ đám mây chạy mô hình Neural ResNet / MCTS và trả nước đi tối ưu về trong mili-giây.

---

## 2. Các Bước Cài Đặt Cho Antigravity Local

### Cách 1: Tải trực tiếp từ Public Gateway (Khuyên dùng)
Tại thư mục bất kỳ trên máy Local (ví dụ: `C:\TrueEngine\` hoặc `~/trueengine/`):

**Trên Windows (PowerShell / CMD):**
```powershell
curl.exe -s https://trueengine.truehieu.qzz.io/download/uci -o trueengine_uci.py
curl.exe -s https://trueengine.truehieu.qzz.io/download/uci_bat -o trueengine_uci.bat
pip install python-chess requests
```

**Trên Linux / macOS:**
```bash
curl -s https://trueengine.truehieu.qzz.io/download/uci -o trueengine_uci.py
chmod +x trueengine_uci.py
pip install python-chess requests
```

---

## 3. Cấu Hình Trong Giao Diện En Croissant

1. Mở phần mềm **En Croissant**.
2. Nhấn vào biểu tượng **Settings (Cài đặt)** ở góc dưới bên trái (hoặc phím tắt `Ctrl + ,`).
3. Chọn mục **Engines** → Nhấn nút **Add Engine** (Thêm động cơ).
4. Điền các trường thông tin:
   * **Name:** `TrueEngine V1`
   * **Path / Executable:** 
     * Nếu là **Windows:** Chọn đường dẫn đến file `trueengine_uci.bat` (ví dụ: `C:\TrueEngine\trueengine_uci.bat`).
     * Nếu là **Linux/Mac:** Chọn đường dẫn đến file `trueengine_uci.py`.
5. Nhấn **Save / Add**.
6. En Croissant sẽ tự động gửi lệnh `uci` và `isready`. Engine sẽ phản hồi `uciok` và `readyok`.
7. Khi phân tích ván đấu hoặc đấu với máy, tại mục lựa chọn Engine, chọn **TrueEngine V1**.

---

## 4. Prompt Mẫu Giao Cho Antigravity Local

Copy toàn bộ đoạn bên dưới gửi cho **Antigravity Local**:

```text
Hãy tích hợp TrueEngine V1 làm Chess Engine chuẩn UCI vào phần mềm En Croissant trên máy tôi:
1. Tải 2 file cầu nối UCI từ Gateway chính thức:
   - https://trueengine.truehieu.qzz.io/download/uci lưu thành trueengine_uci.py
   - https://trueengine.truehieu.qzz.io/download/uci_bat lưu thành trueengine_uci.bat
2. Cài đặt thư viện phụ trợ nếu chưa có: pip install python-chess requests
3. Đăng ký Engine vào En Croissant config (hoặc hướng dẫn tôi chọn file trueengine_uci.bat trong Settings -> Engines của En Croissant).
4. Kiểm tra gửi lệnh 'uci' và 'isready' để xác nhận TrueEngine V1 phản hồi uciok.
```
