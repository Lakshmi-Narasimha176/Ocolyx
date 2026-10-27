import os
import sys
import json
import urllib.request
import urllib.error

import subprocess

def get_git_token():
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True,
            text=True,
            check=True
        )
        for line in proc.stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""

TOKEN = get_git_token()
REPO = "Lakshmi-Narasimha176/Ocolyx"
TAG = "v0.1.1"
RELEASE_NAME = "Ocolyx v0.1.1 - Ultra-Low RAM, Battery & Storage Optimized Desktop App"

RELEASE_BODY = """## Ocolyx v0.1.1 - High Performance & Resource-Optimized Desktop App 🚀

This release delivers major optimizations reducing **RAM usage**, **battery consumption**, and **disk storage footprint** across the application.

---

### 🌟 What's New & Optimized in v0.1.1:

#### 1. ⚡ Ultra-Low RAM Consumption
- **Ring-Buffer Bloat Eliminated**: Restricted Windows DirectShow webcam capture buffer to a single frame (`cv2.CAP_PROP_BUFFERSIZE = 1`), eliminating unneeded multi-frame memory caching.
- **Optimized Capture Resolution**: Streamlined resolution to 480x360 @ 15 FPS, cutting raw per-frame video memory by 44%.
- **Tkinter Widget Thrashing Fixed**: Eliminated repeated widget teardown and regeneration every 500ms in the session log; UI updates now only occur on data changes and when viewing the log tab.
- **Aggressive Memory Reclamation**: Immediate garbage collection (`gc.collect()`) after loading the 95 MB dlib landmark predictor, plus periodic generational cleanup in background loops.

#### 2. 🔋 Minimal Battery & CPU Impact
- **Frame Re-Processing Bug Resolved**: Fixed redundant landmark processing loop; the detector now strictly synchronizes with genuine new camera frames, saving ~90% unnecessary CPU cycles.
- **Temporal Bounding Box Caching**: Reuses face bounding boxes for 9 out of 10 frames, reducing costly dlib HOG frontal face detector invocations by ~90%.
- **Downscaled Face Detection**: Performs HOG detection on 0.5x scaled grayscale frames for a 4x detection speedup.
- **Adaptive Idle Throttle**: When away from your desk (>15 frames with no face detected), Ocolyx automatically drops into power-saver idle mode.

#### 3. 💾 Storage Footprint Reduction
- Cleaned intermediate build artifacts.
- Compressed default log retention from 30 days to 3 days with automated log rotation.
- Excluded unneeded scientific/deep-learning dependencies (`torch`, `scipy`, `mediapipe`, `notebook`, `pandas`) from runtime bundle.

#### 4. 🛡️ 100% Privacy-First Guarantee
- The live webcam video feed is completely hidden from the display screen and replaced with an animated Cyber Privacy Radar.
- All face and eye-aspect ratio tracking occurs 100% locally on your machine with zero external network transmission.

---

### 📦 Windows Desktop App Download:
1. Download **`Ocolyx-Windows.zip`** below.
2. Extract to any folder.
3. Launch **`Ocolyx.exe`** (or double-click the included **`Ocolyx.lnk`** desktop shortcut).

### 🌐 Live Web Version:
Run directly in your browser with zero installation:
👉 **[lakshmi-narasimha176.github.io/Ocolyx](https://lakshmi-narasimha176.github.io/Ocolyx/)**

### 🔐 Checksums & Verification:
- **`dist/Ocolyx-Windows.zip`**: SHA256 `15A15EE33BE6FB0E1B7011B020694352F56A2D2CF9379B31C6A2A79E3A2147E8`
"""

def create_or_get_release():
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Ocolyx-Release-Script"
    }
    
    # Check if release already exists
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/tags/{TAG}", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"Found existing release ID {data['id']}")
            return data
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    
    # Create new release
    payload = json.dumps({
        "tag_name": TAG,
        "target_commitish": "main",
        "name": RELEASE_NAME,
        "body": RELEASE_BODY,
        "draft": False,
        "prerelease": False
    }).encode('utf-8')
    
    post_req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases",
        data=payload,
        headers={**headers, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(post_req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print(f"Created new release {TAG} (ID: {data['id']}) at {data['html_url']}")
        return data

def upload_asset(release, file_path, name, content_type):
    upload_url_template = release["upload_url"]
    base_url = upload_url_template.split("{")[0]
    upload_url = f"{base_url}?name={name}"
    
    file_size = os.path.getsize(file_path)
    print(f"Uploading {name} ({file_size / (1024*1024):.2f} MB) to {upload_url} ...")
    
    # Check if asset already exists in release
    for asset in release.get("assets", []):
        if asset["name"] == name:
            print(f"Deleting existing asset {name} (ID: {asset['id']})...")
            del_req = urllib.request.Request(
                f"https://api.github.com/repos/{REPO}/releases/assets/{asset['id']}",
                headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "User-Agent": "Ocolyx-Release-Script"},
                method="DELETE"
            )
            with urllib.request.urlopen(del_req) as del_resp:
                print("Deleted existing asset.")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": content_type,
        "Content-Length": str(file_size),
        "User-Agent": "Ocolyx-Release-Script"
    }
    
    with open(file_path, "rb") as f:
        data = f.read()
    
    req = urllib.request.Request(upload_url, data=data, headers=headers)
    with urllib.request.urlopen(req) as resp:
        asset_data = json.loads(resp.read().decode('utf-8'))
        print(f"Successfully uploaded {name}: {asset_data['browser_download_url']}")
        return asset_data

if __name__ == "__main__":
    release = create_or_get_release()
    zip_path = os.path.abspath("dist/Ocolyx-Windows.zip")
    sha_path = os.path.abspath("dist/Ocolyx-Windows/SHA256SUMS.txt")
    
    if os.path.exists(zip_path):
        upload_asset(release, zip_path, "Ocolyx-Windows.zip", "application/zip")
    else:
        print(f"Error: {zip_path} not found!")
        sys.exit(1)
        
    if os.path.exists(sha_path):
        upload_asset(release, sha_path, "SHA256SUMS.txt", "text/plain")
        
    print("All release assets uploaded successfully!")
