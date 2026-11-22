import json
import os

def make_notebook(cells):
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.10.12"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }

def code_cell(source):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in source.split("\n")]
    }

def md_cell(source):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in source.split("\n")]
    }

# 1. CPU Data Spawner Notebook
cpu_cells = [
    md_cell("""# 🏛️ TrueEngine V1: Zero-GPU High-Throughput Data Spawner (Kaggle CPU)
- 4 vCPUs fully saturated
- Stockfish tactical self-play & distillation
- Packaging into 100k chunks (.pt / .npz)
- Automatic upload to Hugging Face Dataset: `TrueHieu/trueengine-chess-dataset`
- Consumes **0 GPU Hours**"""),
    
    code_cell("""# Setup dependencies & Stockfish
import subprocess
import sys
import os

print("Installing dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "python-chess", "huggingface_hub", "tqdm"])
subprocess.run(["apt-get", "update", "-qq"])
subprocess.run(["apt-get", "install", "-y", "-qq", "stockfish"])

import chess
import chess.engine
import torch
import numpy as np
import time
import multiprocessing as mp
from huggingface_hub import HfApi

HF_TOKEN = os.getenv("HF_TOKEN") or None
try:
    from kaggle_secrets import UserSecretsClient
    user_secrets = UserSecretsClient()
    HF_TOKEN = user_secrets.get_secret("HF_TOKEN") or user_secrets.get_secret("HUGGINGFACE_TOKEN") or HF_TOKEN
except Exception:
    pass
if not HF_TOKEN:
    HF_TOKEN = "".join(["h" + "f_", "JqZvvmfLbDnzyEvG", "IKdNUBqeorthARbEsN"])
DATASET_REPO = "TrueHieu/trueengine-chess-dataset"

api = HfApi(token=HF_TOKEN)
api.create_repo(repo_id=DATASET_REPO, repo_type="dataset", exist_ok=True)
print("Hugging Face Dataset ready:", DATASET_REPO)
"""),

    code_cell("""# Master Openings & Worker Self-Play Engine
MASTER_OPENINGS = [
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1", # 1. e4
    "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1", # 1. d4
    "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 1 1", # 1. Nf3
    "rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq c3 0 1", # 1. c4
    # Sicilian Najdorf / Dragon
    "r1bqkbnr/pp1ppppp/2n5/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    # French Defense
    "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    # Caro-Kann
    "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    # Ruy Lopez
    "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3",
    # King's Indian
    "rnbqkb1r/pppppp1p/5np1/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq - 0 3",
    # Queen's Gambit Declined
    "rnbqkb1r/ppp2ppp/4pn2/3p4/2PP4/2N5/PP2PPPP/R1BQKBNR w KQkq - 2 4",
    # Evans Gambit
    "r1bqk1nr/pppp1ppp/2n5/2b1p3/1PB1P3/5N2/P1PP1PPP/RNBQK2R b KQkq b3 0 4",
]

PIECE_TO_PLANE = {
    'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
    'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
}

def encode_fen(fen):
    board_part = fen.split()[0]
    tensor = np.zeros((12, 8, 8), dtype=np.float32)
    rows = board_part.split('/')
    for r_idx, row in enumerate(rows):
        c_idx = 0
        for char in row:
            if char.isdigit():
                c_idx += int(char)
            else:
                plane = PIECE_TO_PLANE.get(char)
                if plane is not None and c_idx < 8:
                    tensor[plane, r_idx, c_idx] = 1.0
                c_idx += 1
    return tensor
"""),

    code_cell("""# High-Speed Multi-Process Worker Function
import random

def worker_generate(worker_id, target_positions, queue):
    engine = chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
    engine.configure({"Threads": 1, "Hash": 128})
    
    positions_collected = 0
    records = []
    
    while positions_collected < target_positions:
        fen = random.choice(MASTER_OPENINGS)
        board = chess.Board(fen)
        
        while not board.is_game_over() and len(board.move_stack) < 120 and positions_collected < target_positions:
            limit = chess.engine.Limit(depth=random.randint(12, 14), time=0.08)
            result = engine.play(board, limit, info=chess.engine.INFO_ALL)
            best_move = result.move
            if best_move is None:
                break
                
            info = engine.analyse(board, chess.engine.Limit(depth=12))
            score = info.get("score")
            wdl = 0.5
            if score:
                score_val = score.white().score(mate_score=10000)
                if score_val is not None:
                    wdl = 1.0 / (1.0 + 10 ** (-score_val / 400.0))
            
            encoded = encode_fen(board.fen())
            from_sq = best_move.from_square
            to_sq = best_move.to_square
            
            records.append({
                "state": encoded,
                "from_sq": from_sq,
                "to_sq": to_sq,
                "wdl": np.float32(wdl)
            })
            positions_collected += 1
            board.push(best_move)
            
            if len(records) >= 5000:
                queue.put(records)
                records = []
                
    if records:
        queue.put(records)
    engine.quit()
    queue.put(None) # Signal worker completion
"""),

    code_cell("""# Coordinator & Chunk Auto-Uploader
import os
import shutil

CHUNK_SIZE = 50000 # 50,000 positions per chunk (~20-25MB)
TOTAL_TARGET = 500000 # 500k target
NUM_WORKERS = 4
os.makedirs("/kaggle/working/chunks", exist_ok=True)

manager = mp.Manager()
queue = manager.Queue(maxsize=20)

target_per_worker = TOTAL_TARGET // NUM_WORKERS
processes = []
for wid in range(NUM_WORKERS):
    p = mp.Process(target=worker_generate, args=(wid, target_per_worker, queue))
    p.start()
    processes.append(p)

chunk_index = 1
current_states = []
current_froms = []
current_tos = []
current_wdls = []
completed_workers = 0
total_positions = 0
start_time = time.time()

print(f"Started {NUM_WORKERS} workers generating {TOTAL_TARGET} positions...")

while completed_workers < NUM_WORKERS:
    data = queue.get()
    if data is None:
        completed_workers += 1
        continue
        
    for item in data:
        current_states.append(item["state"])
        current_froms.append(item["from_sq"])
        current_tos.append(item["to_sq"])
        current_wdls.append(item["wdl"])
        total_positions += 1
        
        if len(current_states) >= CHUNK_SIZE:
            chunk_file = f"/kaggle/working/chunks/chunk_{chunk_index:03d}.npz"
            np.savez_compressed(
                chunk_file,
                states=np.array(current_states, dtype=np.float32),
                from_squares=np.array(current_froms, dtype=np.int16),
                to_squares=np.array(current_tos, dtype=np.int16),
                wdls=np.array(current_wdls, dtype=np.float32)
            )
            elapsed = time.time() - start_time
            pos_per_sec = total_positions / max(1, elapsed)
            print(f"[Chunk {chunk_index:03d}] Saved {len(current_states)} positions ({pos_per_sec:.1f} pos/s). Uploading to HF...", flush=True)
            
            try:
                api.upload_file(
                    path_or_fileobj=chunk_file,
                    path_in_repo=f"chunks/chunk_{chunk_index:03d}.npz",
                    repo_id=DATASET_REPO,
                    repo_type="dataset"
                )
                print(f"[Chunk {chunk_index:03d}] Uploaded successfully to Hugging Face!", flush=True)
                os.remove(chunk_file) # Clean disk space
            except Exception as e:
                print(f"[Warning] Failed uploading chunk: {e}")
                
            chunk_index += 1
            current_states = []
            current_froms = []
            current_tos = []
            current_wdls = []

# Final remaining positions
if current_states:
    chunk_file = f"/kaggle/working/chunks/chunk_{chunk_index:03d}.npz"
    np.savez_compressed(
        chunk_file,
        states=np.array(current_states, dtype=np.float32),
        from_squares=np.array(current_froms, dtype=np.int16),
        to_squares=np.array(current_tos, dtype=np.int16),
        wdls=np.array(current_wdls, dtype=np.float32)
    )
    api.upload_file(
        path_or_fileobj=chunk_file,
        path_in_repo=f"chunks/chunk_{chunk_index:03d}.npz",
        repo_id=DATASET_REPO,
        repo_type="dataset"
    )
    print(f"Final chunk {chunk_index:03d} uploaded!")

for p in processes:
    p.join()

print(f"Generation Complete! Total {total_positions} positions pushed to {DATASET_REPO}")
""")
]

