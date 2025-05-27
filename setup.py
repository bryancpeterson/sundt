#!/usr/bin/env python3
"""
Setup script for Sundt RAG demo
"""

import os
import sys
import subprocess
import platform

def run_cmd(cmd, where=None):
    try:
        subprocess.run(cmd, shell=True, check=True, cwd=where, capture_output=True)
        return True
    except:
        return False

def main():
    print("Setting up Sundt RAG demo...")
    
    # Check Python
    if sys.version_info < (3, 8):
        print(f"Need Python 3.8+, found {sys.version_info.major}.{sys.version_info.minor}")
        return
    
    # Check Node
    if not run_cmd("node --version"):
        print("Need Node.js - download from nodejs.org")
        return
    
    print("✓ Requirements OK")
    
    # Setup venv
    if not os.path.exists("venv"):
        print("Creating virtual environment...")
        run_cmd(f"{sys.executable} -m venv venv")
    
    # Get venv paths
    is_windows = platform.system() == "Windows"
    if is_windows:
        python_cmd = "venv\\Scripts\\python"
        pip_cmd = "venv\\Scripts\\pip"
    else:
        python_cmd = "venv/bin/python"
        pip_cmd = "venv/bin/pip"
    
    # Install packages
    print("Installing packages...")
    run_cmd(f"{pip_cmd} install -r backend/requirements.txt")
    run_cmd("npm install", where="frontend")
    
    # Create .env
    if not os.path.exists("backend/.env"):
        os.makedirs("backend", exist_ok=True)
        with open("backend/.env", 'w') as f:
            f.write("""# OpenAI API Key
OPENAI_API_KEY=[add]

# Model settings (optional)
MODEL_NAME=gpt-4.1-mini
TEMPERATURE=0.2

# NVIDIA API Key (optional)
NVIDIA_API_KEY=[add]
""")
    
    # Create data dir
    os.makedirs("backend/data", exist_ok=True)
    
    # Create run script
    if is_windows:
        with open("start.bat", 'w') as f:
            f.write(f"""@echo off
start "Backend" cmd /k "cd backend && {python_cmd} api.py"
timeout 2 > nul
cd frontend && npm run dev
""")
        run_script = "start.bat"
    else:
        with open("start.sh", 'w') as f:
            f.write(f"""#!/bin/bash
cd backend && ../{python_cmd} api.py &
sleep 2
cd frontend && npm run dev
""")
        os.chmod("start.sh", 0o755)
        run_script = "./start.sh"
    
    print("✓ Setup complete")
    print()
    print("Next steps:")
    print("1. Add your OpenAI API key to backend/.env")
    print(f"2. Run: {run_script}")
    print("3. Open: http://localhost:3000")

if __name__ == "__main__":
    main()