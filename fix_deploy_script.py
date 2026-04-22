
import os

filepath = r'deploy_vps.sh'
with open(filepath, 'rb') as f:
    content = f.read()

# Remove BOM
if content.startswith(b'\xef\xbb\xbf'):
    content = content[3:]

# Convert CRLF to LF
content = content.replace(b'\r\n', b'\n')

# Disable git pull (search and replace)
# We look for the step 2 section
# echo "  檢查 repo，並同步最新代碼..."
# git pull origin master || ...
target = b'git pull origin master || (echo "\xf0\x9f\xbb\x8c git pull \xe5\xa4\xb1\xe6\x95\x97\xef\xbc\x8c\xe8\xab\x8b\xe6\xa2\xae\xe6\x9b\xa5\xe6\xac\x8a\xe9\x99\x90\xe5\x8f\x8a\xe7\xb6\xb2\xe8\xb7\xaf\xe3\x80\x82"; exit 1)'
# Note: I'll just look for a simpler string to be safe
content = content.replace(b'git pull origin master', b'echo "Skipping git pull"')

with open(filepath, 'wb') as f:
    f.write(content)
