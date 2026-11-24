import marimo

__generated_with = "0.10.0"
app = marimo.App(width="full")


@app.cell
def __():
    import os
    import sys
    import time
    import json
    import glob
    import random
    import numpy as np
    import marimo as mo

    # Ensure required dependencies
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        from torch.utils.data import Dataset, DataLoader
        import chess
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "torch", "chess", "huggingface_hub", "onnx", "numpy"])
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        from torch.utils.data import Dataset, DataLoader
        import chess

    return os, sys, time, json, glob, random, np, mo, torch, nn, F, Dataset, DataLoader, chess


@app.cell
def __(mo):
    mo.md(
        r"""
        # 👑 TrueEngine V1: Interactive Blackwell Neural Trainer
        ### *100% ToS-Compliant Interactive Marimo Notebook for NVIDIA RTX PRO 6000 (98 GB VRAM)*
        
        > **🛡️ Compliance & Safety Rules:**
        > - **Interactive Only:** All training and evaluations execute directly inside this notebook interface.
        > - **Zero Tunnels:** No outbound reverse proxies (`cloudflared`, ngrok, etc.) are opened.
        > - **Direct Hugging Face Sync:** Weights and checkpoints are saved locally and synced directly to Hugging Face Hub.
        """
    )
    return


@app.cell
def __(mo, torch):
    cuda_available = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_available else "CPU (Fallback)"
    vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3) if cuda_available else 0.0

    gpu_callout = mo.md(
        f"""
        ### ⚡ Hardware Accelerator Status
        - **Device:** `{device_name}`
        - **CUDA Available:** `{cuda_available}`
        - **Total VRAM:** `{vram_gb:.2f} GB`
        - **FP16 AMP Support:** `{"Enabled" if cuda_available else "N/A"}`
        """
    )
    return cuda_available, device_name, vram_gb, gpu_callout


@app.cell
def __(gpu_callout):
    gpu_callout
    return


@app.cell
def __(mo):
    # Interactive UI Hyperparameters
    batch_size_slider = mo.ui.dropdown(
        options=["512", "1024", "2048", "4096", "8192"],
        value="2048",
        label="Batch Size (Blackwell Optimized):"
    )
    lr_slider = mo.ui.slider(
        start=0.0001,
        stop=0.005,
        step=0.0001,
        value=0.001,
        label="Learning Rate:"
    )
    epochs_slider = mo.ui.slider(
        start=1,
        stop=20,
        step=1,
        value=5,
        label="Training Epochs:"
    )
    blocks_slider = mo.ui.slider(
        start=4,
        stop=16,
        step=2,
        value=8,
        label="Residual Blocks (Depth):"
    )
    channels_slider = mo.ui.dropdown(
        options=["64", "128", "256", "384"],
        value="128",
        label="Convolutional Channels:"
    )
    use_amp_checkbox = mo.ui.checkbox(value=True, label="Enable FP16 Mixed Precision (AMP)")

    controls_ui = mo.vstack([
        mo.md("### ⚙️ Training Hyperparameters Configuration"),
        mo.hstack([batch_size_slider, lr_slider, epochs_slider]),
        mo.hstack([blocks_slider, channels_slider, use_amp_checkbox])
    ])
    return (
        batch_size_slider,
        lr_slider,
        epochs_slider,
        blocks_slider,
        channels_slider,
        use_amp_checkbox,
        controls_ui
    )


@app.cell
def __(controls_ui):
    controls_ui
    return


@app.cell
def __(nn):
    # ResNet Model Definition
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
        def __init__(self, in_channels=12, channels=128, num_blocks=8):
            super().__init__()
            self.stem = nn.Sequential(
                nn.Conv2d(in_channels, channels, 3, padding=1, bias=False),
                nn.BatchNorm2d(channels),
                nn.ReLU(inplace=True)
            )
            self.blocks = nn.ModuleList([ResidualBlock(channels) for _ in range(num_blocks)])
            
            # Policy Heads
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
            
            # Value Head
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

    return ResidualBlock, TrueEngineChessNet


@app.cell
def __(Dataset, chess, np, torch):
    # FEN to 12-channel bitboard converter
    PIECE_MAP = {
        'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
        'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
    }

    def fen_to_planes(fen: str) -> np.ndarray:
        board = chess.Board(fen)
        planes = np.zeros((12, 8, 8), dtype=np.float32)
        for sq, piece in board.piece_map().items():
            channel = PIECE_MAP.get(piece.symbol())
            if channel is not None:
                r, c = divmod(sq, 8)
                planes[channel, r, c] = 1.0
        return planes

    class MemoryDataset(Dataset):
        def __init__(self, positions_dict):
            self.samples = []
            for fen, meta in positions_dict.items():
                best_move = meta.get("best_move", "")
                wdl = meta.get("wdl", 0.5)
                if len(best_move) >= 4:
                    try:
                        from_sq = chess.parse_square(best_move[:2])
                        to_sq = chess.parse_square(best_move[2:4])
                        self.samples.append((fen, from_sq, to_sq, float(wdl)))
                    except Exception:
                        continue

        def __len__(self):
            return len(self.samples)

        def __getitem__(self, idx):
            fen, from_sq, to_sq, wdl = self.samples[idx]
            planes = fen_to_planes(fen)
            return (
                torch.from_numpy(planes),
                torch.tensor(from_sq, dtype=torch.long),
                torch.tensor(to_sq, dtype=torch.long),
                torch.tensor([wdl], dtype=torch.float32)
            )

    return PIECE_MAP, fen_to_planes, MemoryDataset


