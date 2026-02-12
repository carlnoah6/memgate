#!/usr/bin/env python3
"""
Test Privacy Guard Plugin structure and basic functionality
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_plugin_files():
    """Test that all required plugin files exist"""
    print("Testing plugin file structure...")
    
    required_files = [
        "openclaw.plugin.json",
        "__init__.py",
        "README.md",
        "pyproject.toml",
        "install.sh",
        "tests/test_privacy_guard.py",
        "examples/basic_usage.py",
    ]
    
    all_exist = True
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✓ {file}")
        else:
            print(f"  ✗ {file} - MISSING")
            all_exist = False
    
    return all_exist

def test_plugin_json():
    """Test plugin JSON configuration"""
    print("\nTesting plugin JSON configuration...")
    
    with open("openclaw.plugin.json", "r") as f:
        config = json.load(f)
    
    # Check required fields
    required_fields = ["id", "name", "description", "version", "openclaw"]
    for field in required_fields:
        if field in config:
            print(f"  ✓ {field}: {config[field]}")
        else:
            print(f"  ✗ Missing required field: {field}")
            return False
    
    # Check OpenClaw specific fields
    openclaw_config = config.get("openclaw", {})
    required_openclaw = ["minVersion", "extensions", "configSchema", "hooks", "tools"]
    for field in required_openclaw:
        if field in openclaw_config:
            print(f"  ✓ openclaw.{field}")
        else:
            print(f"  ✗ Missing openclaw field: {field}")
            return False
    
    return True

def test_python_module():
    """Test Python module structure"""
    print("\nTesting Python module structure...")
    
    try:
        # Try to import the module
        import importlib.util
        
        spec = importlib.util.spec_from_file_location("privacy_guard", "__init__.py")
        module = importlib.util.module_from_spec(spec)
        
        # Check for required classes and functions
        required_items = [
            "PrivacyGuardPlugin",
            "KnowledgeStore",
            "PrivacyContext",
            "PrivacyReviewer",
            "ChannelInfo",
            "KnowledgeItem",
            "create_plugin",
        ]
        
        # Read file to check for class definitions
        with open("__init__.py", "r") as f:
            content = f.read()
        
        all_found = True
        for item in required_items:
            if item in content:
                print(f"  ✓ {item}")
            else:
                print(f"  ✗ Missing class/function: {item}")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"  ✗ Error importing module: {e}")
        return False

def test_config_schema():
    """Test configuration schema"""
    print("\nTesting configuration schema...")
    
    with open("openclaw.plugin.json", "r") as f:
        config = json.load(f)
    
    schema = config.get("openclaw", {}).get("configSchema", {})
    
    # Check schema structure
    if schema.get("type") == "object":
        print("  ✓ Schema type: object")
    else:
        print("  ✗ Invalid schema type")
        return False
    
    # Check properties
    properties = schema.get("properties", {})
    required_props = ["enabled", "review", "knowledge_base", "defaults"]
    
    all_found = True
    for prop in required_props:
        if prop in properties:
            print(f"  ✓ Property: {prop}")
        else:
            print(f"  ✗ Missing property: {prop}")
            all_found = False
    
    return all_found

def test_hooks_and_tools():
    """Test hooks and tools configuration"""
    print("\nTesting hooks and tools...")
    
    with open("openclaw.plugin.json", "r") as f:
        config = json.load(f)
    
    openclaw_config = config.get("openclaw", {})
    
    # Check hooks
    hooks = openclaw_config.get("hooks", {})
    required_hooks = ["session:init", "message:beforeSend", "memory:search", "file:read"]
    
    all_hooks_found = True
    for hook in required_hooks:
        if hook in hooks:
            print(f"  ✓ Hook: {hook} -> {hooks[hook]}")
        else:
            print(f"  ✗ Missing hook: {hook}")
            all_hooks_found = False
    
    # Check tools
    tools = openclaw_config.get("tools", {})
    required_tools = ["privacy-context", "privacy-review", "knowledge-add"]
    
    all_tools_found = True
    for tool in required_tools:
        if tool in tools:
            tool_config = tools[tool]
            print(f"  ✓ Tool: {tool}")
            print(f"    - name: {tool_config.get('name', 'N/A')}")
            print(f"    - description: {tool_config.get('description', 'N/A')[:50]}...")
        else:
            print(f"  ✗ Missing tool: {tool}")
            all_tools_found = False
    
    return all_hooks_found and all_tools_found

def test_readme():
    """Test README content"""
    print("\nTesting README documentation...")
    
    if not os.path.exists("README.md"):
        print("  ✗ README.md not found")
        return False
    
    with open("README.md", "r") as f:
        content = f.read()
    
    # Check for important sections
    sections = [
        "# Privacy Guard Plugin for OpenClaw",
        "## Features",
        "## Installation",
        "## Configuration",
        "## Usage",
        "## License",
    ]
    
    all_sections_found = True
    for section in sections:
        if section in content:
            print(f"  ✓ Section: {section}")
        else:
            print(f"  ✗ Missing section: {section}")
            all_sections_found = False
    
    return all_sections_found

def test_examples():
    """Test example files"""
    print("\nTesting example files...")
    
    if not os.path.exists("examples/basic_usage.py"):
        print("  ✗ examples/basic_usage.py not found")
        return False
    
    with open("examples/basic_usage.py", "r") as f:
        content = f.read()
    
    # Check for example functions
    example_functions = [
        "example_basic_setup",
        "example_add_knowledge",
        "example_session_management",
        "example_message_review",
    ]
    
    all_functions_found = True
    for func in example_functions:
        if f"def {func}" in content:
            print(f"  ✓ Example function: {func}")
        else:
            print(f"  ✗ Missing example function: {func}")
            all_functions_found = False
    
    return all_functions_found

def test_install_script():
    """Test install script"""
    print("\nTesting install script...")
    
    if not os.path.exists("install.sh"):
        print("  ✗ install.sh not found")
        return False
    
    # Check if script is executable
    if os.access("install.sh", os.X_OK):
        print("  ✓ install.sh is executable")
    else:
        print("  ⚠️  install.sh is not executable (run: chmod +x install.sh)")
    
    with open("install.sh", "r") as f:
        content = f.read()
    
    # Check for important parts
    checks = [
        "#!/bin/bash",
        "OPENCLAW_HOME",
        "openclaw plugin",
        "python3",
        "json.dump",
    ]
    
    all_checks_passed = True
    for check in checks:
        if check in content:
            print(f"  ✓ Contains: {check}")
        else:
            print(f"  ⚠️  Missing: {check}")
            # Not all are required, so don't fail
    
    return True

def main():
    """Run all tests"""
    print("Privacy Guard Plugin Structure Tests")
    print("=" * 60)
    
    tests = [
        ("Plugin Files", test_plugin_files),
        ("Plugin JSON", test_plugin_json),
        ("Python Module", test_python_module),
        ("Config Schema", test_config_schema),
        ("Hooks & Tools", test_hooks_and_tools),
        ("README", test_readme),
        ("Examples", test_examples),
        ("Install Script", test_install_script),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 40)
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"  Result: PASS")
            else:
                print(f"  Result: FAIL")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Plugin structure is valid.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please fix the issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())