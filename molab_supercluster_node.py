#!/usr/bin/env python3
"""
TrueEngine V1: Molab Supercluster Blackwell Autonomous Node
===========================================================
- Hardware: NVIDIA RTX PRO 6000 Blackwell Server Edition (98 GB VRAM, 160 GB RAM)
- Tri-Infra Coordination: Works in parallel with Google Colab & Kaggle Dual-T4
- Continuous Iterative Training: Scans Hugging Face dataset, trains ResNet with FP16 AMP
- Batched GPU Self-Play Generation: Generates grandmaster-level positions on GPU
- Real-time Telemetry: Streams GPU & training telemetry back to Instabox relay server
- Model Hub Synchronization: Deploys updated .pt and .onnx weights to Hugging Face Hub
"""

import os
import sys
import time
import glob
import random
import json
import subprocess
import threading
import numpy as np

# Ensure dependencies
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    import chess
    from huggingface_hub import HfApi, hf_hub_download, list_repo_files, upload_file
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "torch", "huggingface_hub", "onnx", "onnxscript", "chess", "requests", "tqdm", "numpy"])
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    import chess
    from huggingface_hub import HfApi, hf_hub_download, list_repo_files, upload_file
    import requests

# 1. Configuration & Security
def get_hf_token():
    token = os.getenv("HF_TOKEN")
    if token:
        return token
    for p in [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.expanduser("~/.cache/huggingface/token"),
        os.path.expanduser("~/.huggingface/token"),
        "/content/token"
    ]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("HF_TOKEN="):
                            return line.strip().split("=", 1)[1].strip("\"'")
                        elif not line.startswith("#") and line.strip().startswith("hf_"):
                            return line.strip()
            except Exception:
                pass
    return None

HF_TOKEN = get_hf_token()
DATASET_REPO = "TrueHieu/trueengine-chess-dataset"
MODEL_REPO = "TrueHieu/trueengine-v1-models"
RELAY_URL = "https://8765-agq5kdlqabbzh5cfuqtmwr5sce.instabox.tech/api/molab_telemetry"

WORK_DIR = "/tmp/molab_train_data"
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
CHUNKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated_chunks")
os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(CHUNKS_DIR, exist_ok=True)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
USE_CUDA = torch.cuda.is_available()

# 2. Neural Network Architecture (Multi-Head ResNet)
class ResidualBlock(nn.Module):
    def __init__(self, channels=128):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        res = x
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.bn2(self.conv2(x))
        return F.relu(x + res)

