import subprocess
import sys
import os

if __name__ == "__main__":
    # Launch the training with the cloud test configuration using subprocess
    config_path = "configs/cloud_test_config.yaml"
    launch_script_path = "training/launch.py"
    
    if not os.path.exists(launch_script_path):
        print(f"Error: Launch script not found at {launch_script_path}")
        sys.exit(1)
        
    command = [sys.executable, launch_script_path, "--config", config_path]
    
    print(f"Executing command: {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
        
    if result.returncode != 0:
        print(f"\nTraining failed with return code {result.returncode}")
        sys.exit(result.returncode)
    else:
        print("\nTraining finished successfully.")