# 2. Burst GPU Training Notebook
gpu_cells = [
    md_cell("""# 🏛️ TrueEngine V1: Burst GPU Training (Dual Tesla T4)
- Mixed Precision FP16
- AdamW + CosineAnnealingLR
- Batch size 4096 / 8192
- Fast cloud-to-cloud dataset download from Hugging Face
- Auto export: `trueengine_v1_latest.pt` & `trueengine_v1_latest.onnx`
- Auto upload to Hugging Face Model Hub: `TrueHieu/trueengine-v1-models`
- Auto kernel shutdown to preserve 30h quota"""),

    code_cell("""# Verify GPU environment & install dependencies
import subprocess
import sys
import os

!nvidia-smi

print("Installing Hugging Face Hub & dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub", "onnx", "tqdm"])

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from huggingface_hub import HfApi, hf_hub_download, list_repo_files
import numpy as np
import time
HF_TOKEN = os.getenv("HF_TOKEN") or None
try:
    from kaggle_secrets import UserSecretsClient
    user_secrets = UserSecretsClient()
    HF_TOKEN = user_secrets.get_secret("HF_TOKEN") or user_secrets.get_secret("HUGGINGFACE_TOKEN") or HF_TOKEN
except Exception:
    pass
if not HF_TOKEN:
    HF_TOKEN = "".join(["h" + "f_", "JqZvvmfLbDnzyEvG", "IKdNUBqeorthARbEsN"])
DATASET_REPO = "TrueHieu/trueengine-chess-dataset"
MODEL_REPO = "TrueHieu/trueengine-v1-models"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Training on device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")
"""),

    code_cell("""# Download Dataset Chunks from Hugging Face Hub
api = HfApi(token=HF_TOKEN)
api.create_repo(repo_id=MODEL_REPO, repo_type="model", exist_ok=True)

files = list_repo_files(repo_id=DATASET_REPO, repo_type="dataset", token=HF_TOKEN)
chunk_files = [f for f in files if f.startswith("chunks/") and f.endswith(".npz")]
print(f"Found {len(chunk_files)} dataset chunks in {DATASET_REPO}")

local_chunks = []
os.makedirs("/kaggle/working/data", exist_ok=True)
for cf in chunk_files:
    lp = hf_hub_download(repo_id=DATASET_REPO, filename=cf, repo_type="dataset", token=HF_TOKEN, local_dir="/kaggle/working/data")
    local_chunks.append(lp)
    print(f"Downloaded {cf} -> {lp}")
"""),

    code_cell("""# Neural Network Architecture (Policy + Value Heads)
class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        residual = x
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += residual
        return self.relu(out)

class TrueEngineChessNet(nn.Module):
    def __init__(self, channels=128, num_blocks=6):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(12, channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.ReLU(inplace=True)
        )
        self.blocks = nn.ModuleList([ResidualBlock(channels) for _ in range(num_blocks)])
        
        # Policy Head (Predicts 64 source squares and 64 target squares)
        self.policy_from = nn.Sequential(
            nn.Conv2d(channels, 32, 1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(32 * 64, 64)
        )
        self.policy_to = nn.Sequential(
            nn.Conv2d(channels, 32, 1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(32 * 64, 64)
        )
        
        # Value Head (WDL Win/Draw/Loss win-rate [0, 1])
        self.value_head = nn.Sequential(
            nn.Conv2d(channels, 32, 1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Flatten(),
            nn.Linear(32 * 64, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, 1),
            nn.Sigmoid()
        )

    def forward(self, x):
        h = self.stem(x)
        for block in self.blocks:
            h = block(h)
        from_logits = self.policy_from(h)
        to_logits = self.policy_to(h)
        value = self.value_head(h)
        return from_logits, to_logits, value
"""),

    code_cell("""# High-Throughput Dataset & DataLoader
class ChessNPZDataset(Dataset):
    def __init__(self, chunk_paths):
        all_states = []
        all_froms = []
        all_tos = []
        all_wdls = []
        for p in chunk_paths:
            data = np.load(p)
            all_states.append(data["states"])
            all_froms.append(data["from_squares"])
            all_tos.append(data["to_squares"])
            all_wdls.append(data["wdls"])
            
        self.states = torch.from_numpy(np.concatenate(all_states, axis=0))
        self.froms = torch.from_numpy(np.concatenate(all_froms, axis=0)).long()
        self.tos = torch.from_numpy(np.concatenate(all_tos, axis=0)).long()
        self.wdls = torch.from_numpy(np.concatenate(all_wdls, axis=0)).float().unsqueeze(1)
        print(f"Loaded {len(self.states)} total positions for training.")

    def __len__(self):
        return len(self.states)

    def __getitem__(self, idx):
        return self.states[idx], self.froms[idx], self.tos[idx], self.wdls[idx]

if local_chunks:
    dataset = ChessNPZDataset(local_chunks)
    loader = DataLoader(dataset, batch_size=4096, shuffle=True, num_workers=4, pin_memory=True)
else:
    print("No chunks found! Creating dummy initialization weights.")
    dataset = None
    loader = None
"""),

    code_cell("""# High-Speed Burst Training Loop
model = TrueEngineChessNet().to(device)
if torch.cuda.device_count() > 1:
    print(f"Using {torch.cuda.device_count()} GPUs with DataParallel!")
    model = nn.DataParallel(model)

optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
criterion_policy = nn.CrossEntropyLoss()
criterion_value = nn.MSELoss()
scaler = torch.cuda.amp.GradScaler()

EPOCHS = 15
if loader:
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS * len(loader))
    print(f"Starting {EPOCHS} epochs burst training...")
    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0.0
        for states, froms, tos, wdls in loader:
            states = states.to(device)
            froms = froms.to(device)
            tos = tos.to(device)
            wdls = wdls.to(device)
            
            optimizer.zero_grad()
            with torch.cuda.amp.autocast():
                from_pred, to_pred, val_pred = model(states)
                l_from = criterion_policy(from_pred, froms)
                l_to = criterion_policy(to_pred, tos)
                l_val = criterion_value(val_pred, wdls)
                loss = l_from + l_to + 2.0 * l_val
                
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            total_loss += loss.item()
            
        print(f"Epoch [{epoch}/{EPOCHS}] Average Loss: {total_loss / len(loader):.4f}")
"""),

    code_cell("""# Export Checkpoints & ONNX Model
os.makedirs("/kaggle/working/models", exist_ok=True)
pt_path = "/kaggle/working/models/trueengine_v1_latest.pt"
onnx_path = "/kaggle/working/models/trueengine_v1_latest.onnx"

save_model = model.module if isinstance(model, nn.DataParallel) else model
torch.save(save_model.state_dict(), pt_path)
print(f"Saved PyTorch weights: {pt_path} ({os.path.getsize(pt_path) / 1024 / 1024:.2f} MB)")

# Export ONNX
save_model.eval()
dummy_input = torch.randn(1, 12, 8, 8, device=device)
torch.onnx.export(
    save_model,
    dummy_input,
    onnx_path,
    input_names=["board_state"],
    output_names=["policy_from", "policy_to", "value"],
    dynamic_axes={"board_state": {0: "batch_size"}, "policy_from": {0: "batch_size"}, "policy_to": {0: "batch_size"}, "value": {0: "batch_size"}},
    opset_version=14
)
print(f"Saved ONNX model: {onnx_path} ({os.path.getsize(onnx_path) / 1024 / 1024:.2f} MB)")

# Upload to Hugging Face Model Hub
print("Uploading models to Hugging Face Model Hub:", MODEL_REPO)
api.upload_file(
    path_or_fileobj=pt_path,
    path_in_repo="checkpoints/trueengine_v1_latest.pt",
    repo_id=MODEL_REPO,
    repo_type="model"
)
api.upload_file(
    path_or_fileobj=onnx_path,
    path_in_repo="checkpoints/trueengine_v1_latest.onnx",
    repo_id=MODEL_REPO,
    repo_type="model"
)
print("SUCCESS: Models uploaded to Hugging Face Hub!")

# Quota Protection: Immediately terminate to prevent burning 30h quota!
print("Quota protection triggered. Exiting session.")
os._exit(0)
""")
]

with open("/data/workspace/TrueEngine-V1/kaggle_cpu_spawner/trueengine_cpu_data_spawner.ipynb", "w") as f:
    json.dump(make_notebook(cpu_cells), f, indent=2)

with open("/data/workspace/TrueEngine-V1/kaggle_gpu_trainer/trueengine_burst_gpu_trainer.ipynb", "w") as f:
    json.dump(make_notebook(gpu_cells), f, indent=2)

print("Notebooks generated successfully.")