class TrueEngineChessNet(nn.Module):
    def __init__(self, in_channels=12, num_blocks=6, channels=128):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(in_channels, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU()
        )
        self.blocks = nn.ModuleList([ResidualBlock(channels) for _ in range(num_blocks)])
        self.policy_from = nn.Sequential(
            nn.Conv2d(channels, 32, 1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(32 * 8 * 8, 64)
        )
        self.policy_to = nn.Sequential(
            nn.Conv2d(channels, 32, 1),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(32 * 8 * 8, 64)
        )
        self.value_head = nn.Sequential(
            nn.Conv2d(channels, 16, 1),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.Flatten(),
            nn.Linear(16 * 8 * 8, 128),
            nn.ReLU(),
            nn.Linear(128, 1),
            nn.Tanh()
        )

    def forward(self, x):
        h = self.stem(x)
        for block in self.blocks:
            h = block(h)
        p_from = self.policy_from(h)
        p_to = self.policy_to(h)
        val = self.value_head(h)
        return p_from, p_to, val

# 3. Telemetry Reporter
def report_telemetry(mode="IDLE", epoch=0, loss=0.0, accuracy=0.0, speed="--"):
    stats = {
        "status": f"ONLINE (RTX PRO 6000 Blackwell - {mode})",
        "gpu": "NVIDIA RTX PRO 6000 Blackwell Server Edition",
        "vram": "98 GB VRAM (97,887 MiB)",
        "ram": "160 GB RAM",
        "mode": mode,
        "epochs_trained": epoch,
        "last_loss": round(float(loss), 4) if loss else None,
        "accuracy_pct": round(float(accuracy), 2) if accuracy else None,
        "speed": speed,
        "role": "Continuous Deep Supernet Training & Batched MCTS Self-Play",
        "timestamp": time.time()
    }
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
        parts = [p.strip() for p in res.stdout.strip().split(",")]
        if len(parts) >= 4:
            stats["gpu_util_pct"] = float(parts[0])
            stats["vram_used_mib"] = float(parts[1])
            stats["gpu_temp_c"] = float(parts[2])
            stats["gpu_power_w"] = float(parts[3])
    except Exception:
        pass

    try:
        requests.post(RELAY_URL, json=stats, timeout=2.0)
    except Exception:
        pass

# 4. Dataset Loader
class FullChessDataset(Dataset):
    def __init__(self, chunk_paths):
        all_states = []
        all_froms = []
        all_tos = []
        all_wdls = []
        
        for p in chunk_paths:
            try:
                data = np.load(p)
                states = data["states"]
                f_sq = data["from_squares"] if "from_squares" in data else data["policy_from"]
                t_sq = data["to_squares"] if "to_squares" in data else data["policy_to"]
                w_val = data["wdls"] if "wdls" in data else data["values"]
                if states.shape[1] == 14:
                    states = states[:, :12, :, :]
                all_states.append(states)
                all_froms.append(f_sq)
                all_tos.append(t_sq)
                all_wdls.append(w_val)
            except Exception as e:
                print(f"[!] Warning reading {p}: {e}")

        self.states = torch.from_numpy(np.concatenate(all_states, axis=0)).float()
        self.froms = torch.from_numpy(np.concatenate(all_froms, axis=0)).long()
        self.tos = torch.from_numpy(np.concatenate(all_tos, axis=0)).long()
        self.wdls = torch.from_numpy(np.concatenate(all_wdls, axis=0)).float().unsqueeze(1)
        print(f"[✓] Loaded {len(self.states):,} total positions into RAM!")

    def __len__(self):
        return len(self.states)

    def __getitem__(self, idx):
        return self.states[idx], self.froms[idx], self.tos[idx], self.wdls[idx]

def download_chunks():
    api = HfApi(token=HF_TOKEN)
    try:
        files = list_repo_files(repo_id=DATASET_REPO, repo_type="dataset", token=HF_TOKEN)
    except Exception:
        files = list_repo_files(repo_id=DATASET_REPO, repo_type="dataset")

    chunk_files = [f for f in files if f.endswith(".npz")]
    local_chunks = []
    for cf in sorted(chunk_files):
        target_path = os.path.join(WORK_DIR, os.path.basename(cf))
        if os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
            local_chunks.append(target_path)
            continue
        try:
            lp = hf_hub_download(repo_id=DATASET_REPO, filename=cf, repo_type="dataset", local_dir=WORK_DIR, token=HF_TOKEN)
            local_chunks.append(lp)
        except Exception:
            pass
    return local_chunks

# 5. Training Phase
def run_training_round(epochs=5, batch_size=4096):
    chunks = download_chunks()
    if not chunks:
        return None, None

    dataset = FullChessDataset(chunks)
    val_size = max(5000, int(len(dataset) * 0.05))
    train_size = len(dataset) - val_size
    train_set, val_set = torch.utils.data.random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True, num_workers=4, pin_memory=USE_CUDA, drop_last=True)
    val_loader = DataLoader(val_set, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=USE_CUDA)

    model = TrueEngineChessNet().to(DEVICE)
    latest_pt = os.path.join(MODELS_DIR, "trueengine_v1_latest.pt")
    if os.path.exists(latest_pt):
        try:
            model.load_state_dict(torch.load(latest_pt, map_location=DEVICE))
            print("[+] Loaded existing weights from trueengine_v1_latest.pt")
        except Exception:
            pass

    optimizer = torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    scaler = torch.amp.GradScaler('cuda') if USE_CUDA else None

    ce_loss = nn.CrossEntropyLoss()
    mse_loss = nn.MSELoss()

    best_loss = 999.0
    final_acc = 0.0

    print(f"\n⚡ Starting Supernet Training Round on {DEVICE} ({len(dataset):,} positions)...")
    for epoch in range(1, epochs + 1):
        model.train()
        start_t = time.time()
        running_loss = 0.0
        correct_moves = 0
        total_moves = 0

        for states, froms, tos, wdls in train_loader:
            states = states.to(DEVICE, non_blocking=True)
            froms = froms.to(DEVICE, non_blocking=True)
            tos = tos.to(DEVICE, non_blocking=True)
            wdls = wdls.to(DEVICE, non_blocking=True)

            optimizer.zero_grad(set_to_none=True)
            if USE_CUDA:
                with torch.amp.autocast('cuda'):
                    p_from, p_to, val = model(states)
                    l_from = ce_loss(p_from, froms)
                    l_to = ce_loss(p_to, tos)
                    l_val = mse_loss(val, wdls)
                    total_l = l_from + l_to + (1.5 * l_val)
                scaler.scale(total_l).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                p_from, p_to, val = model(states)
                total_l = ce_loss(p_from, froms) + ce_loss(p_to, tos) + 1.5 * mse_loss(val, wdls)
                total_l.backward()
                optimizer.step()

            running_loss += total_l.item() * states.size(0)
            pred_from = p_from.argmax(dim=-1)
            pred_to = p_to.argmax(dim=-1)
            correct_moves += ((pred_from == froms) & (pred_to == tos)).sum().item()
            total_moves += states.size(0)

        scheduler.step()
        elapsed = time.time() - start_t
        train_loss = running_loss / total_moves
        train_acc = (correct_moves / total_moves) * 100.0
        final_acc = train_acc
        speed = f"{(total_moves / elapsed):.1f} pos/s"

        print(f"Round Epoch [{epoch}/{epochs}] Loss: {train_loss:.4f} | Acc: {train_acc:.2f}% | Speed: {speed}")
        report_telemetry(mode="SUPERNET_TRAINING", epoch=epoch, loss=train_loss, accuracy=train_acc, speed=speed)

    # Save & Deploy
    torch.save(model.state_dict(), latest_pt)
    onnx_path = os.path.join(MODELS_DIR, "trueengine_v1_latest.onnx")
    try:
        dummy = torch.randn(1, 12, 8, 8, device=DEVICE)
        torch.onnx.export(model, dummy, onnx_path, input_names=["board_state"], output_names=["policy_from", "policy_to", "value"], dynamic_axes={"board_state": {0: "batch"}}, opset_version=14)
    except Exception as e:
        print(f"[!] ONNX export error: {e}")

    # Push to HF
    if HF_TOKEN:
        api = HfApi(token=HF_TOKEN)
        try:
            api.upload_file(path_or_fileobj=latest_pt, path_in_repo="trueengine_v1_latest.pt", repo_id=MODEL_REPO)
            if os.path.exists(onnx_path):
                api.upload_file(path_or_fileobj=onnx_path, path_in_repo="trueengine_v1_latest.onnx", repo_id=MODEL_REPO)
            print("[✓] Pushed latest weights to Hugging Face Model Hub!")
        except Exception as e:
            print(f"[!] HF upload error: {e}")

    return train_loss, final_acc

