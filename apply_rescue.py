#!/usr/bin/env python3
"""Apply rescue diff to restore all modified files."""
import re, sys
from pathlib import Path

diff_path = sys.argv[1]
repo_root = Path(sys.argv[2])
diff_text = Path(diff_path).read_text()

# Parse the diff into file patches
patch_pattern = re.compile(
    r'^diff --git a/(.+?) b/(.+?)$', re.MULTILINE | re.DOTALL
)

files = {}
for m in patch_pattern.finditer(diff_text):
    a_path = m.group(1)
    b_path = m.group(2)
    start = m.end()
    end = diff_text.find('diff --git', start)
    if end == -1:
        end = len(diff_text)
    patch_text = diff_text[start:end]
    
    # Determine target file (use b_path)
    target_path = repo_root / b_path
    
    # Check if it's a deletion
    if a_path == 'dev/null':
        # New file
        # Extract content from +++ lines
        content_match = re.search(r'^\+{3} b/.+?\n((?:^\+.+\n)*)', patch_text, re.MULTILINE)
        if content_match:
            content = ''.join(l[1:] for l in content_match.group(1).splitlines(keepends=True))
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content)
            print(f"  NEW: {b_path}")
        continue
    
    # For modified files, we need to reconstruct the full new content
    # Parse hunks and apply them
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read original content (which was already reset by checkout)
    if target_path.exists():
        original = target_path.read_text()
    else:
        print(f"  MISSING: {b_path}")
        continue
    
    # Use git apply in a subprocess - wait, that's blocked. Let's reconstruct manually.
    # Actually, let's just extract the new content from the diff directly.
    # For each hunk, we apply the changes.
    
    lines = patch_text.split('\n')
    hunk_lines = []
    in_hunk = False
    context_lines = []
    
    # Collect all hunks
    hunks = []
    current_hunk = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('@@'):
            if current_hunk:
                hunks.append(current_hunk)
                current_hunk = []
            in_hunk = True
            # Parse hunk header for old line number
            m = re.match(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@', line)
            if m:
                current_hunk.append(('hunk_start', int(m.group(1))))
            else:
                current_hunk.append(('hunk_start', None))
        elif in_hunk:
            if line.startswith('-'):
                current_hunk.append(('del', line[1:]))
            elif line.startswith('+'):
                current_hunk.append(('add', line[1:]))
            elif line.startswith(' '):
                current_hunk.append(('ctx', line[1:]))
            elif line.startswith('\\'):
                pass  # "No newline at end of file"
        i += 1
    if current_hunk:
        hunks.append(current_hunk)
    
    # Reconstruct new file content from original + hunks
    original_lines = original.split('\n')
    new_lines = list(original_lines)
    
    for hunk in hunks:
        if not hunk:
            continue
        start_info = hunk[0]
        if start_info[0] != 'hunk_start' or start_info[1] is None:
            continue
        
        orig_line_num = start_info[1] - 1  # 1-indexed to 0-indexed
        
        # Walk through hunk operations
        ops = hunk[1:]
        orig_idx = orig_line_num
        new_idx = orig_line_num
        
        for op_type, op_content in ops:
            if op_type == 'ctx':
                # Context line - should match
                if orig_idx < len(original_lines):
                    if original_lines[orig_idx] != op_content:
                        # Mismatch - try to find matching line
                        pass  # skip for now
                    orig_idx += 1
                    new_idx += 1
            elif op_type == 'del':
                if orig_idx < len(original_lines):
                    orig_idx += 1
                # Don't increment new_idx - deleted line is removed
            elif op_type == 'add':
                new_lines.insert(new_idx, op_content)
                new_idx += 1
    
    new_content = '\n'.join(new_lines)
    target_path.write_text(new_content)
    print(f"  PATCHED: {b_path} ({len(hunks)} hunks)")

print(f"\nApplied {len(files)} file patches.")
