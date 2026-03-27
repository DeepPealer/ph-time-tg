import os

def fix_mojibake(text):
    try:
        # The common mojibake in this project is UTF-8 bytes interpreted as cp1252.
        # We reverse this by encoding as cp1252 and decoding as utf-8.
        return text.encode('cp1252').decode('utf-8')
    except Exception:
        # If any part of the file is not valid for this transformation, return original
        return text

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Could not read {filepath}: {e}")
        return

    # Check for presence of common mojibake indicators
    # Ð and Ñ are common in Russian mojibake
    # â is common in emoji/special char mojibake
    if 'Ð' in content or 'Ñ' in content or 'â' in content:
        fixed_content = fix_mojibake(content)
        if fixed_content != content:
            print(f"Fixed mojibake in {filepath}")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
        else:
            print(f"Found indicators in {filepath} but could not fix (already correct or mixed)")
    else:
        # print(f"No mojibake indicators in {filepath}")
        pass

def main():
    # Directories to scan
    scan_dirs = ['bot', 'alembic']
    # Files in root to check
    root_files = ['README.md']
    
    for d in scan_dirs:
        if os.path.isdir(d):
            for root, dirs, files in os.walk(d):
                for file in files:
                    if file.endswith(('.py', '.md', '.sql', '.txt')):
                        process_file(os.path.join(root, file))
    
    for f in root_files:
        if os.path.isfile(f):
            process_file(f)

if __name__ == "__main__":
    main()
