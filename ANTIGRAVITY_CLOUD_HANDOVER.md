# 🚀 ANTIGRAVITY CLOUD HANDOVER: TRUEENGINE V1 ECOSYSTEM
> **Date:** 2026-11-25 | **Authors:** Antigravity & RealTrueHieu  
> **Directive:** This document encapsulates the complete operational state, architecture, cloud pipelines, credentials, and verification test suites of the **TrueEngine V1** ecosystem for deployment to Antigravity Cloud / remote VMs.

---

## 1. HỆ SINH THÁI TỔNG QUAN & TÀI KHOẢN (CREDENTIALS)

- **GitHub Repository:** `https://github.com/RealTrueHieu/TrueEngine-V1.git` (nhánh `main`)
- **Hugging Face Hub:**
  - Token: `<YOUR_HUGGINGFACE_TOKEN>` (User: `TrueHieu`)
  - Datasets: `TrueHieu/trueengine-chess-dataset`
  - Models: `TrueHieu/trueengine-v1-models`
- **Kaggle Account:** `trantrungminhhieu`
- **Cloudflare Tunnels:**
  - `https://trueengine.truehieu.qzz.io` (Gateway chính thức: tải bridge, compute API)
  - `https://chess.truehieu.qzz.io` (Web Portal En Croissant clone & analysis daemon)
  - `https://kaggle.truehieu.qzz.io` (Kaggle Stockfish 19 CPU Supercomputing cluster)

---

## 2. QUY CHUẨN ĐIỆN TOÁN ĐÁM MÂY (ZERO-QUOTA-WASTE)

| Nhiệm vụ | Nền tảng | Cấu hình | Quota tiêu tốn | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **Stockfish 19 Oracle & Self-Play** | Kaggle CPU | 4 vCPUs Intel Xeon, 30GB RAM, 2048MB Hash | **0% GPU (Vô tận)** | `notebookb848d05196` |
| **Huấn luyện Mạng Nơ-ron (ResNet)** | Kaggle GPU | NVIDIA Tesla T4 (16GB VRAM, FP16 Tensor Cores) | **Burst 20-30 phút/tuần** | `trueengine-v1-gpu-training` |
| **Web Phân Tích & Review (En Croissant)** | Local Daemon | Port 8000 + Cloudflare Tunnel | **0% GPU** | `run_chess_analysis_portal.py` |

---

## 3. CẤU TRÚC GÓI TRIỂN KHAI (PACKAGE MANIFEST)

```text
TrueEngine_V1_Cloud_Package/
├── ANTIGRAVITY_CLOUD_HANDOVER.md       # Tài liệu bàn giao & hướng dẫn toàn diện
├── engine/
│   ├── TrueEngine_V1.py                # Lõi động cơ Hybrid (Guardian + Oracle + Memory)
│   ├── trueengine_uci.py               # Cầu nối UCI đạt chuẩn Blueprint Expert Standard
│   └── trueengine_uci.bat              # Launcher Windows với cờ unbuffered python -u
├── books/
│   ├── experience_memory.json          # Bộ nhớ 91,967+ thế cờ Master (veto blunder, boost win)
│   └── grandmaster_book.json           # Khai cuộc kinh điển từ các trận Immortal
├── dist/
│   ├── TrueEngine_V1_Cloud.exe         # Binary động cơ TrueEngine V1 Cloud
│   └── Stockfish_19_Cloud_Kaggle.exe   # Binary cầu nối Stockfish 19 Cloud
├── kaggle_cpu_stockfish/
│   ├── kernel-metadata.json            # Metadata Kaggle CPU
│   └── notebookb848d05196.ipynb        # Server Stockfish 19 4-threads + Cloudflare Tunnel
├── kaggle_gpu_training/
│   ├── kernel-metadata.json            # Metadata Kaggle GPU
│   └── trueengine_v1_gpu_training.ipynb# Script huấn luyện ResNet 15 Epochs tự đẩy HF
├── build_kaggle_cpu_stockfish.py       # Tự động đóng gói & đẩy notebook CPU lên Kaggle
├── build_kaggle_gpu_trainer.py         # Tự động đóng gói & đẩy notebook GPU lên Kaggle
├── fetch_hf_model.py                   # Script 1-click kéo model mới nhất từ Hugging Face
├── stockfish_19_cloud_uci.py           # Cầu nối UCI Python cho Stockfish 19 Cloud
├── play_vanguard_arena.py              # Tool thi đấu tự động với đấu trường Vanguard
└── data/
    ├── vanguard_gen6_clash.pgn         # PGN kết quả thắng 2-0 vs Vanguard Gen-6
    └── solo_match_trueengine_vs_sf19.pgn # PGN kết quả hòa 1.0-1.0 (283 nước, 0 blunder)
```

---

## 4. HƯỚNG DẪN VẬN HÀNH TRÊN CLOUD

1. **Chạy Stockfish 19 Cloud Server:**
   ```bash
   kaggle kernels push -p kaggle_cpu_stockfish
   ```
2. **Kích hoạt phiên Burst Training trên GPU:**
   ```bash
   kaggle kernels push -p kaggle_gpu_training
   ```
3. **Kéo Model mới nhất về từ Hugging Face:**
   ```bash
   python fetch_hf_model.py
   ```
4. **Kiểm tra Handshake UCI:**
   ```bash
   python -u engine/trueengine_uci.py
   # Gửi: uci -> Nhận: uciok
   # Gửi: isready -> Nhận: readyok
   ```
