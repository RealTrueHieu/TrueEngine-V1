import json

nb_path = r'C:\Users\RealTrueHieu\CustomHumanChessEngine\kaggle_t4\trueengine_dual_t4.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

cell_2_code = '''# 2. Deploy Pre-compiled Lc0 & Dependencies in 15 seconds!
import os, shutil, subprocess, time

os.makedirs("/root/chess_bin/stockfish", exist_ok=True)
os.makedirs("/root/lc0/build/release", exist_ok=True)

found_lc0 = None
for root, dirs, files in os.walk("/kaggle/input"):
    if "lc0" in files:
        found_lc0 = os.path.join(root, "lc0")
        break

if found_lc0:
    shutil.copy(found_lc0, "/root/lc0/build/release/lc0")
    print(f"✅ Loaded pre-compiled Lc0 binary from dataset: {found_lc0}", flush=True)
else:
    print("Downloading pre-compiled Lc0 CUDA binary from GitHub CDN...", flush=True)
    subprocess.run(["curl", "-sL", "https://github.com/RealTrueHieu/TrueEngine-V1/releases/download/v1.0.0-bin/lc0", "-o", "/root/lc0/build/release/lc0"])

os.chmod("/root/lc0/build/release/lc0", 0o755)
print("✅ Lc0 binary ready! Size:", os.path.getsize("/root/lc0/build/release/lc0"), flush=True)

# Apt dependencies & Stockfish
!apt-get update -qq && apt-get install -y -qq stockfish curl > /dev/null 2>&1
!ln -sf /usr/games/stockfish /root/chess_bin/stockfish/stockfish-ubuntu-x86-64-avx2
!pip install -q fastapi uvicorn python-chess requests

# Download cloudflared
if not os.path.exists("/usr/local/bin/cloudflared"):
    !curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared

# Download BT4 Grandmaster network weights
bt4_url = "https://storage.lczero.org/files/networks-contrib/BT4-1024x15x32h-swa-6147500-policytune-332.pb.gz"
print("Downloading BT4 Grandmaster Supernet weights...", flush=True)
!curl -sL $bt4_url -o /root/chess_bin/bt4.pb.gz
print("✅ BT4 weights ready! Size:", os.path.getsize("/root/chess_bin/bt4.pb.gz"), flush=True)
'''

nb['cells'][2]['source'] = [line + '\n' for line in cell_2_code.split('\n')[:-1]] + [cell_2_code.split('\n')[-1]]

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print('Cell 2 updated successfully!')
