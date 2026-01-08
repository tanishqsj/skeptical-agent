import os
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox

# 1. Load your keys
load_dotenv() 

# Check if key exists
if not os.getenv("E2B_API_KEY"):
    print("❌ Error: E2B_API_KEY not found in .env file")
    exit()

print(f"🚀 Connecting to E2B Cloud Sandbox...")

# --- THE FIX IS HERE ---
# Use .create() instead of Sandbox()
with Sandbox.create() as sandbox:
    print("✅ Sandbox created! Running remote Python code...")
    
    code = """
import sys
import platform

print(f"Hello from inside the Sandbox!")
print(f"OS: {platform.system()} {platform.release()}")
print(f"Python Version: {sys.version.split()[0]}")

x = 10 * 5
print(f"Calculation Result: {x}")
    """
    
    execution = sandbox.run_code(code)
    
    if execution.error:
        print("❌ Code Failed:", execution.error)
    else:
        print("\n--- SANDBOX OUTPUT ---")
        print(execution.logs.stdout)
        print("----------------------")

print("🔌 Connection closed.")