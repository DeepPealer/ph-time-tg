import os
import re

# Comprehensive mapping for characters that might have been mangled or have missing bytes
# especially for variation selectors and common emojis.
FIX_MAP = {
    'â¬…ï¸': '⬅️',
    'â¬…': '⬅️',
    'âœ…': '✅',
    'â Œ': '❌',
    'âš™ï¸': '⚙️',
    'âš™': '⚙️',
    'â—€ï¸': '◀️',
    'â—€': '◀️',
    'âž•': '➕',
    'ðŸ ™': '🏙️',
    'ðŸŒ†': '🌆',
    'ðŸŒ ': '🌐',
    'ðŸ“Š': '📊',
    'ðŸ“œ': '📜',
    'â “': '❓',
    'â ©': '⏩',
    'âœ ï¸': '✍️',
    'âœ ': '✍️',
    'ðŸ”„': '🔄',
    'ðŸ§º': '🧹',
    'ðŸ  ': '🏠',
    'ðŸ ¦': '🏦',
    'âš–ï¸': '⚖️',
    'âš–': '⚖️',
    'ðŸ ¢': '🏢',
    'ðŸŽ¯': '🎯',
    'ðŸ“ˆ': '📈',
    'ðŸ’¼': '💼',
    'ðŸ“‚': '📂',
    'ðŸ“‹': '📋',
    'ðŸ“–': '📖',
    'ðŸ‘‘': '👑',
    'ðŸ‘¤': '👤',
    'ðŸ—‘': '🗑️',
    'ðŸ“…': '📅',
    'ðŸ” ': '🔍',
    'â ³': '⏳',
    'âžž': '➞',
    'âž ': '➞',
}

def fix_content(text):
    # 1. Apply specific emoji/symbol mapping first
    for k, v in FIX_MAP.items():
        text = text.replace(k, v)
    
    # 2. Try the general CP1252 -> UTF-8 fix for the rest (mostly Cyrillic)
    # We do this in chunks to avoid failing on the whole file if some parts are invalid
    
    def replacer(match):
        s = match.group(0)
        try:
            return s.encode('cp1252').decode('utf-8')
        except Exception:
            return s

    # Cyrillic mojibake usually starts with Ð or Ñ
    # We look for sequences of characters that look like they could be CP1252 representations of UTF-8 Cyrillic.
    # Cyrillic in UTF-8: D0 XX, D1 XX.
    # D0 is Ð in CP1252. D1 is Ñ in CP1252.
    # The second byte is often in the range 80-BF.
    # In CP1252:
    # 80-9F are special characters (â‚¬, â€š, â€ž, etc.)
    # A0-BF are things like Â, Â¡, Â¢, etc.
    
    # This regex looks for sequences starting with Ð or Ñ followed by characters that correspond to 80-BF.
    # But it's easier to just try to encode/decode the whole string if possible, 
    # or use a regex to find all "Ð" and "Ñ" clusters.
    
    # Let's try to fix anything that starts with Ð or Ñ and has a second char.
    pattern = r'[ÐÑ][^ \n\t\r\(\)\[\]\{\}\'"\<\>\,\.\!\?\:\;\\\/\|]{1,}'
    text = re.sub(pattern, replacer, text)
    
    # 3. Fix standard symbols like â†’ (arrow) or â€¦ (ellipsis)
    text = text.replace('â†’', '→')
    text = text.replace('â€¦', '…')
    text = text.replace('â€”', '—')
    text = text.replace('â€“', '–')
    text = text.replace('Â«', '«')
    text = text.replace('Â»', '»')
    text = text.replace('Â ', ' ') # Non-breaking space
    
    return text

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return

    fixed = fix_content(content)
    
    if fixed != content:
        print(f"Fixed mojibake in {filepath}")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fixed)

def main():
    scan_dirs = ['bot', 'alembic']
    for d in scan_dirs:
        if os.path.isdir(d):
            for root, dirs, files in os.walk(d):
                for file in files:
                    if file.endswith(('.py', '.md', '.sql')):
                        process_file(os.path.join(root, file))
    
    if os.path.isfile('README.md'):
        process_file('README.md')

if __name__ == "__main__":
    main()
