import os
import sys
import subprocess

def run_tests():
    print("Searching for Python interpreter...")
    # Try common python commands
    py_cmds = ["python", "py", "python3"]
    py_path = None
    
    for cmd in py_cmds:
        try:
            # Check if command works and isn't just the Windows Store placeholder
            result = subprocess.run([cmd, "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                py_path = cmd
                print(f"Found: {cmd}")
                break
        except Exception:
            continue
            
    if not py_path:
        print("Error: Could not find a working Python interpreter.")
        print("Please ensure Python is installed and added to your PATH.")
        return

    print(f"Using {py_path} to run tests...")
    
    # Install dependencies if needed (optional, maybe skip to avoid noise)
    # subprocess.run([py_path, "-m", "pip", "install", "pytest", "pytest-flask", "pytest-mock"])
    
    # Run pytest
    subprocess.run([py_path, "-m", "pytest", "tests/"])

if __name__ == "__main__":
    run_tests()
