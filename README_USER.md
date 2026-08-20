# Hướng dẫn sử dụng AIC 2026

Tài liệu này dành cho thành viên chỉ sử dụng website. Bạn không cần cài Git, Docker, Python, Node.js hoặc Jenkins.

## Truy cập website

### Trong cùng mạng Wi-Fi/LAN

Nhận địa chỉ website từ người vận hành, ví dụ:

```text
http://192.168.1.20:8088
```

Không sử dụng `localhost:8088`, vì `localhost` luôn chỉ tới chính máy đang mở trình duyệt.

Điều kiện truy cập:

- Máy production và Docker Desktop đang hoạt động.
- Thiết bị kết nối cùng Wi-Fi/LAN với máy production.
- Windows Firewall cho phép kết nối TCP vào port `8088`.
- Mạng Wi-Fi không bật client isolation/AP isolation.

### Qua Internet

Khi hệ thống được triển khai lên server chung, sử dụng domain HTTPS do nhóm cung cấp, ví dụ:

```text
https://aic2026.example.com
```

## Kiểm tra hệ thống

Mở website bằng trình duyệt Chrome, Edge hoặc Firefox phiên bản mới. Nếu trang không tải được, kiểm tra:

1. Địa chỉ IP hoặc domain có chính xác không.
2. Thiết bị có cùng mạng với máy production không.
3. Máy production có đang hoạt động không.
4. Thử tải lại trang bằng `Ctrl + F5`.

## Trạng thái chức năng hiện tại

Frontend và backend core có thể hoạt động, nhưng chức năng tìm kiếm đầy đủ chỉ khả dụng sau khi nhóm tích hợp:

- MongoDB.
- Frame server và keyframes.
- Model/checkpoint.
- Metadata và embeddings.

## Báo lỗi

Khi gặp lỗi, gửi cho nhóm phát triển:

- Thời điểm xảy ra lỗi.
- Địa chỉ website đang truy cập.
- Các bước đã thực hiện.
- Nội dung truy vấn đã nhập.
- Kết quả mong đợi và kết quả thực tế.
- Ảnh chụp màn hình hoặc video lỗi.

Không gửi password, API key, MongoDB URI hoặc Jenkins credential qua nhóm chat.

## Những công cụ người dùng không cần truy cập

- GitHub repository: lưu source code.
- Jenkins: test, build và deploy tự động.
- GitHub Container Registry: lưu Docker images.
- MongoDB và Qdrant: lưu dữ liệu và vector.

Người dùng chỉ cần truy cập website production.
