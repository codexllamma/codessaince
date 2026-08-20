import urllib.request
import zipfile
import os
import shutil

def fix_gpu_environment():
    scripts_dir = os.path.join("..", ".venv", "Scripts")
    zlib_target = os.path.join(scripts_dir, "zlibwapi.dll")
    
    # 1. Get zlibwapi.dll (The root cause of Error 126)
    if not os.path.exists(zlib_target):
        print("[*] Downloading required zlibwapi.dll...")
        urllib.request.urlretrieve("http://www.winimage.com/zLibDll/zlib123dllx64.zip", "zlib.zip")
        with zipfile.ZipFile("zlib.zip", 'r') as z:
            z.extract("dll_x64/zlibwapi.dll")
        shutil.move(os.path.join("dll_x64", "zlibwapi.dll"), zlib_target)
        print(f"[+] Placed zlibwapi.dll in {scripts_dir}")
    else:
        print("[+] zlibwapi.dll already exists.")

    # 2. Copy ALL NVIDIA CUDA/CUBLAS DLLs
    nvidia_dir = os.path.join("..", ".venv", "Lib", "site-packages", "nvidia")
    print("[*] Sweeping site-packages for remaining CUDA DLLs...")
    
    count = 0
    for root, _, files in os.walk(nvidia_dir):
        for file in files:
            if file.endswith(".dll"):
                src = os.path.join(root, file)
                dst = os.path.join(scripts_dir, file)
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    count += 1
                    
    print(f"[+] Copied {count} additional CUDA DLLs to {scripts_dir}")
    print("\n[✅] GPU ENVIRONMENT FULLY PATCHED! Run the orchestrator now.")

if __name__ == "__main__":
    fix_gpu_environment()