from pathlib import Path
from typing import BinaryIO


class LocalStorageProvider:
    def __init__(self, root_path: str) -> None:
        self.root_path = Path(root_path)

    def save_file(self, source: BinaryIO, relative_path: Path) -> str:
        safe_relative_path = Path(*relative_path.parts)
        target_path = self.root_path / safe_relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if target_path.exists():
            raise FileExistsError(f"File already exists: {safe_relative_path}")

        with target_path.open("wb") as destination:
            while chunk := source.read(1024 * 1024):
                destination.write(chunk)

        return safe_relative_path.as_posix()