# 6. Batched Self-Play Generator
PIECE_MAP = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 4, chess.KING: 5}

def board_to_planes(board):
    planes = np.zeros((12, 8, 8), dtype=np.float32)
    for sq, piece in board.piece_map().items():
        row, col = sq // 8, sq % 8
        idx = PIECE_MAP[piece.piece_type] + (6 if piece.color == chess.BLACK else 0)
        planes[idx, row, col] = 1.0
    return planes

def run_selfplay_batch(model, num_games=100, target_positions=30000):
    print(f"\n⚡ Generating Batched Self-Play Positions on {DEVICE}...")
    report_telemetry(mode="GPU_SELFPLAY_GENERATION", speed="Simulating...")
    
    model.eval()
    boards = [chess.Board() for _ in range(num_games)]
    histories = [[] for _ in range(num_games)]
    collected_states = []
    collected_froms = []
    collected_tos = []
    collected_wdls = []

    start_t = time.time()
    active_indices = list(range(num_games))

    while active_indices and len(collected_states) < target_positions:
        # Batch inference
        batch_planes = np.stack([board_to_planes(boards[i]) for i in active_indices])
        batch_tensors = torch.from_numpy(batch_planes).to(DEVICE)
        
        with torch.no_grad():
            if USE_CUDA:
                with torch.amp.autocast('cuda'):
                    p_from, p_to, val = model(batch_tensors)
            else:
                p_from, p_to, val = model(batch_tensors)
                
            p_from_prob = F.softmax(p_from, dim=-1).cpu().numpy()
            p_to_prob = F.softmax(p_to, dim=-1).cpu().numpy()

        finished = []
        for idx_in_batch, game_idx in enumerate(active_indices):
            board = boards[game_idx]
            legal_moves = list(board.legal_moves)
            if not legal_moves or board.is_game_over() or board.fullmove_number > 90:
                # Game end
                res = board.result()
                val_outcome = 0.0
                if res == "1-0": val_outcome = 1.0
                elif res == "0-1": val_outcome = -1.0
                
                for s, f, t, turn in histories[game_idx]:
                    collected_states.append(s)
                    collected_froms.append(f)
                    collected_tos.append(t)
                    # Flip value relative to turn
                    collected_wdls.append(val_outcome if turn == chess.WHITE else -val_outcome)

                boards[game_idx] = chess.Board()
                histories[game_idx] = []
                continue

            # Pick move using softmax policy + legal mask
            best_move = random.choice(legal_moves)
            best_score = -1.0
            pf = p_from_prob[idx_in_batch]
            pt = p_to_prob[idx_in_batch]
            
            for m in legal_moves:
                score = pf[m.from_square] * pt[m.to_square]
                if score > best_score:
                    best_score = score
                    best_move = m

            histories[game_idx].append((board_to_planes(board), best_move.from_square, best_move.to_square, board.turn))
            board.push(best_move)

    elapsed = time.time() - start_t
    print(f"[✓] Generated {len(collected_states):,} self-play positions in {elapsed:.1f}s ({(len(collected_states)/max(1, elapsed)):.1f} pos/s)!")

    # Save to NPZ chunk and push to HF
    if len(collected_states) >= 10000:
        chunk_name = f"molab_chunk_{int(time.time())}.npz"
        chunk_path = os.path.join(CHUNKS_DIR, chunk_name)
        np.savez_compressed(
            chunk_path,
            states=np.array(collected_states, dtype=np.float32),
            from_squares=np.array(collected_froms, dtype=np.int64),
            to_squares=np.array(collected_tos, dtype=np.int64),
            wdls=np.array(collected_wdls, dtype=np.float32)
        )
        if HF_TOKEN:
            try:
                api = HfApi(token=HF_TOKEN)
                api.upload_file(
                    path_or_fileobj=chunk_path,
                    path_in_repo=f"chunks/{chunk_name}",
                    repo_id=DATASET_REPO,
                    repo_type="dataset"
                )
                print(f"[✓] Uploaded new self-play chunk to Hugging Face Dataset: chunks/{chunk_name}!")
            except Exception as e:
                print(f"[!] Upload chunk error: {e}")

# 7. Main Autonomous Loop
def main():
    print("=" * 65)
    print(" 🚀 TRUEENGINE V1: MOLAB SUPERCLUSTER BLACKWELL NODE")
    print(f" 🎯 Device: {DEVICE} ({torch.cuda.get_device_name(0) if USE_CUDA else 'CPU'})")
    print(f" 📂 Dataset: {DATASET_REPO}")
    print(f" 📦 Model: {MODEL_REPO}")
    print("=" * 65)

    cycle = 1
    while True:
        print(f"\n=== [CYCLE {cycle}] SUPERCLUSTER ITERATION START ===")
        # 1. Training Round (5 epochs)
        run_training_round(epochs=5, batch_size=4096)
        
        # 2. Self-Play Generation
        model = TrueEngineChessNet().to(DEVICE)
        latest_pt = os.path.join(MODELS_DIR, "trueengine_v1_latest.pt")
        if os.path.exists(latest_pt):
            model.load_state_dict(torch.load(latest_pt, map_location=DEVICE))
        run_selfplay_batch(model, num_games=128, target_positions=35000)

        cycle += 1
        time.sleep(5)

if __name__ == "__main__":
    main()
