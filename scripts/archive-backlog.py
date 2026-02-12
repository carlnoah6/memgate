import os
import re
import sys
from datetime import datetime

BACKLOG_PATH = '/home/ubuntu/.openclaw/workspace/data/backlog.md'
ARCHIVE_HEADER = "## 已完成"
TODO_HEADER = "## 待办"

def main():
    if not os.path.exists(BACKLOG_PATH):
        print(f"Error: {BACKLOG_PATH} not found.")
        sys.exit(1)

    with open(BACKLOG_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    archived_lines = []
    
    # State flags
    in_todo_section = False
    header_stack = [] # List of dict: {'level': int, 'line': str, 'printed': bool}
    
    # Logic for moving blocks (task + subtasks)
    moving_block_indent = -1 # -1 means not currently moving a block
    
    iterator = iter(lines)
    
    current_line_idx = 0
    while current_line_idx < len(lines):
        line = lines[current_line_idx]
        current_line_idx += 1
        
        stripped = line.strip()
        
        # 1. Detect Section Boundaries
        if line.startswith(TODO_HEADER):
            in_todo_section = True
            new_lines.append(line)
            # Reset stack when entering TODO
            header_stack = []
            moving_block_indent = -1
            continue
        
        # Exit TODO section if we hit another top-level or level-2 header
        # Assumption: Subsections in TODO are level 3 (###) or deeper, OR 
        # the user structure uses ## for major sections.
        # Based on file content: "## Wiki...", "## 已完成" are boundaries.
        if in_todo_section and line.startswith('## ') and not line.startswith('###'):
            in_todo_section = False
            # Fall through to standard append logic for the rest of the file
        
        if not in_todo_section:
            new_lines.append(line)
            continue
            
        # 2. Inside TODO Section
        
        # Check if Header
        if line.lstrip().startswith('#'):
            # It's a header line
            level = len(line.split()[0]) # Count '#'s. Assumes '# Title' format
            # Pop headers that are essentially closed by this new header
            while header_stack and header_stack[-1]['level'] >= level:
                header_stack.pop()
            
            header_stack.append({'level': level, 'line': line, 'printed': False})
            
            # Reset moving state because a header breaks a task block
            moving_block_indent = -1
            continue
            
        # Check if Completed Task
        # Matches "- [x]" or "* [x]"
        is_completed = re.match(r'^\s*[-*]\s*\[x\]', line, re.IGNORECASE)
        
        if is_completed:
            # Found a completed task
            archived_lines.append(line)
            
            # Set indent to capture children
            indent_match = re.match(r'^(\s*)', line)
            moving_block_indent = len(indent_match.group(1)) if indent_match else 0
            continue
            
        # Check if Child of Moved Task (Continuation)
        if moving_block_indent >= 0:
            # Calculate indent of current line
            indent_match = re.match(r'^(\s*)', line)
            curr_indent = len(indent_match.group(1)) if indent_match else 0
            
            # If line is blank, treat as part of block? Or ignore?
            # Usually keep it to preserve formatting, unless it separates tasks.
            is_blank = (stripped == '')
            
            # Logic:
            # If indented deeper -> child -> move
            # If same indent but starts with bullet -> sibling -> don't move (unless completed, caught above)
            # If same indent but text -> continuation -> move
            # If less indent -> end of block -> stop moving
            
            if is_blank:
                # Keep blank lines with the moved block
                archived_lines.append(line)
                continue
                
            if curr_indent > moving_block_indent:
                # It is a child
                archived_lines.append(line)
                continue
            
            # Same indent?
            if curr_indent == moving_block_indent:
                # Check if it is a new list item
                is_list_item = re.match(r'^\s*[-*]\s+', line)
                if not is_list_item:
                    # Multi-line task text
                    archived_lines.append(line)
                    continue
            
            # If we reached here, the block is finished
            moving_block_indent = -1
            
        # 3. If we are here, we are keeping this line in TODO
        
        # Flush headers that haven't been printed yet
        # This ensures headers only appear if they have content
        for h in header_stack:
            if not h['printed']:
                new_lines.append(h['line'])
                h['printed'] = True
        
        new_lines.append(line)

    # Post-process: Insert archived lines into "## 已完成"
    # Identify where to insert.
    # We look for "## 已完成" in new_lines.
    
    final_lines = []
    inserted = False
    
    # Prepare archive block
    if archived_lines:
        today_str = datetime.now().strftime('%Y-%m-%d')
        archive_block = [f"\n### 归档于 {today_str}\n"] + archived_lines
    else:
        archive_block = []

    for line in new_lines:
        final_lines.append(line)
        if line.startswith(ARCHIVE_HEADER):
            if archive_block:
                final_lines.extend(archive_block)
                inserted = True
    
    # If header didn't exist (should have been copied from original if it existed outside TODO?)
    # Wait, my logic for "OUTSIDE" copies everything.
    # So if "## 已完成" was in the file, it is in `final_lines`.
    # If it wasn't there, we should append it.
    
    has_done_header = any(l.startswith(ARCHIVE_HEADER) for l in lines)
    
    if not inserted and archive_block:
        if not has_done_header:
            final_lines.append(f"\n\n{ARCHIVE_HEADER}\n")
            final_lines.extend(archive_block)
        else:
            # Header exists but we didn't trigger? 
            # (Maybe it was inside TODO section logic by mistake? No, logic handles ## boundaries)
            # Just to be safe, if we didn't insert and we have stuff, append.
            # But normally we insert right after the header line.
            pass

    # Write back
    with open(BACKLOG_PATH, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
    
    print(f"Archived {len(archived_lines)} lines.")

if __name__ == "__main__":
    main()
