"""The public ZIP names and character folders are independent of the installable roots."""
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "pd2-las"))
from status import pack_names  # noqa: E402
from dist_paths import dist_path  # noqa: E402


def test_character_folders_and_renamed_las_packages():
    dist = ROOT / 'dist'
    names = set(pack_names())
    expected_folders = {dist_path(ROOT, f"{name}.zip").parent.name for name in names}
    assert {p.name for p in dist.iterdir() if p.is_dir()} == expected_folders
    for group, name, internal in (
        ('Miranda_L4D2', 'Miranda_L4D2_LAS.zip', 'Miranda_LAS/'),
        ('Miranda_L4D2', 'Miranda_L4D2_Busty_LAS.zip', 'Miranda_Busty_LAS/'),
        ('Miranda_Romance', 'Miranda_Romance_LAS.zip', 'Lawson_LAS/'),
    ):
        archive = dist / group / name
        assert archive.is_file()
        with zipfile.ZipFile(archive) as z:
            assert z.namelist() and all(n.startswith(internal) for n in z.namelist())
        assert archive.with_name(name + '.sha256').is_file()
    assert {path.stem for path in dist.rglob('*.zip')} == names
    assert not (dist / 'Christie' / 'Christie_LAS_Slim.zip').exists()
    assert not (dist / 'Christie' / 'Christie_LAS_Slim.zip.sha256').exists()
    assert not list(dist.glob('*.zip'))


def test_character_archives_live_in_references():
    refs = ROOT / 'references'
    for name in ('Geralt.7z',
                 'PC _ Computer - Mass Effect 2 - Non-Playable Characters - Miranda Lawson (Romance).zip',
                 '1581859199_135363.rar', 'npc_criminals_suit_1.7z'):
        assert (refs / name).is_file()
    assert not (ROOT / 'models').exists()
