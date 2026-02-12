import os
import subprocess

def get_tree():
    # Use find to get all files, then filter in python to avoid complex shell pipes in python string
    try:
        cmd = ["find", ".", "-maxdepth", "4", "-not", "-path", "*/.*"]
        result = subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()
        
        # Filter for our project directories
        whitelist = ["./configs", "./data", "./model", "./training", "./scripts", "./tests", "./.gitignore", "./.pre-commit-config.yaml"]
        
        filtered = []
        for line in result:
            if line == ".": continue
            # Check if line starts with any whitelisted path
            if any(line.startswith(w) for w in whitelist):
                # Extra cleanup: remove pycache
                if "__pycache__" in line: continue
                filtered.append(line)
        
        filtered.sort()
        
        # Simple tree formatting
        tree_str = ".\n"
        for path in filtered:
            depth = path.count(os.sep) - 1
            indent = "    " * depth
            basename = os.path.basename(path)
            tree_str += f"{indent}|-- {basename}\n"
            
        return tree_str
    except Exception as e:
        return f"Error generating tree: {e}"

def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except:
        return "Error reading file"

def main():
    tree = get_tree()
    
    config_yaml = read_file("configs/config.yaml")
    pre_commit = read_file(".pre-commit-config.yaml")
    model_conf = read_file("configs/model/default.yaml")
    
    md = f"""# Project Scaffolding Structure

## Directory Structure
```text
{tree}
```

## Key Configurations

### Main Config (Hydra)
`configs/config.yaml`
```yaml
{config_yaml}
```

### Model Config
`configs/model/default.yaml`
```yaml
{model_conf}
```

### Pre-commit Config
`.pre-commit-config.yaml`
```yaml
{pre_commit}
```
"""
    print(md)

if __name__ == "__main__":
    main()