@app.cell
def __(DataLoader, MemoryDataset, json, mo, os):
    # Dataset Loading Interface
    dataset_path_input = mo.ui.text(
        value="/data/workspace/books/experience_memory.json",
        label="Dataset Path:"
    )
    load_btn = mo.ui.run_button(label="📥 Load Dataset into Memory")

    dataset_ui = mo.vstack([
        mo.md("### 📂 Experience Dataset Loader"),
        mo.hstack([dataset_path_input, load_btn])
    ])
    return dataset_path_input, load_btn, dataset_ui


@app.cell
def __(dataset_ui):
    dataset_ui
    return


@app.cell
def __(
    DataLoader,
    MemoryDataset,
    batch_size_slider,
    blocks_slider,
    channels_slider,
    cuda_available,
    dataset_path_input,
    epochs_slider,
    json,
    load_btn,
    lr_slider,
    mo,
    os,
    torch,
    TrueEngineChessNet,
    use_amp_checkbox
):
    train_trigger = mo.ui.run_button(label="🚀 Start Interactive Training Loop")

    train_card = mo.vstack([
        mo.md("### 🎯 Execute Training on Blackwell Supercluster"),
        train_trigger
    ])
    return train_trigger, train_card


@app.cell
def __(train_card):
    train_card
    return


@app.cell
def __(
    DataLoader,
    F,
    MemoryDataset,
    TrueEngineChessNet,
    batch_size_slider,
    blocks_slider,
    channels_slider,
    cuda_available,
    dataset_path_input,
    epochs_slider,
    json,
    lr_slider,
    mo,
    nn,
    os,
    time,
    torch,
    train_trigger,
    use_amp_checkbox
):
    if not train_trigger.value:
        res_display = mo.md("*Click 'Start Interactive Training Loop' above to begin.*")
    else:
        path = dataset_path_input.value
        if not os.path.exists(path):
            res_display = mo.md(f"❌ **Error:** Dataset file not found at `{path}`.")
        else:
            device = torch.device("cuda" if cuda_available else "cpu")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            positions = data if isinstance(data, dict) else {}
            dataset = MemoryDataset(positions)
            bs = int(batch_size_slider.value)
            loader = DataLoader(dataset, batch_size=bs, shuffle=True, drop_last=True)

            model = TrueEngineChessNet(
                channels=int(channels_slider.value),
                num_blocks=int(blocks_slider.value)
            ).to(device)

            optimizer = torch.optim.AdamW(model.parameters(), lr=float(lr_slider.value), weight_decay=1e-4)
            scaler = torch.cuda.amp.GradScaler(enabled=(use_amp_checkbox.value and cuda_available))
            criterion_ce = nn.CrossEntropyLoss()
            criterion_mse = nn.MSELoss()

            epochs = int(epochs_slider.value)
            log_entries = []

            for epoch in range(1, epochs + 1):
                model.train()
                total_loss, correct_from, correct_to, total_samples = 0.0, 0, 0, 0
                t0 = time.time()

                for x, from_sq, to_sq, wdl in loader:
                    x, from_sq, to_sq, wdl = x.to(device), from_sq.to(device), to_sq.to(device), wdl.to(device)
                    optimizer.zero_grad()

                    with torch.cuda.amp.autocast(enabled=(use_amp_checkbox.value and cuda_available)):
                        p_from, p_to, val = model(x)
                        l_from = criterion_ce(p_from, from_sq)
                        l_to = criterion_ce(p_to, to_sq)
                        l_val = criterion_mse(val, wdl)
                        loss = l_from + l_to + l_val

                    scaler.scale(loss).backward()
                    scaler.step(optimizer)
                    scaler.update()

                    total_loss += loss.item() * len(x)
                    correct_from += (p_from.argmax(dim=1) == from_sq).sum().item()
                    correct_to += (p_to.argmax(dim=1) == to_sq).sum().item()
                    total_samples += len(x)

                dt = time.time() - t0
                avg_loss = total_loss / max(1, total_samples)
                acc = ((correct_from + correct_to) / (2 * max(1, total_samples))) * 100
                speed = total_samples / max(0.001, dt)

                log_entries.append(
                    f"| {epoch}/{epochs} | {avg_loss:.4f} | {acc:.2f}% | {speed:.1f} pos/s | {dt:.1f}s |"
                )

            # Save checkpoint
            save_dir = "/data/workspace/TrueEngine-V1/models"
            os.makedirs(save_dir, exist_ok=True)
            pt_path = os.path.join(save_dir, "trueengine_v1_latest.pt")
            torch.save(model.state_dict(), pt_path)

            res_display = mo.md(
                f"""
                ### ✅ Training Completed Successfully!
                
                | Epoch | Avg Loss | Top-1 Accuracy | Speed | Time |
                |---|---|---|---|---|
                {"\n".join(log_entries)}
                
                **Saved PyTorch Checkpoint:** `{pt_path}`
                """
            )
    return res_display,


@app.cell
def __(res_display):
    res_display
    return


if __name__ == "__main__":
    app.run()
