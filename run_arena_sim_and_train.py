import os
import sys
import time
import json
import random
import multiprocessing
import subprocess
import chess
import chess.engine
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

print("=" * 65)
print("  TRUEENGINE V1 - PARALLEL ARENA SIMULATION & DISTILLATION (T4)")
print("=" * 65)

STOCKFISH_PATH = "/usr/games/stockfish"
if not os.path.exists(STOCKFISH_PATH):
    STOCKFISH_PATH = "/usr/bin/stockfish"

print(f"[Stockfish] Using engine: {STOCKFISH_PATH}")

OPENINGS = [
    ("Sicilian Najdorf", "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2"),
    ("King's Indian Defense", "rnbqkb1r/pppppp1p/5np1/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq - 0 3"),
    ("Ruy Lopez", "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"),
    ("French Defense", "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"),
    ("Queen's Gambit Declined", "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq c3 0 2"),
    ("Caro-Kann Defense", "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"),
    ("English Opening", "rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq c3 0 1"),
    ("Italian Game", "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"),
    ("Grünfeld Defense", "rnbqkb1r/ppp1pp1p/5np1/3p4/2PP4/2N5/PP2PPPP/R1BQKBNR w KQkq d6 0 4"),
    ("Nimzo-Indian Defense", "rnbqk2r/pppp1ppp/4pn2/8/1bPP4/2N5/PP2PPPP/R1BQKBNR w KQkq - 2 4")
]

def simulate_arena_game(game_id, max_plies=40):
    opening_name, start_fen = random.choice(OPENINGS)
    board = chess.Board(start_fen)
    positions = []

    try:
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        engine.configure({"Threads": 1, "Hash": 16})
    except Exception as e:
        return []

    try:
        ply = 0
        while not board.is_game_over() and ply < max_plies:
            fen_before = board.fen()
            legal = list(board.legal_moves)
            if not legal:
                break

            limit = chess.engine.Limit(nodes=3000)
            info = engine.analyse(board, limit)
            best_move = info.get("pv", [None])[0]
            score_obj = info.get("score")
            score_cp = score_obj.white().score(mate_score=10000) if score_obj else 0
            if score_cp is None:
                score_cp = 0

            if best_move is None or best_move not in legal:
                best_move = random.choice(legal)

            positions.append({
                "fen": fen_before,
                "best_move": best_move.uci(),
                "score_cp": max(-1000, min(1000, score_cp)),
                "ply": ply,
                "opening": opening_name
            })

            # Player move selection:
            # 80% Stockfish top move, 20% alternative master branch to explore refutations
            if random.random() < 0.80 or len(legal) == 1:
                chosen_move = best_move
            else:
                chosen_move = random.choice(legal[:min(4, len(legal))])

            board.push(chosen_move)
            ply += 1
    finally:
        engine.quit()

    return positions

def run_parallel_arena_simulation(total_games=120):
    print(f"\n[Simulation] Spawning parallel arena matches across 4 workers ({total_games} games)...")
    t0 = time.time()
    
    with multiprocessing.Pool(processes=4) as pool:
        results = pool.map(simulate_arena_game, range(total_games))

    all_positions = []
    for r in results:
        all_positions.extend(r)

    elapsed = time.time() - t0
    spawn_rate = len(all_positions) / max(0.001, elapsed)
    print(f"[Simulation Complete] Generated {len(all_positions)} master positions in {elapsed:.2f}s!")
    print(f"[Throughput] Spawn rate: {spawn_rate:.1f} positions/second.")

    sim_file = "/content/arena_simulated_games.jsonl"
    with open(sim_file, "w", encoding="utf-8") as f:
        for p in all_positions:
            f.write(json.dumps(p) + "\n")
    print(f"[Saved] Arena dataset saved to: {sim_file}")
    return all_positions

class ResBlock(nn.Module):
    def __init__(self, channels=128):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        residual = x
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += residual
        return self.relu(out)

class TrueEngineDistillNet(nn.Module):
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
        p = p.view(p.size(0), -1)
        policy_logits = self.policy_fc(p)

        v = self.relu(self.value_bn(self.value_conv(out)))
        v = v.view(v.size(0), -1)
        v = self.relu(self.value_fc1(v))
        value = self.tanh(self.value_fc2(v))

        return policy_logits, value

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

