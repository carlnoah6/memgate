#!/usr/bin/env python3
"""
Markdown → 纯文本邮件格式
去掉 markdown 标记，保留可读性

用法:
    python3 scripts/md-to-email-text.py < report.md > email.txt
    python3 scripts/md-to-email-text.py --file report.md
"""

import re, sys, argparse

def md_to_email(md_text):
    lines = md_text.strip().split('\n')
    output = []
    
    for line in lines:
        s = line.rstrip()
        
        # Remove ugly separators
        if re.match(r'^[—─━]{5,}$', s.strip()):
            continue
        
        # H1 → plain title
        if s.strip().startswith('# '):
            output.append(s.strip()[2:])
            output.append('=' * min(len(s.strip()) - 2, 40))
            continue
        
        # H2 → section header
        if s.strip().startswith('## '):
            heading = s.strip()[3:]
            output.append('')
            output.append(f'━━ {heading} ━━')
            continue
        
        # H3 → subsection
        if s.strip().startswith('### '):
            heading = s.strip()[4:]
            output.append('')
            output.append(f'▸ {heading}')
            continue
        
        # Blockquote
        if s.strip().startswith('> '):
            output.append(f'  {s.strip()[2:]}')
            continue
        
        # --- horizontal rule
        if re.match(r'^---+$', s.strip()):
            output.append('─' * 30)
            continue
        
        # Strip **bold** → 「bold」
        s = re.sub(r'\*\*(.+?)\*\*', r'「\1」', s)
        
        # Strip `code` → code
        s = re.sub(r'`(.+?)`', r'\1', s)
        
        output.append(s)
    
    # Clean multiple blank lines
    result = '\n'.join(output)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', '-f', help='Input file')
    args = parser.parse_args()
    
    if args.file:
        with open(args.file) as f:
            md = f.read()
    else:
        md = sys.stdin.read()
    
    print(md_to_email(md))

if __name__ == "__main__":
    main()
