#!/usr/bin/env python3
"""
fetch_hf_model.py
Downloads the latest TrueEngine V1 trained weights & ONNX models from Hugging Face Hub
(TrueHieu/trueengine-v1-models) into models/.
Zero Local GPU required.
"""

import os
import sys
from huggingface_hub import HfApi, hf_hub_download, list_repo_files

def get_hf_token():
    token = os.getenv("HF_TOKEN")
    if token:
        return token
    token_file = os.path.expanduser("~/.huggingface/token")
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            return f.read().strip()
    return None

HF_TOKEN = get_hf_token()
MODEL_REPO = "TrueHieu/trueengine-v1-models"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

def fetch_latest_model():
    print(f"[*] Connecting to Hugging Face Hub: {MODEL_REPO}")
    api = HfApi(token=HF_TOKEN)
    
    try:
        files = list_repo_files(repo_id=MODEL_REPO, repo_type="model", token=HF_TOKEN)
    except Exception as e:
        print(f"[!] Warning: Unable to list repo files: {e}")
        return False
        
    model_files = [f for f in files if f.startswith("checkpoints/") or f.endswith((".pt", ".onnx", ".bin"))]
    if not model_files:
        print("[-] No model files found in repository yet.")
        return False
        
    print(f"[+] Found {len(model_files)} model files in repository:")
    for f in model_files:
        print(f"    - {f}")
        
    for f in model_files:
        print(f"[*] Downloading {f}...")
        try:
            local_path = hf_hub_download(
                repo_id=MODEL_REPO,
                filename=f,
                repo_type="model",
                token=HF_TOKEN,
                local_dir=MODELS_DIR
            )
            print(f"[+] Saved to: {local_path}")
        except Exception as e:
            print(f"[!] Error downloading {f}: {e}")
            
    print("[+] Model fetch completed.")
    return True

if __name__ == "__main__":
    fetch_latest_model()
