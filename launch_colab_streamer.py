import subprocess, os

# Install deps if not present
try:
    import chess
except ImportError:
    print("Installing python-chess and stockfish...")
    subprocess.run("pip install -q python-chess stockfish", shell=True)
    subprocess.run("apt-get update -qq && apt-get install -y -qq stockfish", shell=True)

# Check if streamer is already running
try:
    pids = subprocess.check_output("ps aux", shell=True).decode()
    if "t4_100m_selfplay_streamer.py" not in pids:
        print("Launching streamer...")
        p = subprocess.Popen(["python3", "-u", "/content/t4_100m_selfplay_streamer.py"], stdout=open("/content/streamer.log", "w"), stderr=subprocess.STDOUT)
        print("LAUNCHED PID:", p.pid)
    else:
        print("Streamer is ALREADY running!")
except Exception as e:
    print("Error:", e)