class DistillChessDataset(Dataset):
    def __init__(self, positions):
        self.data = positions

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        x = fen_to_tensor(item["fen"])
        target_move = uci_to_index(item["best_move"])
        target_val = item["score_cp"] / 400.0
        target_val = max(-1.0, min(1.0, target_val))
        return x, target_move, torch.tensor(target_val, dtype=torch.float32)

def distill_and_train(positions):
    use_cuda = torch.cuda.is_available()
    device = torch.device("cuda" if use_cuda else "cpu")
    print(f"\n[Distillation Training] Training on {device} ({len(positions)} positions)...")
    if use_cuda:
        print(f"[GPU Details] {torch.cuda.get_device_name(0)} (T4 Tensor Cores FP16 Enabled)")
    else:
        print("[Notice] GPU limit/unavailable. Seamless fallback to multi-core CPU mode.")

    dataset = DistillChessDataset(positions)
    batch_size = 512 if use_cuda else 64
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model = TrueEngineDistillNet(num_blocks=6, channels=128).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion_policy = nn.CrossEntropyLoss()
    criterion_value = nn.MSELoss()
    scaler = torch.amp.GradScaler('cuda', enabled=use_cuda)

    epochs = 5
    for epoch in range(1, epochs + 1):
        model.train()
        total_p_loss = 0.0
        total_v_loss = 0.0
        total_correct = 0
        total_samples = 0
        t0 = time.time()

        for x, target_moves, target_vals in loader:
            x = x.to(device)
            target_moves = target_moves.to(device)
            target_vals = target_vals.to(device).unsqueeze(1)

            optimizer.zero_grad(set_to_none=True)

            with torch.amp.autocast('cuda', enabled=use_cuda):
                p_logits, v_pred = model(x)
                p_loss = criterion_policy(p_logits, target_moves)
                v_loss = criterion_value(v_pred, target_vals)
                loss = p_loss + 0.5 * v_loss

            if use_cuda:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                optimizer.step()

            total_p_loss += p_loss.item() * x.size(0)
            total_v_loss += v_loss.item() * x.size(0)
            preds = torch.argmax(p_logits, dim=-1)
            total_correct += (preds == target_moves).sum().item()
            total_samples += x.size(0)

        elapsed = time.time() - t0
        speed = total_samples / max(0.001, elapsed)
        acc = (total_correct / total_samples) * 100.0
        print(f"Distill Epoch [{epoch}/{epochs}] | Policy Loss: {total_p_loss/total_samples:.4f} | Value Loss: {total_v_loss/total_samples:.4f} | Acc: {acc:.2f}% | Speed: {speed:.0f} pos/sec")

    # Save model checkpoint
    model_path = "/content/trueengine_v1_distilled_t4.pt"
    torch.save({
        "model_state": model.state_dict(),
        "arch": "TrueEngineDistillNet-ResNet6x128",
        "positions_trained": len(positions),
        "timestamp": time.time()
    }, model_path)
    print(f"\n[Model Export] Successfully saved distilled weights to: {model_path}")

    # Build distilled experience memory for TrueEngine V1
    print("\n[Experience Memory] Building distilled opening and tactical corrections...")
    distilled_memory = {}
    for p in positions:
        try:
            fen_key = chess.Board(p["fen"]).epd(use_en_passant=False)
            m = p["best_move"]
            score = p["score_cp"]
            if fen_key not in distilled_memory:
                distilled_memory[fen_key] = {}
            
            mult = 2.5 if score > 75 else (1.4 if score > -50 else 0.1)
            distilled_memory[fen_key][m] = {
                "visits": 1,
                "wins": 1 if score > 75 else 0,
                "draws": 1 if -75 <= score <= 75 else 0,
                "losses": 1 if score < -75 else 0,
                "q_val": round(score / 400.0, 3),
                "multiplier": mult,
                "blunder": (score < -150)
            }
        except Exception:
            continue

    memory_path = "/content/distilled_experience.json"
    with open(memory_path, "w", encoding="utf-8") as f:
        json.dump(distilled_memory, f, indent=2)
    print(f"[Memory Export] Exported {len(distilled_memory)} distilled positions to: {memory_path}")

if __name__ == "__main__":
    positions = run_parallel_arena_simulation(total_games=120)
    if positions:
        distill_and_train(positions)
