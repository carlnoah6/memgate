#!/bin/bash
# Build Privacy Guard Plugin package for distribution

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building Privacy Guard Plugin Package${NC}"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "openclaw.plugin.json" ]; then
    echo -e "${RED}Error: Must run from plugin directory${NC}"
    exit 1
fi

# Create build directory
BUILD_DIR="dist"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "Building package structure..."

# Copy all necessary files
cp -r openclaw.plugin.json __init__.py index.js pyproject.toml README.md LICENSE install.sh "$BUILD_DIR/"
cp -r tests examples "$BUILD_DIR/"

# Create additional documentation
cp WIKI_CONTENT.md RESEARCH_SUMMARY.md "$BUILD_DIR/"

# Create package info file
cat > "$BUILD_DIR/PACKAGE_INFO.md" << EOF
# Privacy Guard Plugin Package

## Package Contents

### Core Files
- \`openclaw.plugin.json\` - Plugin manifest
- \`__init__.py\` - Python plugin implementation
- \`index.js\` - JavaScript plugin implementation
- \`pyproject.toml\` - Python package configuration
- \`README.md\` - Documentation
- \`LICENSE\` - MIT License
- \`install.sh\` - Installation script

### Documentation
- \`WIKI_CONTENT.md\` - Wiki documentation content
- \`RESEARCH_SUMMARY.md\` - Research summary
- \`PACKAGE_INFO.md\` - This file

### Development Files
- \`tests/\` - Test suite (50+ tests)
- \`examples/\` - Usage examples

## Installation

### From Source
\`\`\`bash
./install.sh
\`\`\`

### Manual Installation
1. Copy the plugin directory to OpenClaw plugins folder:
   \`\`\`bash
   cp -r . ~/.openclaw/plugins/privacy-guard
   \`\`\`

2. Update OpenClaw configuration (\`~/.openclaw/openclaw.json\`):
   \`\`\`json
   {
     "plugins": {
       "load": {
         "paths": ["~/.openclaw/plugins/privacy-guard"]
       },
       "entries": {
         "privacy-guard": {
           "enabled": true,
           "review": {"enabled": true},
           "knowledge_base": {"path": "./privacy/knowledge"},
           "defaults": {"visibility": "private"}
         }
       }
     }
   }
   \`\`\`

## Building for Distribution

To create a distributable package:

\`\`\`bash
# Build Python package
python -m build

# The package will be in dist/ directory:
# - openclaw-privacy-guard-1.0.0.tar.gz
# - openclaw_privacy_guard-1.0.0-py3-none-any.whl
\`\`\`

## Testing

Run the test suite:

\`\`\`bash
python3 test_plugin_structure.py
python3 -m pytest tests/ -v
\`\`\`

## Version Information

- Version: 1.0.0
- OpenClaw Compatibility: >= 2026.2.0
- License: MIT
- Author: Luna Team
- Build Date: $(date)

## Support

- Documentation: README.md
- Examples: examples/basic_usage.py
- Tests: tests/test_privacy_guard.py
- Issues: GitHub repository
EOF

# Create Python package structure
echo "Creating Python package..."
mkdir -p "$BUILD_DIR/privacy_guard"
cp __init__.py "$BUILD_DIR/privacy_guard/"
cat > "$BUILD_DIR/privacy_guard/__init__.py" << 'EOF'
"""
Privacy Guard Plugin for OpenClaw

A multi-user privacy isolation framework that provides context-based
knowledge access control, output review, and memory filtering.
"""

from .plugin import PrivacyGuardPlugin, create_plugin

__version__ = "1.0.0"
__all__ = ["PrivacyGuardPlugin", "create_plugin"]
EOF

# Move the main implementation
mv "$BUILD_DIR/__init__.py" "$BUILD_DIR/privacy_guard/plugin.py"

# Update pyproject.toml for proper packaging
cat > "$BUILD_DIR/pyproject.toml" << EOF
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "openclaw-privacy-guard"
version = "1.0.0"
description = "Multi-user privacy isolation framework for OpenClaw"
readme = "README.md"
authors = [
    {name = "Luna Team", email = "luna@example.com"}
]
license = {text = "MIT"}
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Security",
    "Topic :: Software Development :: Libraries :: Python Modules",
]
keywords = ["openclaw", "privacy", "security", "multi-user", "isolation"]
dependencies = []

[project.urls]
Homepage = "https://github.com/openclaw/privacy-guard"
Repository = "https://github.com/openclaw/privacy-guard"
Documentation = "https://docs.openclaw.dev/plugins/privacy-guard"
Issues = "https://github.com/openclaw/privacy-guard/issues"

[tool.setuptools]
packages = ["privacy_guard"]

[tool.setuptools.package-data]
"privacy_guard" = ["*.json", "*.md"]
EOF

# Create setup.py for backward compatibility
cat > "$BUILD_DIR/setup.py" << 'EOF'
from setuptools import setup, find_packages

setup(
    name="openclaw-privacy-guard",
    version="1.0.0",
    description="Multi-user privacy isolation framework for OpenClaw",
    author="Luna Team",
    license="MIT",
    packages=find_packages(),
    install_requires=[],
    python_requires=">=3.8",
)
EOF

# Create MANIFEST.in
cat > "$BUILD_DIR/MANIFEST.in" << 'EOF'
include *.md
include *.json
include *.sh
include *.py
recursive-include tests *.py
recursive-include examples *.py
EOF

# Create final archive
echo "Creating distribution archive..."
cd "$BUILD_DIR"
tar -czf "../privacy-guard-plugin-1.0.0.tar.gz" .
cd ..

echo -e "${GREEN}✓ Package built successfully!${NC}"
echo ""
echo "Package files:"
echo "  - privacy-guard-plugin-1.0.0.tar.gz (complete package)"
echo "  - dist/ (unpacked directory)"
echo ""
echo "Package contents:"
echo "  ✓ Plugin implementation (Python + JavaScript)"
echo "  ✓ Documentation (README, examples, tests)"
echo "  ✓ Installation script"
echo "  ✓ Configuration files"
echo ""
echo "Ready for distribution to ClawHub!"