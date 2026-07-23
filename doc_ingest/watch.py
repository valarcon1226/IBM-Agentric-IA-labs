"""
watch.py: entrypoint for folder watcher.
Usage:
  python watch.py              (watches ./watch_folder/ by default)
  python watch.py ./my_docs/   (watches custom folder)
"""
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

from watcher.folder_watcher import FolderWatcher

if __name__ == "__main__":
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    watch_path = sys.argv[1] if len(sys.argv) > 1 else None
    watcher = FolderWatcher(watch_path=watch_path)
    watcher.start()
