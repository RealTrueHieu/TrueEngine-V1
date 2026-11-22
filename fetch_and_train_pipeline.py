import os
import sys
import json
import time
import urllib.request
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

PROJECT_DIR = r"C:\Users\RealTrueHieu\CustomHumanChessEngine"
MEMORY_PATH = os.path.join(PROJECT_DIR, "books", "experience_memory.json")
BRIDGE_URL = "https://thumbnails-quoted-guaranteed-venue.trycloudflare.com"
MODEL_SAVE_PATH = os.path.join(PROJECT_DIR, "models", "trueengine_v1_supernet_latest.pt")
ONNX_SAVE_PATH = os.path.join(PROJECT_DIR, "models", "neural_net.onnx")

print("=" * 65)
print("  TRUEENGINE V1 — CONTINUOUS DATA FETCH & MODEL TRAINING")
print("=" * 65)

# Step 1: Fetch distilled positions from Colab Bridge
print(f"[1/4] Fetching latest distilled master positions from Colab bridge...")
distilled_data = {}
try:
    req = urllib.request.urlopen(f"{BRIDGE_URL}/distilled", timeout=20)
    distilled_data = json.loads(req.read().decode())
    print(f"  -> Successfully received {len(distilled_data):,} positions from Colab!")
except Exception as e:
    print(f"  -> Warning: Could not fetch from bridge ({e}), will use local memory.")

# Step 2: Merge into local experience memory
print(f"[2/4] Consolidating dataset with local brain memory...")
local_data = {}
if os.path.exists(MEMORY_PATH):
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            local_data = json.load(f)
    except Exception:
        local_data = {}

merged_new = 0
for fen, moves in distilled_data.items():
    if fen not in local_data:
        local_data[fen] = {}
        merged_new += 1
    if isinstance(moves, dict):
        for m, m_data in moves.items():
            local_data[fen][m] = m_data

if merged_new > 0:
    temp_mem = MEMORY_PATH + ".tmp"
    with open(temp_mem, "w", encoding="utf-8") as f:
        json.dump(local_data, f, indent=2)
    os.replace(temp_mem, MEMORY_PATH)
    print(f"  -> Merged {merged_new:,} new positions. Total Local Memory: {len(local_data):,} positions.")
else:
    print(f"  -> Total Local Memory: {len(local_data):,} positions.")

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
        # Skip vetoed blunders
        if m_info.get("blunder") or m_info.get("multiplier", 1.0) < 0.1:
            continue
        weight = m_info.get("multiplier", 1.0)
        q_val = m_info.get("q_val", 0.0)
        training_samples.append((fen, m_uci, weight, q_val))

print(f"[3/4] Prepared {len(training_samples):,} curated training samples (vetoed blunders filtered out).")

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

# Neural Architecture: 6-block Deep ResNet Policy & Value Network
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

# Step 4: Train on GPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[4/4] Starting Training on: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True

dataset = CuratedChessDataset(training_samples)
batch_size = 512 if torch.cuda.is_available() else 64
loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, pin_memory=torch.cuda.is_available())

model = TrueEngineChessNet().to(device)

# Load existing weights if available to warm-start
if os.path.exists(MODEL_SAVE_PATH):
    try:
        ckpt = torch.load(MODEL_SAVE_PATH, map_location=device)
        if "model_state_dict" in ckpt:
            model.load_state_dict(ckpt["model_state_dict"])
            print("  -> Warm-started from existing checkpoint!")
    except Exception:
        pass

optimizer = optim.AdamW(model.parameters(), lr=8e-4, weight_decay=1e-4)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=10, eta_min=1e-5)
criterion_policy = nn.CrossEntropyLoss(reduction="none")
criterion_value = nn.MSELoss()
scaler = torch.amp.GradScaler('cuda', enabled=torch.cuda.is_available())

epochs = 5
print(f"\nTraining {epochs} epochs over {len(training_samples):,} positions (Batch Size: {batch_size})...")

for epoch in range(1, epochs + 1):
    model.train()
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    t0 = time.time()

    for x, target_m, weights, q_vals in loader:
        x = x.to(device, non_blocking=True)
        target_m = target_m.to(device, non_blocking=True)
        weights = weights.to(device, non_blocking=True)
        q_vals = q_vals.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        with torch.amp.autocast('cuda', enabled=torch.cuda.is_available()):
            policy_logits, value_preds = model(x)
            loss_p = (criterion_policy(policy_logits, target_m) * weights).mean()
            loss_v = criterion_value(value_preds, q_vals)
            loss = loss_p + 0.5 * loss_v

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item() * x.size(0)
        preds = torch.argmax(policy_logits, dim=-1)
        total_correct += (preds == target_m).sum().item()
        total_count += x.size(0)

    scheduler.step()
    elapsed = time.time() - t0
    acc = (total_correct / total_count) * 100.0
    print(f"  Epoch [{epoch}/{epochs}] | Loss: {total_loss/total_count:.4f} | Accuracy: {acc:.2f}% | Speed: {total_count/elapsed:.0f} pos/sec | Time: {elapsed:.2f}s")

# Save Checkpoint
torch.save({
    "model_state_dict": model.state_dict(),
    "arch": "ResNet-6x128-PolicyValue",
    "samples_trained": len(training_samples),
    "timestamp": time.time()
}, MODEL_SAVE_PATH)
print(f"\n[Saved] PyTorch Model checkpoint saved to: {MODEL_SAVE_PATH}")

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
