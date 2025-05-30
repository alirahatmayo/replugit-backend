import os

def find_null_lines(filepath):
    null_lines = []
    with open(filepath, 'rb') as f:
        for i, line in enumerate(f, 1):
            if b'\x00' in line:
                null_lines.append(i)
    return null_lines

null_files = {}
for root, dirs, files in os.walk("replugit-backend"):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            lines_with_null = find_null_lines(path)
            if lines_with_null:
                null_files[path] = lines_with_null

if null_files:
    print("Files containing null bytes:")
    for filepath, lines in null_files.items():
        print(f"File: {filepath} has null bytes at lines: {lines}")
else:
    print("No .py files with null bytes found in replugit-backend.")
