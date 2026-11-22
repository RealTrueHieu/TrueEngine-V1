import json
import os

cpu_metadata = {
    "id": "truehieu/trueengine-cpu-data-spawner",
    "title": "TrueEngine CPU High-Throughput Data Spawner",
    "code_file": "trueengine_cpu_data_spawner.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": "true",
    "enable_gpu": "false",
    "enable_tpu": "false",
    "enable_internet": "true",
    "dataset_sources": [],
    "competition_sources": [],
    "kernel_sources": [],
    "model_sources": []
}

with open("/data/workspace/TrueEngine-V1/kaggle_cpu_spawner/kernel-metadata.json", "w") as f:
    json.dump(cpu_metadata, f, indent=2)

gpu_metadata = {
    "id": "truehieu/trueengine-burst-gpu-trainer",
    "title": "TrueEngine Burst GPU Trainer",
    "code_file": "trueengine_burst_gpu_trainer.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": "true",
    "enable_gpu": "true",
    "enable_tpu": "false",
    "enable_internet": "true",
    "dataset_sources": [],
    "competition_sources": [],
    "kernel_sources": [],
    "model_sources": []
}

with open("/data/workspace/TrueEngine-V1/kaggle_gpu_trainer/kernel-metadata.json", "w") as f:
    json.dump(gpu_metadata, f, indent=2)

print("Metadata files created successfully.")
