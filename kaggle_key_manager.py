#!/usr/bin/env python3
"""
Kaggle Key Rotation Manager for TrueEngine V1
Manages a pool of Kaggle API tokens (3x 30-hour GPU accounts = 90h reserve)
"""

import os
import json
import urllib.request
from pathlib import Path

POOL_FILE = Path("/data/workspace/TrueEngine-V1/config/kaggle_key_pool.json")
KAGGLE_DIR = Path.home() / ".kaggle"
KAGGLE_JSON = KAGGLE_DIR / "kaggle.json"

def load_pool():
    if not POOL_FILE.exists():
        raise FileNotFoundError(f"Pool file {POOL_FILE} not found.")
    with open(POOL_FILE, "r") as f:
        return json.load(f)

def save_pool(pool):
    with open(POOL_FILE, "w") as f:
        json.dump(pool, f, indent=2)

def test_token(token: str) -> bool:
    try:
        req = urllib.request.Request(
            "https://api.kaggle.com/v1/datasets/list?pageSize=1",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            return resp.status == 200
    except Exception:
        return False

def apply_key(key_obj):
    KAGGLE_DIR.mkdir(parents=True, exist_ok=True)
    token = key_obj["token"]
    username = key_obj.get("username", "trntrungminhhiu")
    
    # Write kaggle.json
    with open(KAGGLE_JSON, "w") as f:
        json.dump({"username": username, "key": token}, f)
    os.chmod(KAGGLE_JSON, 0o600)
    
    # Write access_token
    token_file = KAGGLE_DIR / "access_token"
    with open(token_file, "w") as f:
        f.write(token.strip())
    os.chmod(token_file, 0o600)

def rotate_key():
    pool = load_pool()
    idx = pool.get("active_key_index", 0)
    keys = pool.get("keys", [])
    if not keys:
        raise ValueError("No keys in pool.")
    
    next_idx = (idx + 1) % len(keys)
    pool["active_key_index"] = next_idx
    selected = keys[next_idx]
    save_pool(pool)
    apply_key(selected)
    print(f"[✓] Rotated to Key {selected['id']}: {selected['token'][:10]}... ({selected['gpu_quota_hours']}h GPU quota)")
    return selected

def status():
    pool = load_pool()
    print("=" * 65)
    print("     TRUEENGINE V1 - KAGGLE GPU KEY ROTATION POOL (3-KEY)")
    print("=" * 65)
    active_idx = pool.get("active_key_index", 0)
    for i, k in enumerate(pool.get("keys", [])):
        is_active = " [ACTIVE]" if i == active_idx else ""
        valid = test_token(k["token"])
        valid_str = "VALID (HTTP 200)" if valid else "INVALID/EXPIRED"
        print(f"Key {k['id']}{is_active}:")
        print(f"  Token: {k['token'][:10]}...{k['token'][-6:]}")
        print(f"  Quota: {k.get('gpu_quota_hours', 30.0)} Hours GPU")
        print(f"  Status: {k.get('status', 'standby')} | {valid_str}")
        print(f"  Source: {k.get('source', 'unknown')}")
        print("-" * 65)
    total_hours = sum(k.get("gpu_quota_hours", 30.0) for k in pool.get("keys", []))
    print(f"Total Reserve Quota: {total_hours} Hours GPU (3 x 30h)")
    print("Current State: STANDBY (Active training running on Google Colab)")
    print("=" * 65)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "rotate":
        rotate_key()
    else:
        status()
