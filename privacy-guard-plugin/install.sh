#!/bin/bash
# Privacy Guard Plugin Installer for OpenClaw

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Privacy Guard Plugin Installer${NC}"
echo "======================================"

# Check if OpenClaw is installed
if ! command -v openclaw &> /dev/null; then
    echo -e "${RED}Error: OpenClaw is not installed or not in PATH${NC}"
    echo "Please install OpenClaw first: https://docs.openclaw.dev/getting-started"
    exit 1
fi

# Get OpenClaw config directory
OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
PLUGINS_DIR="$OPENCLAW_HOME/plugins"
PLUGIN_NAME="privacy-guard"

echo "OpenClaw home: $OPENCLAW_HOME"
echo "Plugins directory: $PLUGINS_DIR"

# Create plugins directory if it doesn't exist
mkdir -p "$PLUGINS_DIR"

# Check if plugin already exists
if [ -d "$PLUGINS_DIR/$PLUGIN_NAME" ]; then
    echo -e "${YELLOW}Plugin already exists at $PLUGINS_DIR/$PLUGIN_NAME${NC}"
    read -p "Do you want to update it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    echo "Updating plugin..."
fi

# Copy plugin files
echo "Installing plugin files..."
cp -r "$(dirname "$0")" "$PLUGINS_DIR/$PLUGIN_NAME"

# Remove installer script from plugin directory
rm -f "$PLUGINS_DIR/$PLUGIN_NAME/install.sh"

# Check if Python is available
if command -v python3 &> /dev/null; then
    echo "Checking Python dependencies..."
    cd "$PLUGINS_DIR/$PLUGIN_NAME"
    
    # Check if virtual environment should be created
    if [ ! -d "venv" ]; then
        echo "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment and install dependencies
    echo "Installing Python dependencies..."
    source venv/bin/activate
    pip install -e . > /dev/null 2>&1 || {
        echo -e "${YELLOW}Warning: Could not install Python dependencies${NC}"
        echo "You may need to install them manually:"
        echo "  cd $PLUGINS_DIR/$PLUGIN_NAME && pip install -e ."
    }
    deactivate
fi

# Update OpenClaw configuration
CONFIG_FILE="$OPENCLAW_HOME/openclaw.json"
BACKUP_FILE="$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"

if [ -f "$CONFIG_FILE" ]; then
    echo "Backing up configuration to $BACKUP_FILE..."
    cp "$CONFIG_FILE" "$BACKUP_FILE"
    
    # Check if plugin is already in config
    if grep -q "\"$PLUGIN_NAME\"" "$CONFIG_FILE"; then
        echo -e "${YELLOW}Plugin already configured in openclaw.json${NC}"
    else
        echo "Updating OpenClaw configuration..."
        
        # Use Python to update JSON config
        python3 -c "
import json
import sys

config_file = '$CONFIG_FILE'
plugin_path = '$PLUGINS_DIR/$PLUGIN_NAME'

try:
    with open(config_file, 'r') as f:
        config = json.load(f)
except FileNotFoundError:
    config = {'plugins': {'load': {'paths': []}, 'entries': {}}}

# Ensure plugins structure exists
if 'plugins' not in config:
    config['plugins'] = {'load': {'paths': []}, 'entries': {}}
if 'load' not in config['plugins']:
    config['plugins']['load'] = {'paths': []}
if 'paths' not in config['plugins']['load']:
    config['plugins']['load']['paths'] = []
if 'entries' not in config['plugins']:
    config['plugins']['entries'] = {}

# Add plugin path if not already present
if plugin_path not in config['plugins']['load']['paths']:
    config['plugins']['load']['paths'].append(plugin_path)

# Add plugin configuration
config['plugins']['entries']['$PLUGIN_NAME'] = {
    'enabled': True,
    'review': {
        'enabled': True,
        'llm_self_review': False,
        'block_on_violation': True
    },
    'knowledge_base': {
        'path': './privacy/knowledge',
        'auto_tag': True
    },
    'defaults': {
        'visibility': 'private',
        'always_private_categories': [
            'calendar', 'family', 'finance', 'health',
            'auth', 'contact_private', 'dm_content'
        ]
    }
}

# Write updated config
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)
    
print('Configuration updated successfully')
" || echo -e "${YELLOW}Warning: Could not update configuration automatically${NC}"
    fi
else
    echo -e "${YELLOW}Warning: OpenClaw configuration file not found${NC}"
    echo "You need to manually add the plugin to your configuration."
fi

# Create knowledge directory structure
KNOWLEDGE_DIR="$OPENCLAW_HOME/workspace/privacy/knowledge"
echo "Creating knowledge directory structure..."
mkdir -p "$KNOWLEDGE_DIR"

# Create example knowledge files
EXAMPLE_USER="example_user"
USER_DIR="$KNOWLEDGE_DIR/$EXAMPLE_USER"
mkdir -p "$USER_DIR"

# Create example public knowledge
cat > "$USER_DIR/public.jsonl" << EOF
{"id": "k_001", "user": "$EXAMPLE_USER", "content": "会 Python 编程", "visibility": "public", "category": "skill", "source": "example", "created": "2026-02-10T07:00:00+08:00"}
{"id": "k_002", "user": "$EXAMPLE_USER", "content": "喜欢喝咖啡", "visibility": "public", "category": "preference", "source": "example", "created": "2026-02-10T07:00:00+08:00"}
EOF

# Create example private knowledge
cat > "$USER_DIR/private.jsonl" << EOF
{"id": "k_003", "user": "$EXAMPLE_USER", "content": "明天 14:00 要见客户", "visibility": "private", "category": "calendar", "source": "example", "created": "2026-02-10T07:00:00+08:00"}
{"id": "k_004", "user": "$EXAMPLE_USER", "content": "月薪 5000 元", "visibility": "private", "category": "finance", "source": "example", "created": "2026-02-10T07:00:00+08:00"}
EOF

echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Restart OpenClaw gateway: openclaw gateway restart"
echo "2. Verify plugin is loaded: openclaw plugin list"
echo "3. Test privacy guard functionality in a chat session"
echo ""
echo "Documentation: https://docs.openclaw.dev/plugins/privacy-guard"
echo "Issues: https://github.com/openclaw/privacy-guard/issues"