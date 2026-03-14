"""Quick test to see if main.py can start."""
import sys
import traceback
try:
    print("Importing main...", flush=True)
    import main
    print("Running...", flush=True)
    sys.argv = ["main.py", "--show-window"]
    main.run()
except Exception as e:
    traceback.print_exc()
    print(f"\nERROR: {e}", flush=True)
finally:
    input("\nPress Enter to close...")
