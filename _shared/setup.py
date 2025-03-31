#!/usr/bin/env python3
"""
BSW Project Template — Setup Script
Initializes BSW submodule + platform MCAL submodule, installs toolchain and pyOCD.

Usage:
    python _shared/setup.py --platform bsw-mcal-msp
    python _shared/setup.py                          # interactive menu
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
import tarfile
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────

SCRIPT_DIR   = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SHARED_DIR   = SCRIPT_DIR

# Check for workspace-level _shared first (server/CI env), fallback to repo-local
_WORKSPACE_SHARED = Path("/srv/workspaces/_shared/tools/compilers")
_LOCAL_SHARED     = PROJECT_ROOT / "_shared" / "tools" / "compilers"

TOOLS_DIR = _WORKSPACE_SHARED if _WORKSPACE_SHARED.exists() else _LOCAL_SHARED

PLATFORMS_JSON = SHARED_DIR / "platforms.json"

# BSW submodule
BSW_REPO_URL = "https://github.com/Weldex-Corporation/bsw.git"
BSW_PATH     = PROJECT_ROOT / "bsw"

# ARM GCC download URLs (Arm GNU Toolchain 13.3.rel1)
ARM_GCC_VERSION = "13.3.rel1"
ARM_GCC_URLS = {
    "Linux":   "https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-x86_64-arm-none-eabi.tar.xz",
    "Darwin":  "https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-darwin-x86_64-arm-none-eabi.tar.xz",
    "Windows": "https://developer.arm.com/-/media/Files/downloads/gnu/13.3.rel1/binrel/arm-gnu-toolchain-13.3.rel1-mingw-w64-i686-arm-none-eabi.zip",
}

OS = platform.system()  # 'Linux', 'Darwin', 'Windows'

# ── Helpers ─────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[setup] {msg}")

def run(cmd, cwd=None, check=True):
    log(f"$ {' '.join(str(c) for c in cmd)}")
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=check)

def load_platforms():
    with open(PLATFORMS_JSON) as f:
        return json.load(f)

def select_platform(platforms, arg=None):
    keys = list(platforms.keys())
    if arg and arg in platforms:
        return arg
    print("\nAvailable platforms:")
    for i, key in enumerate(keys, 1):
        print(f"  [{i}] {key} — {platforms[key]['description']}")
    while True:
        try:
            choice = int(input("\nSelect platform number: "))
            if 1 <= choice <= len(keys):
                return keys[choice - 1]
        except (ValueError, KeyboardInterrupt):
            pass
        print("Invalid selection, try again.")

# ── Step 1: BSW submodule ───────────────────────────────────────────────────

def init_bsw():
    if (BSW_PATH / ".git").exists():
        log("BSW submodule already initialized — skipping")
        return
    log("Initializing BSW submodule...")
    # If bsw is already registered as a gitlink use update, else add
    gitmodules = PROJECT_ROOT / ".gitmodules"
    if gitmodules.exists() and '[submodule "bsw"]' in gitmodules.read_text():
        run(["git", "submodule", "update", "--init", "bsw"], cwd=PROJECT_ROOT)
    else:
        run(["git", "submodule", "add", "--branch", "main", BSW_REPO_URL, "bsw"], cwd=PROJECT_ROOT)
    log("BSW submodule ready")

# ── Step 2: Platform MCAL submodule ─────────────────────────────────────────

def init_platform(platform_cfg):
    submodule_path = platform_cfg["submodule_path"]  # e.g. platform/bsw-mcal-msp
    target = BSW_PATH / submodule_path
    if (target / ".git").exists():
        log(f"Platform submodule '{submodule_path}' already initialized — skipping")
        return
    log(f"Initializing platform submodule: {submodule_path}")
    run(["git", "submodule", "update", "--init", submodule_path], cwd=BSW_PATH)
    log(f"Platform '{submodule_path}' ready")

# ── Step 3: ARM GCC toolchain ────────────────────────────────────────────────

def install_toolchain():
    gcc_bin = TOOLS_DIR / "gnu-arm" / ARM_GCC_VERSION / "bin" / (
        "arm-none-eabi-gcc.exe" if OS == "Windows" else "arm-none-eabi-gcc"
    )
    if gcc_bin.exists():
        log(f"ARM GCC already present: {gcc_bin}")
        return

    if not ARM_GCC_URLS.get(OS):
        log(f"WARNING: No ARM GCC URL for OS '{OS}'. Install manually.")
        return

    url      = ARM_GCC_URLS[OS]
    filename = url.split("/")[-1]
    dest_dir = TOOLS_DIR / "gnu-arm" / ARM_GCC_VERSION
    dest_dir.mkdir(parents=True, exist_ok=True)
    archive  = TOOLS_DIR / filename

    log(f"Downloading ARM GCC {ARM_GCC_VERSION} for {OS}...")
    urllib.request.urlretrieve(url, archive, reporthook=_progress)
    print()

    log(f"Extracting to {dest_dir} ...")
    if filename.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest_dir)
    else:
        with tarfile.open(archive) as t:
            t.extractall(dest_dir)
    archive.unlink()
    log("ARM GCC installed")

def _progress(block, block_size, total):
    done = block * block_size
    pct  = min(100, int(done * 100 / total)) if total > 0 else 0
    print(f"\r  {pct}% ({done // 1024} KB)", end="", flush=True)

# ── Step 4: pyOCD ────────────────────────────────────────────────────────────

def install_pyocd(platform_cfg):
    if shutil.which("pyocd"):
        log("pyOCD already installed")
    else:
        log("Installing pyOCD...")
        run([sys.executable, "-m", "pip", "install", "--quiet", "pyocd"])

    pack = platform_cfg.get("pyocd_pack")
    if pack:
        log(f"Installing pyOCD target pack: {pack}")
        run(["pyocd", "pack", "update"], check=False)
        run(["pyocd", "pack", "install", pack], check=False)

# ── Step 5: Verify ────────────────────────────────────────────────────────────

def verify():
    log("\n── Verification ──────────────────────────────")
    gcc_path = TOOLS_DIR / "gnu-arm" / ARM_GCC_VERSION / "bin"
    os.environ["PATH"] = str(gcc_path) + os.pathsep + os.environ.get("PATH", "")

    for cmd in [["arm-none-eabi-gcc", "--version"], ["pyocd", "--version"]]:
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).split("\n")[0]
            print(f"  ✓ {out}")
        except Exception:
            print(f"  ✗ {cmd[0]} not found")

    print(f"\n  BSW  : {BSW_PATH}")
    print(f"  Tools: {TOOLS_DIR}")
    print("\n  Ready! Next steps:")
    print("    cmake --preset <platform>")
    print("    ninja -C build/<platform>")
    print("    pyocd flash build/<platform>/led_blink.elf\n")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BSW Project Template Setup")
    parser.add_argument("--platform", help="Platform name (e.g. bsw-mcal-msp)")
    parser.add_argument("--skip-toolchain", action="store_true",
                        help="Skip ARM GCC download (use system/pre-installed)")
    args = parser.parse_args()

    platforms = load_platforms()
    chosen    = select_platform(platforms, args.platform)
    cfg       = platforms[chosen]

    log(f"Platform: {chosen} — {cfg['description']}")

    init_bsw()
    init_platform(cfg)
    if not args.skip_toolchain:
        install_toolchain()
    install_pyocd(cfg)
    verify()

if __name__ == "__main__":
    main()
