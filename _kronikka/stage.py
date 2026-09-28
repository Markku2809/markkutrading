"""Copy website assets to Pages without the collector, tests or Git files."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
destination=ROOT/'_site'
destination.mkdir(exist_ok=True)
for item in ROOT.iterdir():
    if item.name.startswith(('.', '_')) or item.name in ('README.md','MARKKINA_KRITEERIT.md'):
        continue
    if item.is_dir():
        shutil.copytree(item,destination/item.name,dirs_exist_ok=True)
    else:
        shutil.copy2(item,destination/item.name)
(destination/'.nojekyll').touch()
