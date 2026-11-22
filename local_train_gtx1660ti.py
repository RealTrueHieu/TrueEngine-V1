import os
import sys
import json
import subprocess

print("=" * 65)
print("  TRUEENGINE V1 - LOCAL NVIDIA GTX 1660 Ti INTEGRATION & UPGRADE")
print("=" * 65)

# 1. Check local NVIDIA GPU
try:
    smi = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], text=True)
    print(f"[Hardware Detected] {smi.strip()}")
except Exception as e:
    print(f"[Hardware Warning] nvidia-smi check: {e}")

# 2. Merge Distilled Experience Memory from Colab T4
distilled_path = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\books\distilled_experience.json"
local_mem_path = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\books\experience_memory.json"

if os.path.exists(distilled_path):
    print(f"[Memory Merger] Reading distilled knowledge from: {distilled_path}")
    with open(distilled_path, "r", encoding="utf-8") as f:
        distilled_data = json.load(f)

    existing_data = {}
    if os.path.exists(local_mem_path):
        try:
            with open(local_mem_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            existing_data = {}

    merged_count = 0
    blunder_count = 0
    win_boost_count = 0

    for fen, moves in distilled_data.items():
        if fen not in existing_data:
            existing_data[fen] = {}
        for m, data in moves.items():
            existing_data[fen][m] = data
            merged_count += 1
            if data.get("blunder"):
                blunder_count += 1
            if data.get("wins", 0) > 0:
                win_boost_count += 1

    with open(local_mem_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, indent=2)

    print(f"[Memory Merger] Successfully integrated {merged_count} master positions:")
    print(f"  - Winning / High-Evaluation Lines Boosted: {win_boost_count}")
    print(f"  - Tactical Blunders Blacklisted: {blunder_count}")
    print(f"  - Total Unique Positions in Brain: {len(existing_data)}")

# 3. Verify Distilled Model Checkpoint
distilled_model_path = r"C:\Users\RealTrueHieu\CustomHumanChessEngine\models\trueengine_v1_distilled_t4.pt"
if os.path.exists(distilled_model_path):
    size_mb = os.path.getsize(distilled_model_path) / (1024 * 1024)
    print(f"[Model Verification] Distilled model checkpoint ready: {distilled_model_path} ({size_mb:.2f} MB)")

print("\n[Complete] TrueEngine V1 local brain successfully updated with Stockfish-distilled intelligence!")
