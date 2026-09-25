import os
import re

# Comprehensive regex pattern to match most emojis and symbols that cause charmap issues
emoji_pattern = re.compile(
    r'['
    r'\U0001f600-\U0001f64f'  # emoticons
    r'\U0001f300-\U0001f5ff'  # symbols & pictographs
    r'\U0001f680-\U0001f6ff'  # transport & map symbols
    r'\U0001f700-\U0001f77f'  # alchemical symbols
    r'\U0001f780-\U0001f7ff'  # Geometric Shapes Extended
    r'\U0001f800-\U0001f8ff'  # Supplemental Arrows-C
    r'\U0001f900-\U0001f9ff'  # Supplemental Symbols and Pictographs
    r'\U0001fa00-\U0001fa6f'  # Chess Symbols
    r'\U0001fa70-\U0001faff'  # Symbols and Pictographs Extended-A
    r'\u2600-\u26ff'          # misc symbols
    r'\u2700-\u27bf'          # dingbats (including checkmarks)
    r'\u2300-\u23ff'          # misc technical
    r'\u2b50'                 # star
    r']+',
    flags=re.UNICODE
)

def clean_emojis():
    changed_files = []
    for filename in os.listdir('.'):
        if filename.endswith('.py'):
            # Detect encoding
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(filename, 'r', encoding='utf-16') as f:
                    content = f.read()
            
            # Clean emojis
            new_content = emoji_pattern.sub('', content)
            
            if new_content != content:
                # Save as UTF-8
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                changed_files.append(filename)
                
    print(f"Archivos limpiados de raiz: {changed_files}")

if __name__ == '__main__':
    clean_emojis()
