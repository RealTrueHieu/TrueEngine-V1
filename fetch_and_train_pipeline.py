#!/usr/bin/env python3
"""
TrueEngine V1: Autonomous Experience Consolidation & Model Training Pipeline
- Automatically fetches latest self-play data & distilled positions from Google Colab T4
- Consolidates knowledge into books/experience_memory.json
- Trains TrueEngineChessNet directly on this machine
- Exports PyTorch checkpoint and ONNX runtime weights
- Emits real-time training metrics for Cloudflare Worker live dashboard
"""

import os
import sys
import json
import time
import subprocess
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOKS_DIR = os.path.join(SCRIPT_DIR, "books")
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")
MEMORY_PATH = os.path.join(BOOKS_DIR, "experience_memory.json")
COLAB_DISTILLED_PATH = os.path.join(BOOKS_DIR, "colab_distilled_experience.json")
MODEL_SAVE_PATH = os.path.join(MODELS_DIR, "trueengine_v1_supernet_latest.pt")
ONNX_SAVE_PATH = os.path.join(MODELS_DIR, "neural_net.onnx")
STATS_PATH = os.path.join(MODELS_DIR, "latest_training_stats.json")

os.makedirs(BOOKS_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

print("=" * 65)
print("  TRUEENGINE V1 — CONTINUOUS DATA FETCH & MODEL TRAINING")
print("=" * 65)

# Step 1: Fetch distilled positions from Colab T4
print(f"[1/4] Fetching latest distilled master positions from Google Colab...")
try:
    cmd = [
        "colab", "download",
        "/content/colab_distilled_experience.json",
        COLAB_DISTILLED_PATH
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
    if res.returncode == 0:
        print(f"  -> Successfully downloaded latest Colab distilled experience!")
    else:
        print(f"  -> Notice: Colab download returned {res.returncode}, will use local copy.")
except Exception as e:
    print(f"  -> Warning: Colab download skipped ({e}), will use local memory.")

# Also download selfplay metrics if available
try:
    metrics_path = os.path.join(SCRIPT_DIR, "selfplay_100m_metrics.json")
    subprocess.run(["colab", "download", "/content/selfplay_100m_metrics.json", metrics_path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
except Exception:
    pass

# Step 2: Merge into local experience memory
print(f"[2/4] Consolidating dataset with local brain memory...")
local_data = {}
if os.path.exists(MEMORY_PATH):
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            local_data = json.load(f)
    except Exception:
        local_data = {}

distilled_data = {}
if os.path.exists(COLAB_DISTILLED_PATH):
    try:
        with open(COLAB_DISTILLED_PATH, "r", encoding="utf-8") as f:
            distilled_data = json.load(f)
    except Exception:
        distilled_data = {}

merged_new = 0
for fen, moves in distilled_data.items():
    if fen not in local_data:
        local_data[fen] = {}
        merged_new += 1
    if isinstance(moves, dict):
        for m, m_data in moves.items():
            local_data[fen][m] = m_data

if merged_new > 0 or not os.path.exists(MEMORY_PATH):
    temp_mem = MEMORY_PATH + ".tmp"
    with open(temp_mem, "w", encoding="utf-8") as f:
        json.dump(local_data, f, indent=2)
    os.replace(temp_mem, MEMORY_PATH)
    print(f"  -> Merged {merged_new:,} new positions. Total Brain Memory: {len(local_data):,} positions.")
else:
    print(f"  -> Brain Memory Up-To-Date: {len(local_data):,} positions.")

# Step 3: Build Training Samples
PIECE_TO_PLANE = {
    'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
    'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
}

def fen_to_tensor(fen: str):
    board_part = fen.split()[0]
    tensor = torch.zeros((12, 8, 8), dtype=torch.float32)
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

def uci_to_index(uci_move: str):
    if len(uci_move) < 4:
        return 0
    from_sq = (ord(uci_move[0]) - ord('a')) + (int(uci_move[1]) - 1) * 8
    to_sq = (ord(uci_move[2]) - ord('a')) + (int(uci_move[3]) - 1) * 8
    from_sq = max(0, min(63, from_sq))
    to_sq = max(0, min(63, to_sq))
    return from_sq * 64 + to_sq

training_samples = []
for fen, moves in local_data.items():
    if not isinstance(moves, dict):
        continue
    for m_uci, m_info in moves.items():
        if not isinstance(m_info, dict):
            continue
        if m_info.get("blunder") or m_info.get("multiplier", 1.0) < 0.1:
            continue
        weight = m_info.get("multiplier", 1.0)
        q_val = m_info.get("q_val", 0.0)
        training_samples.append((fen, m_uci, weight, q_val))

# Sample up to 10,000 recent / curated positions per training step for swift execution
if len(training_samples) > 10000:
    import random
    training_samples = random.sample(training_samples, 10000)

print(f"[3/4] Prepared {len(training_samples):,} curated training samples (vetoed blunders filtered).")

class CuratedChessDataset(Dataset):
    def __init__(self, samples):
        self.samples = samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        fen, move_uci, weight, q_val = self.samples[idx]
        x = fen_to_tensor(fen)
        target_move = uci_to_index(move_uci)
        return x, target_move, torch.tensor(weight, dtype=torch.float32), torch.tensor([q_val], dtype=torch.float32)

class ResBlock(nn.Module):
    def __init__(self, channels=128):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        return self.relu(self.bn2(self.conv2(self.relu(self.bn1(self.conv1(x))))) + x)

class TrueEngineChessNet(nn.Module):
    def __init__(self, in_channels=12, num_blocks=6, channels=128):
        super().__init__()
        self.conv_in = nn.Conv2d(in_channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn_in = nn.BatchNorm2d(channels)
        self.relu = nn.ReLU(inplace=True)
        self.res_blocks = nn.ModuleList([ResBlock(channels) for _ in range(num_blocks)])

        self.policy_conv = nn.Conv2d(channels, 32, kernel_size=1)
        self.policy_bn = nn.BatchNorm2d(32)
        self.policy_fc = nn.Linear(32 * 8 * 8, 4096)

        self.value_conv = nn.Conv2d(channels, 16, kernel_size=1)
        self.value_bn = nn.BatchNorm2d(16)
        self.value_fc1 = nn.Linear(16 * 8 * 8, 128)
        self.value_fc2 = nn.Linear(128, 1)
        self.tanh = nn.Tanh()

    def forward(self, x):
        out = self.relu(self.bn_in(self.conv_in(x)))
        for block in self.res_blocks:
            out = block(out)

        p = self.relu(self.policy_bn(self.policy_conv(out)))
        policy_logits = self.policy_fc(p.view(p.size(0), -1))

        v = self.relu(self.value_bn(self.value_conv(out)))
        v = self.relu(self.value_fc1(v.view(v.size(0), -1)))
        value = self.tanh(self.value_fc2(v))

        return policy_logits, value

# Step 4: Train on CPU (Zero Local GPU Load)
device = torch.device("cpu")
print(f"[4/4] Starting Training on: {device} (Zero GPU Policy Enforced)")

dataset = CuratedChessDataset(training_samples)
batch_size = 64
loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

model = TrueEngineChessNet().to(device)

if os.path.exists(MODEL_SAVE_PATH):
    try:
        ckpt = torch.load(MODEL_SAVE_PATH, map_location=device)
        if "model_state_dict" in ckpt:
            model.load_state_dict(ckpt["model_state_dict"])
            print("  -> Warm-started from existing checkpoint!")
    except Exception:
        pass

optimizer = optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
criterion_policy = nn.CrossEntropyLoss(reduction="none")
criterion_value = nn.MSELoss()

epochs = 2
print(f"\nTraining {epochs} epochs over {len(training_samples):,} positions (Batch Size: {batch_size})...")

last_loss = 0.0
last_acc = 0.0
last_speed = 0.0

for epoch in range(1, epochs + 1):
    model.train()
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    t0 = time.time()

    for x, target_m, weights, q_vals in loader:
        optimizer.zero_grad()
        policy_logits, value_preds = model(x)
        loss_p = (criterion_policy(policy_logits, target_m) * weights).mean()
        loss_v = criterion_value(value_preds, q_vals)
        loss = loss_p + 0.5 * loss_v

        loss.backward()
        optimizer.step()

        total_loss += loss.item() * x.size(0)
        preds = torch.argmax(policy_logits, dim=-1)
        total_correct += (preds == target_m).sum().item()
        total_count += x.size(0)

    elapsed = time.time() - t0
    acc = (total_correct / max(1, total_count)) * 100.0
    avg_loss = total_loss / max(1, total_count)
    speed = total_count / max(0.01, elapsed)
    last_loss = avg_loss
    last_acc = acc
    last_speed = speed
    print(f"  Epoch [{epoch}/{epochs}] | Loss: {avg_loss:.4f} | Accuracy: {acc:.2f}% | Speed: {speed:.0f} pos/sec | Time: {elapsed:.2f}s")

# Save Checkpoint
torch.save({
    "model_state_dict": model.state_dict(),
    "arch": "ResNet-6x128-PolicyValue",
    "samples_trained": len(training_samples),
    "timestamp": time.time()
}, MODEL_SAVE_PATH)
print(f"\n[Saved] PyTorch Model checkpoint saved to: {MODEL_SAVE_PATH}")

# Save Stats for Dashboard
stats = {
    "status": "COMPLETED",
    "epochs_trained": epochs,
    "final_loss": round(last_loss, 4),
    "accuracy_pct": round(last_acc, 2),
    "training_speed_pos_sec": round(last_speed, 1),
    "positions_in_batch": len(training_samples),
    "total_brain_memory": len(local_data),
    "timestamp": time.time()
}
with open(STATS_PATH, "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2)

# Export ONNX
try:
    dummy_input = torch.randn(1, 12, 8, 8, device=device)
    torch.onnx.export(
        model,
        dummy_input,
        ONNX_SAVE_PATH,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=['board_input'],
        output_names=['policy_logits', 'value_eval'],
        dynamic_axes={'board_input': {0: 'batch_size'}, 'policy_logits': {0: 'batch_size'}, 'value_eval': {0: 'batch_size'}}
    )
    print(f"[Saved] ONNX Model exported to: {ONNX_SAVE_PATH} ({os.path.getsize(ONNX_SAVE_PATH)/(1024*1024):.2f} MB)")
except Exception as e:
    print(f"[ONNX Warning] Export warning: {e}")

print("=" * 65)
print("  TRAINING PIPELINE COMPLETE — MODEL UPGRADED SUCCESSFULLY")
print("=" * 65)
