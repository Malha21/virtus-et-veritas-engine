from pathlib import Path
from typing import BinaryIO, Protocol


class StorageProvider(Protocol):
    def save_file(self, source: BinaryIO, relative_path: Path) -> str:
        pass
