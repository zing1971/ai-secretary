
import os

filepath = r'deploy_vps.sh'
with open(filepath, 'rb') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # Remove git pull logic entirely
    if b'git pull origin master' in line:
        new_lines.append(b'  echo "Skipping git sync..."\n')
    elif b'git pull' in line: # Any other git pull lines
        new_lines.append(b'  # git pull skipped\n')
    else:
        new_lines.append(line)

# Handle the specific syntax error reported (line 140 else)
# This usually happens if the previous line ended with a semicolon or something that broke the if block
# Or if the replace left a trailing '||'

with open(filepath, 'wb') as f:
    f.writelines(new_lines)
