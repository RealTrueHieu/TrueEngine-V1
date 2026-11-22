import os, subprocess

print("Checking remote status...")
print("lc0 binary exists:", os.path.exists("/root/lc0/build/release/lc0"))
print("bt4 weights exist:", os.path.exists("/root/chess_bin/bt4.pb.gz"))
if os.path.exists("/root/chess_bin/bt4.pb.gz"):
    print("bt4 size:", os.path.getsize("/root/chess_bin/bt4.pb.gz"))

if os.path.exists("/root/lc0/build/release/lc0"):
    os.chmod("/root/lc0/build/release/lc0", 0o755)
    res = subprocess.run(["/root/lc0/build/release/lc0", "--help"], capture_output=True, text=True)
    print("LC0_READY:", res.stdout.splitlines()[0] if res.stdout else "NO_STDOUT")
else:
    ps = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    for l in ps.stdout.splitlines():
        if any(k in l for k in ["ninja", "c++", "git", "meson"]):
            print("RUNNING_PROC:", l[:120])
