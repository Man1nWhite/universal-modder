#!/usr/bin/env python3
"""Build `voice_lines_vox/vo_master.xlsx`: the single source of truth for PD2 VO mods.

    python tools/build_vo_master.py            # rebuild the workbook + the per-tab CSVs
    python tools/build_vo_master.py --asr      # also re-transcribe every audio source (pocketsphinx)
    python tools/build_vo_master.py --check    # exit 1 if the tracked outputs are out of date

The workbook joins every voice-line source the repository holds onto one row per id: the
community sheets (imported by ``tools/import_voiceline_sheet.py`` into ``voice_lines_vox/sheets/``),
the shared-bank targets the stream packs wrote (``voice_lines_vox/targets/``), Hila's line
list and its slot table (``voice_lines_vox/hila_regular_vox.csv`` and ``miranda_lawson/``), the
Sydney documents (``references/sheets/Syndey Voicelines.docx``/``.pdf``), the Bodhi sheet
(``references/sheets/Bodhi Voicelines.zip``), the Heister callout table, and a machine transcript
of every audio file the reference packs carry (``voice_lines_vox/vo_transcripts.csv``).

Every machine transcript is an unverified draft: whisper's model hosts are unreachable from this
environment, so ``--asr`` runs **pocketsphinx** (bundled en-us model) and marks the engine in the
table. Do not treat its wording as final; treat it as a reading aid, flagged for review.

``--asr`` needs the reference archives extracted: it does that itself into
``build/vo-master/`` (a few hundred MB of scratch, gitignored), then decodes each ``.stream``
with ``tools/pd2-las/wwise_ima.py`` (the 27 Wwise Vorbis ids cannot be decoded here and are
recorded as such), and each ``.ogg``/``.mp3`` with the ffmpeg that ``imageio-ffmpeg`` ships.

The default build reads only tracked files plus ``vo_transcripts.csv``; it needs ``openpyxl``,
``pypdf`` and ``python-docx`` (all in the pinned ``.venv``).
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
import sys as _sys
_sys.path.insert(0, str(HERE / "pd2-las"))
import wwise_ima  # noqa: E402  (the fork's .stream codec: read/decode only)

V = ROOT / "voice_lines_vox"
SHEETS = V / "sheets"
TARGETS = V / "targets"
ML = V / "miranda_lawson"
GERALT = V / "geralt"
ARIVUS = V / "arivus"
DIST = ROOT / "dist"
OUT_XLSX = V / "vo_master.xlsx"
OUT_DIR = V / "vo_master"
TRANSCRIPTS = V / "vo_transcripts.csv"

def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, '') for k in fields})

def word_overlap(a, b):
    def toks(s):
        return re.findall(r"[a-z0-9']+", (s or '').lower())
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta), set(tb)
    return len(sa & sb) / max(1, len(sa | sb))

# ----------------------------------------------------------------- ASR (--asr)

VOICE_ARCHIVES = [
    ("references/voice/Tokoyami Hila.7z", "tokoyami", "7z"),
    ("references/voice/Marine VO for Rust.7z.001", "marine", "7z-join"),
    ("references/voice/LAWSON VOICE (PAYDAY 2).7z", "mira_takes", "7z"),
    ("references/voice/GERALT VOICE (PAYDAY 2).zip", "geralt", "zip"),
    ("references/voice/ARIVUS VOICE (PAYDAY 2).zip", "arivus", "zip"),
]

def _extract(archive, dst, kind):
    import py7zr
    dst = Path(dst)
    if list(dst.iterdir()) if dst.exists() else False:
        return  # reuse a populated scratch dir
    dst.mkdir(parents=True, exist_ok=True)
    if kind == "zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(dst)
        return
    src = Path(archive)
    if kind == "7z-join":
        volumes = sorted(src.parent.glob(src.name.rsplit('.', 1)[0] + '.*'))
        joined = ROOT / "build" / "vo-master" / "joined.7z"
        with open(joined, 'wb') as out:
            for v in volumes:
                out.write(v.read_bytes())
        src = joined
    with py7zr.SevenZipFile(src) as z:
        z.extractall(dst)

def _decode_stream(path):
    blob = Path(path).read_bytes()
    try:
        rate, audio = wwise_ima.decode_file(blob)
    except wwise_ima.FormatError as error:
        return None, None, None, str(error)
    mono = audio.astype('float32').mean(axis=1) if audio.ndim > 1 else audio[:, 0].astype('float32')
    n = int(len(mono) * 16000 / rate)
    xi = _np_interp(mono, n)
    return (16_000, (xi * 32767.0).clip(-32768, 32767).astype('<i2').tobytes(),
            f"{rate} Hz {audio.shape[1]} ch", len(mono) / rate)

def _np_interp(x, n):
    import numpy as np
    return np.interp(np.linspace(0, max(len(x) - 1, 0), n), np.arange(len(x)), x / 32768.0)

def _decode_file_ffmpeg(path, tmp):
    from imageio_ffmpeg import get_ffmpeg_exe
    import subprocess
    out = Path(tmp)
    subprocess.run([get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-i', str(path),
                    '-ar', '16000', '-ac', '1', '-f', 's16le', str(out)],
                   check=True)
    raw = out.read_bytes()
    out.unlink()
    seconds = len(raw) / 2 / 16000
    return 16_000, raw, "16 kHz (ffmpeg-decoded)", seconds

def asr_all(workdir=ROOT / "build" / "vo-master"):
    from pocketsphinx import Decoder
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    model = Path(pocketsphinx_model_dir()) / 'en-us'
    hmm, lm, dic = model / 'en-us', model / 'en-us.lm.bin', model / 'cmudict-en-us.dict'
    dec = Decoder(hmm=str(hmm), lm=str(lm), dict=str(dic))

    def hyp_for(pcm):
        dec.start_utt(); dec.process_raw(pcm, no_search=False, full_utt=True); dec.end_utt()
        h = dec.hyp()
        return h.hypstr if h else ''

    rows = []
    def add(archive, bank, file, id_, fmt, rate, channels, seconds, transcript):
        rows.append(dict(source_archive=archive, bank=bank, file=file, id=id_, fmt=fmt,
                         rate_hz=rate, channels=channels,
                         seconds=f"{seconds:.3f}" if seconds else '', engine=ENGINE,
                         transcript=transcript))
    for archive, name, kind in VOICE_ARCHIVES:
        dst = workdir / name
        _extract(ROOT / archive, dst, kind)
        streams = sorted(dst.rglob('*.stream'))
        for s in streams:
            r = _decode_stream(s)
            if r is None or r[1] is None:
                rows.append(dict(source_archive=Path(archive).name, bank=s.parent.name,
                                 file=s.name, id=s.stem, fmt='vorbis', rate_hz='', channels='',
                                 seconds='', engine='none', transcript='',
                                 note='Wwise Vorbis (fmt tag 0xFFFF): not decodable with the ADPCM codec; the game plays it or needs Hoppip’s Soundbank Editor'))
                continue
            rate, pcm, info, seconds = r
            ch = info.split(' Hz ')[1].split(' ch')[0]
            add(Path(archive).name, s.parent.name, s.name, s.stem, 'adpcm', info.split(' Hz')[0], ch, seconds, hyp_for(pcm))
        for ext, fmt in [('*.mp3', 'mp3'), ('*.ogg', 'ogg')]:
            for s in sorted(dst.rglob(ext)):
                rate, pcm, info, seconds = _decode_file_ffmpeg(s, workdir / 'asr_tmp.s16')
                rel = s.parent.name if s.parent != dst else '.'
                add(Path(archive).name, rel, s.name,
                    s.stem if s.stem.isdigit() else '', fmt, '16000', '1', seconds, hyp_for(pcm))
    write_csv(TRANSCRIPTS, rows, TRANSCRIPT_FIELDS)
    return rows

def pocketsphinx_model_dir():
    import pocketsphinx
    return pocketsphinx.get_model_path()

ENGINE = 'pocketsphinx 5.x en-us (whisper models unreachable: model hosts blocked); unverified draft, needs review'
TRANSCRIPT_FIELDS = ['source_archive', 'bank', 'file', 'id', 'fmt', 'rate_hz', 'channels',
                     'seconds', 'engine', 'transcript', 'note']

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--asr', action='store_true',
                   help='re-transcribe every audio source into voice_lines_vox/vo_transcripts.csv (pocketsphinx)')
    p.add_argument('--check', action='store_true',
                   help='rebuild the per-tab CSVs into a temp dir and fail if the tracked ones differ')
    args = p.parse_args(argv)
    if args.asr:
        rows = asr_all()
        done = sum(1 for r in rows if r['transcript'])
        print(f"asr: {len(rows)} files, {done} transcribed, {sum(1 for r in rows if r['fmt'] == 'vorbis')} vorbis (not decodable)", file=sys.stderr)
    if args.check:
        return check()
    build_all()
    return 0

# ------------------------------------------------------------------- build

def load_transcripts():
    rows = read_csv(TRANSCRIPTS) if TRANSCRIPTS.exists() else []
    by_id = {}
    for r in rows:
        if r.get('id'):
            by_id[(r['source_archive'], r['bank'], r['id'])] = r
    return rows, by_id

def load_targets():
    rust = {r['id']: r for r in read_csv(TARGETS / 'rust_shared_regular_vox.csv')}
    hoxton = {r['id']: r for r in read_csv(TARGETS / 'old_hoxton_shared_regular_vox.csv')}
    rust_ded = [r for r in read_csv(TARGETS / 'rust_dedicated_char_rust.csv')]
    return rust, hoxton, rust_ded

def load_hila():
    hila = {r['PD2 ID']: (r['Speech'], r['Category']) for r in read_csv(V / 'hila_regular_vox.csv')}
    cuts = {r['hila_id']: r for r in read_csv(ML / 'hila_intent_cuts.csv')}
    sem = {r['slot']: r for r in read_csv(ML / 'hila_semantic_fit.csv')}
    removed = {r['slot']: r for r in read_csv(ML / 'removed_slots.csv')}
    vorbis = {r['hila_id'] for r in read_csv(ML / 'hila_vorbis_ids.csv')}
    return hila, cuts, sem, removed, vorbis

def word_overlap_best(a, b):
    return word_overlap(a, b)

def match_label(transcript, text):
    if not transcript:
        return ''
    if not text:
        return 'no-text'
    o = word_overlap(transcript, text)
    if o >= 0.6:
        return 'high'
    if o >= 0.35:
        return 'partial'
    return 'low'

REGULAR_VOX_FIELDS = ['bank_space', 'id', 'who', 'what', 'notes', 'needs_review',
                      'hila_line', 'hila_speech', 'hila_category', 'intent', 'slot',
                      'cut_line', 'written_miranda', 'written_geralt', 'written_arivus',
                      'vorbis', 'removed_slot', 'removed_reason',
                      'tokoyami_transcript', 'transcript_match']

def tab_regular_vox(data):
    comm = read_csv(SHEETS / 'regular_vox.csv')
    hila, cuts, sem, removed, vorbis = data['hila']
    rust, hoxton, _ = data['targets']
    tok = data['transcripts_by_id']
    rows, seen = [], set()
    for r in comm:
        id_ = r['id']
        seen.add(id_)
        rows.append(_regular_row(r, id_, 'community-export', data))
    for id_ in sorted((set(cuts) | set(hila)) - seen):
        speech, category = hila.get(id_, ('', ''))
        cut = cuts.get(id_, {})
        t = tok.get(('Tokoyami Hila.7z', 'regular_vox', id_))
        transcript = t['transcript'] if t else ''
        slot = cut.get('slot', '')
        rows.append({
            'bank_space': 'hila-dlc-bank', 'id': id_, 'who': '', 'what': '', 'notes': '',
            'needs_review': '', 'hila_line': 'yes',
            'hila_speech': speech, 'hila_category': category,
            'intent': cut.get('intent', ''), 'slot': slot, 'cut_line': cut.get('cut_line', ''),
            'written_miranda': _written_miranda(id_, slot, removed, vorbis),
            'written_geralt': _target_written(rust, id_),
            'written_arivus': _target_written(hoxton, id_),
            'vorbis': 'yes' if id_ in vorbis else '',
            'removed_slot': 'yes' if slot in removed else '',
            'removed_reason': removed[slot]['reason'] if slot in removed else '',
            'tokoyami_transcript': transcript,
            'transcript_match': match_label(transcript, speech),
        })
    rows.sort(key=lambda r: (int(r['id']) if r['id'].isdigit() else 0, r['bank_space']))
    return REGULAR_VOX_FIELDS, rows

def _regular_row(r, id_, space, data):
    hila, cuts, sem, removed, vorbis = data['hila']
    speech, category = hila.get(id_, ('', ''))
    cut = cuts.get(id_, {})
    t = data['transcripts_by_id'].get(('Tokoyami Hila.7z', 'regular_vox', id_))
    transcript = t['transcript'] if t else ''
    slot = cut.get('slot', '')
    rust, hoxton, _ = data['targets']
    return {
        'bank_space': space, 'id': id_, 'who': r['who'], 'what': r['what'],
        'notes': r['notes'], 'needs_review': r['needs_review'],
        'hila_line': 'yes' if id_ in hila else '',
        'hila_speech': speech, 'hila_category': category,
        'intent': cut.get('intent', ''), 'slot': slot, 'cut_line': cut.get('cut_line', ''),
        'written_miranda': _written_miranda(id_, slot, removed, vorbis),
        'written_geralt': _target_written(rust, id_),
        'written_arivus': _target_written(hoxton, id_),
        'vorbis': 'yes' if id_ in vorbis else '',
        'removed_slot': 'yes' if slot in removed else '',
        'removed_reason': removed[slot]['reason'] if slot in removed else '',
        'tokoyami_transcript': transcript,
        'transcript_match': match_label(transcript, speech or r['what']),
    }

def _written_miranda(id_, slot, removed, vorbis):
    if id_ in vorbis:
        return 'no'
    if slot in removed:
        return 'no'
    return 'yes' if slot else ''

def _target_written(table, id_):
    row = table.get(id_)
    if row is None:
        return ''
    return row['written']

ROBBERS_FIELDS = ['id', 'who', 'what', 'notes', 'needs_review',
                  'in_tokoyami', 'in_marine', 'transcript_tokoyami', 'transcript_marine',
                  'tokoyami_match', 'marine_match',
                  'sydney_docx', 'sydney_what', 'sydney_category', 'sydney_match']

def tab_robbers(data):
    comm = {r['id']: r for r in read_csv(SHEETS / 'robbers_mission_gen.csv')}
    _, rob_docx, _ = sydney_documents()
    rows, ids = [], set(comm)
    tok_rows = {}
    for (archive, bank, id_), t in data['transcripts_by_id'].items():
        if archive == 'Tokoyami Hila.7z' and bank == 'robbers_mission_gen':
            tok_rows.setdefault(id_, t)
    mar_rows = {}
    for (archive, bank, id_), t in data['transcripts_by_id'].items():
        if archive == 'Marine VO for Rust.7z.001' and bank == 'robbers_mission_gen':
            mar_rows.setdefault(id_, t)
    ids |= set(tok_rows) | set(mar_rows) | set(rob_docx)
    for id_ in sorted(ids, key=lambda x: int(x) if x.isdigit() else 0):
        r = comm.get(id_)
        t_tok, t_mar = tok_rows.get(id_), mar_rows.get(id_)
        comm_what = (r or {}).get('what', '')
        comm_who = (r or {}).get('who', '')
        notes = (r or {}).get('notes', '')
        syn = rob_docx.get(id_)
        syn_what = syn[0] if syn else ''
        if not r and syn:
            who, what = 'Sydney', syn_what
            notes = 'only in the Sydney .docx (mission-chatter table); no community row'
            needs_review, sydney_match = 'yes (document-sourced line, not in-game-verified)', ''
        elif syn and not comm_what.strip():
            who, what = comm_who.strip() or 'Sydney', syn_what
            notes = (notes + '; ' if notes else '') + 'line text backfilled from the Sydney .docx (mission-chatter table)'
            needs_review, sydney_match = 'yes (line text from the Sydney .docx; document-sourced)', 'no-text'
        elif syn:
            who, what = comm_who or 'Sydney', comm_what
            needs_review, sydney_match = (r or {}).get('needs_review', ''), match_label(syn_what, comm_what)
        else:
            who, what = comm_who, comm_what
            needs_review, sydney_match = ((r or {}).get('needs_review', '') if r else 'yes (audio-only row: no community line)'), ''
        rows.append({
            'id': id_, 'who': who, 'what': what,
            'notes': notes, 'needs_review': needs_review,
            'in_tokoyami': 'yes' if t_tok else '', 'in_marine': 'yes' if t_mar else '',
            'transcript_tokoyami': t_tok['transcript'] if t_tok else '',
            'transcript_marine': t_mar['transcript'] if t_mar else '',
            'tokoyami_match': match_label(t_tok['transcript'] if t_tok else '', what),
            'marine_match': match_label(t_mar['transcript'] if t_mar else '', what),
            'sydney_docx': 'yes' if syn else '',
            'sydney_what': syn_what,
            'sydney_category': syn[1] if syn else '',
            'sydney_match': sydney_match,
        })
    return ROBBERS_FIELDS, rows

SYDNEY_FIELDS = ['id', 'what', 'category', 'in_csv', 'in_docx', 'in_pdf', 'notes']

_SYDNEY_CACHE = None

def sydney_documents():
    global _SYDNEY_CACHE
    if _SYDNEY_CACHE is not None:
        return _SYDNEY_CACHE
    from docx import Document
    from pypdf import PdfReader
    syd_docx, rob_docx = {}, {}
    d = Document(ROOT / 'references/sheets/Syndey Voicelines.docx')
    for i, t in enumerate(d.tables):
        for row in t.rows:
            cells = [c.text.strip() for c in row.cells]
            if cells and cells[0].isdigit():
                (syd_docx if i == 0 else rob_docx)[cells[0]] = (cells[1] if len(cells) > 1 else '',
                                                                 cells[2] if len(cells) > 2 else '')
    r = PdfReader(ROOT / 'references/sheets/Syndey Voicelines.pdf')
    txt = '\n'.join((p.extract_text() or '') for p in r.pages)
    pdf_ids = set(re.findall(r'\d{5,10}', txt))
    _SYDNEY_CACHE = (syd_docx, rob_docx, pdf_ids)
    return _SYDNEY_CACHE

def tab_sydney(data):
    comm = {r['id']: r for r in read_csv(SHEETS / 'char_sydney.csv')}
    docx_rows, _, pdf_ids = sydney_documents()
    ids = set(comm) | set(docx_rows)  # the pdf is the same document's print; it adds no ids to this bank
    rows = []
    for id_ in sorted(ids, key=lambda x: int(x)):
        csv_r, doc_r = comm.get(id_), docx_rows.get(id_)
        what = (doc_r[0] if doc_r else '') or (csv_r['what'] if csv_r else '')
        category = (doc_r[1] if doc_r else '') or (csv_r['notes'] if csv_r else '')
        notes = []
        if csv_r:
            if csv_r['notes']:
                notes.append(csv_r['notes'])
            if csv_r['needs_review'] == 'yes':
                notes.append('needs_review')
        if id_ not in docx_rows:
            notes.append('not in the .docx')
        if id_ not in pdf_ids:
            notes.append('not in the .pdf')
        if id_ in pdf_ids and id_ not in docx_rows:
            notes.append('pdf-only id; line text unverified')
        rows.append({'id': id_, 'what': what, 'category': category,
                     'in_csv': 'yes' if csv_r else '', 'in_docx': 'yes' if doc_r else '',
                     'in_pdf': 'yes' if id_ in pdf_ids else '', 'notes': '; '.join(notes)})
    return SYDNEY_FIELDS, rows

CHAR_RUST_FIELDS = ['row', 'id', 'bank', 'fmt', 'rate_hz', 'channels', 'seconds',
                    'transcript', 'slot', 'engine', 'note']

def tab_char_rust(data):
    measured = read_csv(TARGETS / 'rust_dedicated_char_rust.csv')
    tok = data['transcripts_by_id']
    rows = []
    for i, r in enumerate(measured, 1):
        id_ = r['id']
        t = tok.get(('Marine VO for Rust.7z.001', 'char_rust', id_))
        rows.append({
            'row': i, 'id': id_, 'bank': 'char_rust',
            'fmt': (t or {}).get('fmt', ''), 'rate_hz': (t or {}).get('rate_hz', ''),
            'channels': (t or {}).get('channels', ''), 'seconds': (t or {}).get('seconds', ''),
            'transcript': (t or {}).get('transcript', ''),
            'slot': '',
            'engine': (t or {}).get('engine', ''),
            'note': (t or {}).get('note', '') or 'measured in Marine VO for Rust.7z.001; the line each id answers is unknown — a game extraction must name it (D76)',
        })
    return CHAR_RUST_FIELDS, rows

SLOTS_FIELDS = ['slot', 'intent', 'uses', 'hila_category', 'cut_line',
                'semantic_score', 'semantic_status', 'semantic_rationale',
                'written_miranda_pack', 'removed_vanilla', 'removed_reason',
                'miranda_take', 'geralt_take', 'arivus_take']

def tab_slots(data):
    hila, cuts, sem, removed, vorbis = data['hila']
    rust, hoxton, _ = data['targets']
    m_picks = {r['slot']: r for r in read_csv(ML / 'slot_picks.csv')}
    g_picks = {r['slot']: r for r in read_csv(GERALT / 'slot_picks.csv')}
    a_picks = {r['slot']: r for r in read_csv(ARIVUS / 'slot_picks.csv')}
    ids_by_slot = {}
    for id_, cut in cuts.items():
        ids_by_slot.setdefault(cut['slot'], []).append(id_)
    slots = sorted(set(cuts_s for cuts_s in (r.get('slot') for r in cuts.values()) if cuts_s))
    rows = []
    for slot in slots:
        s = sem.get(slot, {})
        ids = ids_by_slot.get(slot, [])
        written = sum(1 for i in ids
                      if _written_miranda(i, slot, removed, vorbis) == 'yes')
        rem = removed.get(slot)
        rows.append({
            'slot': slot,
            'intent': _first(cut['intent'] for cut in cuts.values() if cut['slot'] == slot) or '',
            'uses': s.get('uses', ''),
            'hila_category': _first(cut['hila_category'] for cut in cuts.values() if cut['slot'] == slot) or '',
            'cut_line': _first(cut['cut_line'] for cut in cuts.values() if cut['slot'] == slot) or s.get('cut_line', ''),
            'semantic_score': s.get('score', ''),
            'semantic_status': s.get('status', ''),
            'semantic_rationale': s.get('rationale', ''),
            'written_miranda_pack': f"{written}/{len(ids)}",
            'removed_vanilla': 'yes' if rem else '',
            'removed_reason': rem['reason'] if rem else '',
            'miranda_take': (m_picks.get(slot) or {}).get('source_ogg', ''),
            'geralt_take': (g_picks.get(slot) or {}).get('source_ogg', ''),
            'arivus_take': (a_picks.get(slot) or {}).get('source_ogg', ''),
        })
    return SLOTS_FIELDS, rows

def _first(it):
    for x in it:
        if x:
            return x
    return ''

PACKS_FIELDS = ['pack', 'zip', 'route', 'target_heister', 'bank', 'model_switch',
                'source_archive', 'stream_files', 'slots_covered', 'ids_written',
                'vanilla_left', 'alternative', 'heard_in_game', 'rebuild']

def tab_packs(data):
    rust, hoxton, _ = data['targets']
    hila, cuts, sem, removed, vorbis = data['hila']
    written_m = sum(1 for id_, cut in cuts.items()
                    if _written_miranda(id_, cut['slot'], removed, vorbis) == 'yes')
    written_g = sum(1 for r in rust.values() if r['written'] == 'yes')
    written_a = sum(1 for r in hoxton.values() if r['written'] == 'yes')
    g_slots = len({r['slot'] for r in rust.values() if r['written'] == 'yes'})
    a_slots = len({r['slot'] for r in hoxton.values() if r['written'] == 'yes'})
    m_slots = len({cut['slot'] for id_, cut in cuts.items()
                   if _written_miranda(id_, cut['slot'], removed, vorbis) == 'yes'})
    rows = [
        dict(pack='Miranda_Lawson_VO_over_Hila_Stream', zip='dist/Miranda/Miranda_Lawson_VO_over_Hila_Stream.zip',
             route='id-keyed .stream (Wwise IMA ADPCM)', target_heister='Hila (ecp_female, switch rb21)',
             bank='regular_vox', model_switch='rb21',
             source_archive='references/voice/Голос Лоусон.7z (clips), references/voice/LAWSON VOICE (PAYDAY 2).7z (takes)',
             stream_files=written_m, slots_covered=m_slots, ids_written=written_m,
             vanilla_left=885 - written_m, alternative='compatible with Geralt_VO_over_Rust (different route/prefix)',
             heard_in_game='yes — 2026-11-25, user reported it works',
             rebuild='make -sC tools/pd2-las voices_stream'),
        dict(pack='Geralt_VO_over_Rust', zip='dist/Geralt/Geralt_VO_over_Rust.zip',
             route='BeardLib <Sounds> + <redirect prefix="rb16"/> + Lua XAudio lifecycle fix (D97)',
             target_heister='Rust (npc_criminal_wild_1, switch rb16)',
             bank='voicelines/*.ogg (event redirects on prefix rb16)', model_switch='rb16',
             source_archive='references/voice/GERALT VOICE (PAYDAY 2).zip',
             stream_files=0, slots_covered='29 slots + 2 callouts (36 OGG takes)', ids_written='45 bark events',
             vanilla_left='all uncovered Rust events stay vanilla',
             alternative='replaces retired Geralt_VO_over_Rust_Stream; coexists with Miranda_Lawson_VO_over_Hila_Stream',
             heard_in_game='pending in-game check (verified in LuaJIT against BeardLib 5.2.0)',
             rebuild='make -sC tools/pd2-las voices_geralt'),
        dict(pack='Geralt_VO_over_Rust_Stream', zip='Geralt_VO_over_Rust_Stream.zip (deleted from dist/ 2026-11-28, D89)',
             route='id-keyed .stream (Wwise IMA ADPCM)', target_heister='Rust (npc_criminal_wild_1, switch rb16)',
             bank='regular_vox', model_switch='rb16',
             source_archive='references/voice/GERALT VOICE (PAYDAY 2).zip',
             stream_files=written_g, slots_covered=g_slots, ids_written=written_g,
             vanilla_left=885 - written_g, alternative='retired 2026-11-28; deleted from dist/ (D89)',
             heard_in_game='no — never heard in game',
             rebuild='— (retired 2026-11-28; the builder remains for the char_rust route)'),
        dict(pack='Arivus_VO_over_Hoxton_Stream', zip='Arivus_VO_over_Hoxton_Stream.zip (deleted from dist/ 2026-11-28, D89)',
             route='id-keyed .stream (Wwise IMA ADPCM)', target_heister='Old Hoxton (npc_criminals_suit_1, switch rb5)',
             bank='regular_vox', model_switch='rb5',
             source_archive='references/voice/ARIVUS VOICE (PAYDAY 2).zip (+ one borrowed file from the GERALT archive)',
             stream_files=written_a, slots_covered=a_slots, ids_written=written_a,
             vanilla_left=885 - written_a, alternative='retired 2026-11-28; deleted from dist/ (D89)',
             heard_in_game='no — never heard in game',
             rebuild='— (retired 2026-11-28; the builder remains for the char_rust route)'),
    ]
    return PACKS_FIELDS, rows

CALLOUTS_FIELDS = ['category', 'event', 'meaning', 'raw_cell']
_EVENT = re.compile(r'^\s*([A-Za-z][A-Za-z0-9_.\-]*?)\s*[-–—]\s*(.+?)\s*$')

def tab_callouts():
    rows = []
    raw = list(csv.reader(open(ROOT / 'references/sheets/Payday 2 Voiceline IDs - Heister Voice IDs.csv',
                               encoding='utf-8', errors='replace')))
    headers = [c.strip() for c in raw[2]] if len(raw) > 2 else []
    for r_i, row in enumerate(raw):
        if r_i < 4:
            continue  # titles + header row + scope note row
        for c_i, cell in enumerate(row):
            cell = cell.strip()
            if not cell:
                continue
            category = headers[c_i] if c_i < len(headers) else ''
            m = _EVENT.match(cell)
            if m:
                rows.append({'category': category, 'event': m.group(1),
                             'meaning': m.group(2).strip('"'), 'raw_cell': cell})
            else:
                rows.append({'category': category, 'event': '', 'meaning': cell.strip('"'),
                             'raw_cell': cell})
    return CALLOUTS_FIELDS, rows

BODHI_FIELDS = ['sheet', 'id', 'what', 'note']

def tab_bodhi():
    import zipfile
    import openpyxl
    rows = []
    with zipfile.ZipFile(ROOT / 'references/sheets/Bodhi Voicelines.zip') as z:
        z.extract('Bodhi Voicelines.xlsx', ROOT / 'build/vo-master/bodhi-extract')
    wb = openpyxl.load_workbook(ROOT / 'build/vo-master/bodhi-extract/Bodhi Voicelines.xlsx',
                                data_only=True)
    for ws in wb.worksheets:
        if ws.title == 'Blank Sheet':
            continue
        for row in ws.iter_rows(values_only=True):
            if row and isinstance(row[0], int):
                rows.append({'sheet': ws.title, 'id': row[0],
                             'what': row[1] if len(row) > 1 and row[1] is not None else '',
                             'note': row[2] if len(row) > 2 and row[2] is not None else ''})
    rows.sort(key=lambda r: (str(r['sheet']), int(r['id'])))
    return BODHI_FIELDS, rows

MIRANDA_FIELDS = ['filename', 'duration_s', 'whisper_transcript', 'corrected_transcript', 'changed']

def tab_miranda_transcripts():
    return MIRANDA_FIELDS, read_csv(ML / 'miranda_transcripts_corrected.csv')

KV_FIELDS = ['key', 'value']

def tab_readme(data, stats):
    B = [
        ('title', 'PAYDAY 2 VO mods — the single source of truth'),
        ('built', "2026-11-28 by tools/build_vo_master.py (make -sC tools/pd2-las voices_master). Do not hand-edit this workbook or the CSVs beside it; change the tool or the sources and rebuild."),
        ('what_this_is', 'One row per voice-line id from every source the repository holds — the community sheets (imported in full), Hila\'s 885-line bank, the shipped .stream pack, the Sydney and Bodhi documents, the event-name callout table — joined on the id, with machine transcripts of every audio file the reference packs carry. It replaces docs/pd2-voice-mod-install.md, docs/pd2-voice-stream-tables.md and docs/tokoyami-hila-voice-mod-analysis.md, which were deleted on 2026-11-28. The decisions live on in docs/pd2-las/DECISIONS.md.'),
        ('', ''),
        ('RULES', ''),
        ('R1', 'THE ID IS THE HANDLE. Wwise strips every name; a line is a file soundbanks/streamed/<bank>/<id>.stream. Line text is evidence, never an override.'),
        ('R2', 'INSTALL ONLY ONE shared-bank .stream pack — today that is Miranda_Lawson_VO_over_Hila_Stream (see packs tab); the Geralt/Arivus shared-bank stream packs were retired and deleted 2026-11-28 (D89). Geralt_VO_over_Rust uses BeardLib <Sounds> event redirects scoped to prefix="rb16" with a companion Lua lifecycle fix (D97), so it coexists cleanly alongside Miranda_Lawson_VO_over_Hila_Stream.'),
        ('R3', 'Uncovered slots stay VANILLA rather than a weak take. 27 ids are Wwise Vorbis (no ADPCM pack can write them) and 17 slots (162 ids) scored below the semantic-fit floor — those play as vanilla Hila.'),
        ('R4', 'Community-sheet wording is community-sourced: wrong, stale and duplicated rows exist; needs_review marks them. Sydney and Bodhi rows are document-sourced, pdf-only ids are unverified.'),
        ('R5', 'MACHINE TRANSCRIPTS ARE UNVERIFIED DRAFTS. Whisper\'s model hosts are unreachable from this environment, so every transcript column here is pocketsphinx output (see transcripts tab, engine column) — a reading aid to flag for review, never final wording. Miranda\'s 866 source oggs are the exception: those carry whisper transcripts + hand corrections (miranda_lawson/miranda_transcripts_corrected.csv, imported as the miranda_transcripts tab).'),
        ('R6', 'The community REGULAR_VOX export is NOT the bank the packs write: 0 of the 885 pack-bank ids appear in it, while the community ROBBERS_MISSION_GEN export DOES match the packs (196/202 tokoyami, 213/220 marine). Treat every id→line pair for the pack bank as UNVERIFIED by that sheet; only Hila\'s own list (hila_regular_vox.csv) and the slot table name those ids\' text. See finding F1.'),
        ('R7', 'char_rust: the 1,046 ids are measured, the lines are not. The re-key (D76) stays blocked until a game extraction names them. Do not fill slots for them.'),
        ('R8', 'slot → bank → id tables the packs are built from live in voice_lines_vox/targets/ (pinned to the zips by tests/test_stream_tables.py); this workbook folds them into the regular_vox and slots tabs.'),
        ('', ''),
        ('FINDINGS', ''),
        ('F1', 'ID-SPACE MISMATCH (measured 2026-11-27): 0 of 885 pack-bank ids are in the community regular_vox export (20,404 rows, 20,403 ids). The robbers_mission_gen export matches the packs (196/202 and 213/220) — so the ids are real, the regular_vox tab simply covers a different bank than the one the packs write. The 20,404-row table is kept here because it is the only id→line evidence for ITS bank; it cannot verify the pack bank.'),
        ('F2', 'The reference pack writes 887 regular_vox files: the 885 ids in Hila\'s list plus 124616049 and 134711817, which appear in NO tracked table (noted, unused).'),
        ('F3', 'Marine VO for Rust carries 1 id that also sits in the community robbers_mission_gen export; char_rust and regular_vox (community) share 0. Rust\'s own bank question (D71) stays open; the pack writes the shared bank.'),
        ('F4', 'Miranda pack heard in game and works (2026-11-25, user report). Geralt and Arivus packs have NOT been heard. Evidence vs assumption: the spreadsheet marks every row measured vs derived; nothing here is in-game-verified beyond the Hila pack.'),
        ('F5', 'The Marine reference pack also carries 55 Wwise Vorbis files in char_rust (fmt tag 0xFFFF), on top of Tokoyami’s 27 — none of them decodable with the ADPCM codec. Any dedicated-bank pack must filter Vorbis out the same way (measurement, 2026-11-28).'),
        ('', ''),
        ('TABS', ''),
        ('regular_vox', 'shared-bank lines, both id spaces (community export; hila-dlc-bank), one row per id; pack coverage, Vorbis/removed markers, machine transcript where audio exists'),
        ('robbers_mission_gen', 'the objective-callout bank: community text for 1,722 ids, plus Sydney’s .docx mission-chatter table (224 rows; 145 backfill audio-only community rows, 1 new id), plus machine transcripts from the two reference packs (202 + 220 files)'),
        ('char_sydney', 'Sydney, complete as a bank in three sources: community CSV (1,037), the .docx’s char_sydney table (1,077) and its .pdf print; union, one row each with in_csv/in_docx/in_pdf flags. The .docx’s second table is Sydney-voiced mission chatter — her robbers_mission_gen lines — and lives in that tab, not here'),
        ('char_rust', 'the measured char_rust bank (1,046 ids from Marine VO for Rust), with machine transcripts — slots unknown, see R7'),
        ('slots', 'Hila intent slots: uses, semantic-fit score/status, vanilla-removed reason, per-pack take file; the pack coverage view'),
        ('packs', 'the packs as they stand: route, bank, source, file counts, who heard them, rebuild commands — and which two were retired and deleted 2026-11-28 (D89)'),
        ('format', 'the .stream file format contract (container, IMA ADPCM block, byte-rate rule, Vorbis exception, variants, codec pointer) — moved here from the deleted analysis doc'),
        ('install', 'how to install and check a pack, and what was tried before (the dropped BeardLib route, D61) — moved here from the deleted install doc'),
        ('heister_callouts', 'the event-name callout table (g/p/v/f/l/s/d/whistling …) from the community Heister Voice IDs sheet; event names, NOT ids — reference only (manual keybinds / the dropped route)'),
        ('bodhi', 'the Bodhi lines (1,351 rows, 1,344 distinct ids, 25 tabs) — the only Bodhi data in the repository'),
        ('miranda_transcripts', 'the 866 source oggs\' whisper transcripts + hand corrections (the corrected column wins)'),
        ('coverage', 'what each source declares vs what is held, computed from the data'),
        ('transcripts', 'the raw machine-transcription table (source → file → id → draft text), the evidence behind every transcript column'),
        ('', ''),
        ('OPEN', ''),
        ('O1', 'Does Rust bark from regular_vox (packs write it) or char_rust (Marine pack exists)? One in-game install or a game extraction of soundbanks/streamed/char_rust decides it (docs/pd2-las/in-game-checklist.md 1e).'),
        ('O2', 'char_rust line→id map: needs a game extraction decoded line by line; the sheet cannot fill it (different bank, no overlap).'),
        ('O3', f"robbers_mission_gen: {stats['rob_no_text']:,} of {stats['rob_rows']:,} ids have no text anywhere reachable (the Sydney .docx backfilled 145 of the 3,686 rows with neither who nor line); the two reference packs cover 422 of them (machine drafts as reading aids, not wording)."),
        ('O4', 'Geralt and Arivus takes are TTS, wording unverified by ear; Mira takes likewise ("text unverified" everywhere).'),
        ('O5', 'Sydney’s char_sydney bank: the .docx’s second table (224 robbers ids) is mission chatter, folded into the robbers_mission_gen tab — it is not part of this bank. No .pdf-only ids remain: every flagged id is in the .docx; the CSV-only id (75103998) is in neither (1,037 vs 1,077).'),
        ('REBUILD', 'make -sC tools/pd2-las voices_master  (writes this file, the per-tab CSVs in vo_master/ and prints counts). --asr re-transcribes into vo_transcripts.csv (needs the reference archives, it extracts them itself into build/vo-master/).'),
    ]
    return KV_FIELDS, [dict(key=k, value=v) for k, v in B]

SOURCES_FIELDS = ['source', 'role', 'rows', 'what_it_is', 'notes']

def tab_sources(data, stats):
    S = [
        ('references/sheets/PAYDAY 2 Sound files - regular_vox.csv', 'community export (used via sheets/regular_vox.csv)', '20,404', 'The community regular_vox tab, status block intact; imported in full 2026-11-26 (D81)', 'NOT the bank the packs write (0/885 id overlap — finding F1); kept as the id→line evidence for its own bank'),
        ('voice_lines_vox/sheets/regular_vox.csv', 'used (regular_vox tab)', '20,404 (20,403 ids + 1 dup id 1052460785, kept not merged)', 'Normalized community table: id,who,what,notes,needs_review; 29 needs_review; 22 speakers (Cop (static) 3,159 · Cop 2,291 · Chains 1,911)', 'Generated by tools/import_voiceline_sheet.py; status block re-checked FULL at import'),
        ('references/sheets/PAYDAY 2 Sound files - robbers_mission_gen.csv', 'community export (used via sheets/robbers_mission_gen.csv)', '5,499', 'Community robbers_mission_gen tab (measured): 1,811 rows carry a `who` (1,720 with a line), 1,722 carry a line, 3,686 carry neither', 'Matches the pack banks (196/202 tokoyami, 213/220 marine share ids)'),
        ('voice_lines_vox/sheets/robbers_mission_gen.csv', 'used (robbers_mission_gen tab)', '5,499', 'Normalized: id,who,what,notes,needs_review', 'The usable part is the 1,722 text rows; the rest wait for text (Sydney .docx covers 145 of them)'),
        ('references/sheets/PAYDAY 2 Sound files - char_sydney.csv', 'community export (used)', '1,037', 'Sydney\'s bank, 100% complete, all Sydney', 'Sub-Type/second Notes columns exist only in the export and the .docx/.pdf, not in the normalized file'),
        ('voice_lines_vox/sheets/char_sydney.csv', 'used (char_sydney tab)', '1,037', 'Normalized char_sydney', 'Type lands in notes; Sub-Type not carried'),
        ('references/sheets/Syndey Voicelines.docx', 'used (char_sydney tab + robbers_mission_gen tab)', '1,302 digit-id rows / 1,301 distinct ids, in two tables', 'Word export of the Sydney sheet: table 0 = char_sydney (1,078 rows, 1,077 ids); table 1 = Sydney’s robbers_mission_gen lines (224 ids)', 'The fuller Sydney source; char_sydney∩CSV is 1,036 (41 docx-only); 1 CSV-only id; all 224 robbers ids sit in the robbers tab'),
        ('references/sheets/Syndey Voicelines.pdf', 'used (char_sydney tab; flags)', '68 pages, 1,301 ids', 'The same document printed; id set = both .docx tables together', 'Line text is not re-parsed from the print; flags only'),
        ('references/sheets/Bodhi Voicelines.zip', 'used (bodhi tab)', '1,351 rows / 1,344 distinct ids / 25 tabs', 'Bodhi Voicelines.xlsx — the only Bodhi data in the repository', 'Blank Sheet (6 rows of notes) excluded; robbers_mission_gen tab carries 245 ids, sheet-specific'),
        ('references/sheets/Payday 2 Voiceline IDs - Heister Voice IDs.csv', 'used (heister_callouts tab)', '230 parsed event entries', 'Community callout table: g/p/v general/specials/… event names with meanings; used for manual keybinds and the dropped route', 'Event NAMES, not numeric ids; not the bank the packs write; Heister sheet\'s own caveats apply'),
        ('voice_lines_vox/hila_regular_vox.csv', 'used (hila fields in regular_vox tab)', '887 rows / 885 ids (list has 2 repeated ids)', 'Hila\'s regular_vox line list: id, speech, category — the provenance of the pack bank', 'The 885 ids the stream packs write; NOT in the community export (F1)'),
        ('voice_lines_vox/miranda_lawson/hila_intent_cuts.csv', 'used (regular_vox, slots)', '885', 'Hila id → speech/category/intent/slot/cut_line — the authoritative cut table for the packs', 'Source of slot and cut_line cells'),
        ('voice_lines_vox/miranda_lawson/hila_semantic_fit.csv', 'used (slots)', '79 slots', 'Semantic fit 0–10 per slot vs game intention; status kept/replaced_tts/removed', 'Score drives the vanilla-removal rule (<8 → vanilla unless a take exists)'),
        ('voice_lines_vox/miranda_lawson/removed_slots.csv', 'used (regular_vox, slots)', '17 slots / 162 ids', 'Slots left vanilla by the sub-8 rule, with what they replaced and why', 'Builders refuse to pick for these; pack leaves the ids alone'),
        ('voice_lines_vox/miranda_lawson/hila_vorbis_ids.csv', 'used (regular_vox, format)', '27 ids', 'The shared ids the vanilla bank streams as Wwise Vorbis (fmt 0xFFFF)', 'No ADPCM pack can write them; vanilla plays; excluded from every pack'),
        ('voice_lines_vox/miranda_lawson/miranda_transcripts_corrected.csv', 'used (miranda_transcripts tab)', '866', 'Whisper transcripts + hand corrections for the 866 source oggs in Голос Лоусон.7z', 'corrected_transcript wins; whisper_transcript kept for diff'),
        ('voice_lines_vox/miranda_lawson/slot_picks.csv', 'used (slots)', '62', 'Hand-curated clip per Miranda slot (file + time range)', 'The pack\'s clip list'),
        ('voice_lines_vox/miranda_lawson/hila_intent_fit.csv', 'not imported', '79', 'Generated fit scores per slot', 'Superseded by hila_semantic_fit.csv for the keep/remove decision; kept for reference'),
        ('voice_lines_vox/miranda_lawson/hila_slot_pieces.csv', 'not imported', '62', 'Build record of exact cuts', 'Per-slot drill-down; nothing in the workbook needs it (pack manifests hold id→clip)'),
        ('voice_lines_vox/miranda_lawson/hila_to_miranda_mapping.csv', 'not imported', '885', 'Hila id → heuristic Miranda file hint', 'A suggestion table; the picks table wins'),
        ('voice_lines_vox/miranda_lawson/ogg_phrase_splits.csv', 'not imported', '866', 'Per-ogg phrase boundaries used when cutting barks', 'Build input; not a line mapping'),
        ('voice_lines_vox/miranda_lawson/slot_event_ids.csv', 'used (Geralt_VO_over_Rust event redirects)', '79', 'Slot → PAYDAY 2 bark event names (PlayerSound:say)', 'Used by Geralt_VO_over_Rust (<redirect prefix="rb16"/>, D97); Hila stream pack keys on numeric ids instead'),
        ('voice_lines_vox/geralt/rust_beardlib_takes.csv', 'used (Geralt_VO_over_Rust)', '36', 'All 36 Geralt takes → OGG trim windows, <random> pools, and rb16 bark event redirects', '29 bark slots (civ.down x4, inspire.faster x2, mask.go x2) + 2 summon callouts (f21ab_sin, f21d_sin)'),
        ('voice_lines_vox/targets/rust_shared_regular_vox.csv', 'used (regular_vox written_geralt, packs)', '885', 'Slot → bank → id for Rust on the shared bank; written=315 (Geralt pack)', 'Generated by tools/build_stream_tables.py; pinned by tests/test_stream_tables.py'),
        ('voice_lines_vox/targets/old_hoxton_shared_regular_vox.csv', 'used (regular_vox written_arivus, packs)', '885', 'Same for Old Hoxton; written=324 (Arivus pack)', 'Same generator, same pin'),
        ('voice_lines_vox/targets/rust_dedicated_char_rust.csv', 'used (char_rust tab)', '1,046', 'Measured char_rust ids (Marine VO for Rust pack); slots unknown', 'The re-key table (D76); refuses to fill without a game extraction'),
        ('references/voice/Tokoyami Hila.7z', 'used (transcripts; format evidence)', '887 regular_vox + 202 robbers_mission_gen', 'The reference .stream pack; proof of the id-keyed route', '1,062 files ADPCM; 27 regular_vox are Vorbis (nothing copied into dist/)'),
        ('references/voice/Marine VO for Rust.7z.001/.002', 'used (transcripts; char_rust measurement)', '1,046 char_rust + 220 robbers_mission_gen', 'The reference Rust pack; the measured char_rust bank', 'g36x_any (prefix rb16) redirected to four rust_med_kill OGGs in its main.xml'),
        ('references/voice/Голос Лоусон.7z', 'used (miranda_transcripts; pack audio)', '866 oggs', 'Miranda Lawson\'s own barks; the clips the Hila pack cuts from', 'Whisper-transcribed + hand-corrected (see miranda_lawson/miranda_transcripts_corrected.csv)'),
        ('references/voice/LAWSON VOICE (PAYDAY 2).7z', 'used (transcripts; pack audio)', '36 mp3s', 'Purpose-authored Mira takes for the slots the real barks do not cover', 'Wording unverified by ear'),
        ('references/voice/GERALT VOICE (PAYDAY 2).zip', 'used (transcripts; pack audio)', '36 mp3s (CP866 names)', 'Purpose-authored Geralt barks: 29 slots (with 5 alternates) + 2 callouts (Hila, Hoxton)', 'TTS; file names decode cp866; all 36 takes ship in Geralt_VO_over_Rust.zip'),
        ('references/voice/ARIVUS VOICE (PAYDAY 2).zip', 'used (transcripts; pack audio)', '18 mp3s', 'Purpose-authored Arivus barks, 18 slots', 'TTS; unverified by ear'),
        ('voice_lines_vox/vo_transcripts.csv', 'used (transcripts tab; every transcript column)', str(stats['transcripts_total']) + ' rows', 'Machine transcription of every audio file above (pocketsphinx, 2026-11-27)', 'Unverified drafts; the engine column says so on every row; 27 Vorbis rows are untranscribable here'),
        ('dist/Miranda/Miranda_Lawson_VO_over_Hila_Stream.zip', 'pack (packs tab)', '699 .stream files', 'The shipped Hila pack (manifest: hila_stream_map.csv, 885 rows)', 'Heard in game 2026-11-25 (user): works'),
        ('dist/Geralt/Geralt_VO_over_Rust.zip', 'pack (packs tab)', '36 .ogg files + hooks/beardlib_sound_fix.lua', 'The shipped Geralt-over-Rust BeardLib <Sounds> pack (manifest: geralt_rust_vo_map.csv, 36 rows)', 'Mirrors Marine VO for Rust <redirect prefix="rb16"/> + fixes BeardLib 5.2.0 SoundManager lifecycle bugs (D97)'),
        ('Geralt_VO_over_Rust_Stream.zip (deleted from dist/ 2026-11-28, D89)', 'pack (packs tab)', '315 .stream files', 'The Geralt pack, retired and deleted from dist/ 2026-11-28 (D89); manifest: geralt_rust_stream_map.csv', 'Never heard in game; kept visible for the record, not installable'),
        ('Arivus_VO_over_Hoxton_Stream.zip (deleted from dist/ 2026-11-28, D89)', 'pack (packs tab)', '324 .stream files', 'The Arivus pack, retired and deleted from dist/ 2026-11-28 (D89); manifest: arivus_hoxton_stream_map.csv', 'Never heard in game; carried the borrowed Geralt \'Hoxton.\' callout; not installable'),
        ('tools/build_vo_master.py', 'this workbook\'s generator (make -sC tools/pd2-las voices_master)', '—', 'Reads the above; writes vo_master.xlsx + vo_master/*.csv + vo_transcripts.csv (--asr)', 'The workbook is only reproducible from here; do not hand-edit'),
    ]
    return SOURCES_FIELDS, [dict(source=s, role=r, rows=n, what_it_is=w, notes=nn) for s, r, n, w, nn in S]

def tab_format(data):
    vorbis_ids = [r['hila_id'] for r in read_csv(ML / 'hila_vorbis_ids.csv')]
    B = [
        ('what_this_tab_is', 'The .stream file format the stream packs write, and WHY the game plays them. Moved here verbatim-in-substance from docs/tokoyami-hila-voice-mod-analysis.md (deleted 2026-11-28); the dissection of Tokoyami Hila.7z is the evidence.'),
        ('the_rule', 'A PAYDAY 2 heister line is a file soundbanks/streamed/<bank>/<id>.stream. The id is the file NAME, a 32-bit Wwise id; the bank folder says which heister/lines. The game plays the file under the id — no Lua, no event table, no BeardLib.'),
        ('bank_folders', 'regular_vox = the shared bank (original crew; every pack here writes it) · robbers_mission_gen = heist-scripted mission chatter · char_<module> = dedicated heister banks (char_rust, char_sydney, char_joy…) · safehouse_vo = safe house. The packs write regular_vox; the re-key (char_rust) is blocked on the id map (D76).'),
        ('bank_modules', 'NEVER MIX THE BANKS. Rust is switch rb16 (dedicated bank char_rust); Old Hoxton is switch rb5 and his lines are the shared bank — no documented char_hoxton folder exists and none is tracked. A file written to a folder the heister does not stream from is inert, and it replaces the wrong heister’s line if that other heister streams from it. The packs write the shared bank; whether Rust barks from it is the open question O1 (one in-game install decides it).'),
        ('reference_pack', 'Tokoyami Hila.7z (“Tokoyami Towa Voice for Hila”, the evidence this format comes from): main.xml with one <Hooks> node → hooks/localization.lua renaming Hila → “Towa” (cosmetic; audio works without it); 1,089 .stream files — regular_vox 887, robbers_mission_gen 202; 1,062 IMA ADPCM + 27 Wwise Vorbis; two DDS-wrapped ecp_female.texture icons. No <Sounds>, no BeardLib module, no OGG — the soundbanks are the entire mod.'),
        ('reference_pack_ids', 'the 887 regular_vox files are the 885 hila_regular_vox ids plus 124616049 and 134711817, which appear in NO tracked table (noted, unused — do not adopt them). The 202 robbers files: 196 ids sit in the community robbers_mission_gen export; 6 do not.'),
        ('', ''),
        ('CONTAINER (RIFF, 64-byte header, both variants)', ''),
        ('mono_layout', '0000 RIFF size=filesize-8 WAVE · 000c "fmt " payload 24 · 0014 wFormatTag 2 (IMA ADPCM) channels 1 · 0018 sample rate 44100 · 001c byte rate 24804 · 0020 block align 36, 4 bits/sample, cbSize 6 · 0028 six-byte Wwise tail 00 00 04 00 00 00 · 002e "JUNK" 4 zeros · 003a "data" <size> · 0040 audio'),
        ('stereo_tail', 'stereo differs only in channels=2, block align 72, byte rate 49608, and the six-byte fmt tail 00 00 03 00 00 00'),
        ('byte_rate_rule', 'byte rate = (sample_rate // 64) * block_align  → 44.1 kHz mono 24,804 · 22.05 kHz mono 12,384 · 22.05 stereo 24,768 · stereo 44.1 kHz 49,608. The textbook rate*block_align/64 gives 24,806 — the game reads the floored form; wwise_ima.py writes it and tests/test_wwise_ima.py pins it.'),
        ('variants_measured', 'across the 1,089 files in Tokoyami Hila.7z only four ADPCM variants exist: 44.1 kHz mono (394), 44.1 kHz stereo (631), 22.05 kHz mono (33), 22.05 kHz stereo (4). data is always a whole number of blocks and RIFF size = filesize − 8.'),
        ('', ''),
        ('PER BLOCK', ''),
        ('block', 'one 36-byte sub-block per channel, in channel order (72 bytes stereo): +0 int16 predictor (first sample, verbatim) · +2 uint8 step index 0..88 · +3 reserved 0 · +4 32 bytes nibbles, low nibble first'),
        ('frames', 'a block is 64 frames: the header sample plus 63 coded samples; the 64th nibble is padding and is 0 in practice'),
        ('nibble', '3 bits magnitude (0–7) + sign bit (8). delta = ((2*mag + 1) * step) >> 3, added or subtracted, clamped to int16. Index moves by (-1,-1,-1,-1,2,4,6,8)[mag], clamped 0..88'),
        ('blocks_independent', 'predictor and index restart from the header every 36 bytes — which is what makes offline encoding possible and what makes the per-block start index matter (13 dB SNR from index 0 vs 30–35 dB when chosen per block)'),
        ('', ''),
        ('THE 27 VORBIS IDS (fmt tag 0xFFFF, cbSize 48, Wwise Vorbis — NOT decodable by the codec here)', ''),
        ('vorbis_ids', ', '.join(vorbis_ids)),
        ('vorbis_rule', 'an ADPCM pack cannot write these ids — they are left vanilla. Any dedicated bank measured in full will contain its own Vorbis files and must be filtered the same way. (hila_vorbis_ids.csv is the tracked list; every regular_vox row here carries the flag.)'),
        ('', ''),
        ('CODEC AND BUILD', ''),
        ('codec_location', 'tools/pd2-las/wwise_ima.py — read, decode, encode, write. Reads a .stream and prints header/duration/peak (python tools/pd2-las/wwise_ima.py FILE.stream [--wav out.wav]); encodes reproducibly (integer-only numpy batches; -fflags +bitexact everywhere; per-block start-index search)'),
        ('verification', 'header bytes identical to a real mono file; every stream decodes; manifest agrees with zip; packs heard in game: Hila pack yes (user, 2026-11-25), Geralt/Arivus no. Vorbis ids and removed slots are intentionally vanilla — that is coverage, not failure.'),
        ('manifests', 'each pack carries its build manifest: hila_stream_map.csv / geralt_rust_stream_map.csv / arivus_hoxton_stream_map.csv (id → slot → clip), plus main.xml (a <mod> marker only, no <Sounds>/<Hooks>) and mod.txt (BLT list metadata)'),
    ]
    return KV_FIELDS, [dict(key=k, value=v) for k, v in B]

def tab_install():
    B = [
        ('what_this_tab_is', 'How to install, check and uninstall the VO pack — and what was already tried. Moved here from docs/pd2-voice-mod-install.md (deleted 2026-11-28). The decision to keep only the id-keyed route is D61 in docs/pd2-las/DECISIONS.md.'),
        ('prerequisites', 'Any BLT / SuperBLT build. No BeardLib, no Lua, no XAudio API, nothing to enable in the mod list beyond the mod itself.'),
        ('', ''),
        ('INSTALL (one pack — see packs tab, install exactly one)', ''),
        ('layout', 'PAYDAY 2/\n └─ mods/\n     └─ <Mod Folder>/            ← folder name is free-form, one folder deep\n         ├─ main.xml              ← <mod name="…"> and nothing else; BLT serves the files\n         ├─ mod.txt               ← makes the folder appear in the main-menu mod list\n         ├─ README.txt\n         ├─ <pack>_stream_map.csv     ← build manifest: id → slot → clip\n         └─ soundbanks/streamed/regular_vox/<id>.stream   ← one file per written voice-line id'),
        ('steps', '1. Unzip the pack into PAYDAY 2/mods/ so that mods/<Mod Folder>/main.xml exists (one folder deep — double nesting is the classic failure).\n2. Start the game.\n3. Play a heist as the pack\'s heister (or with them as AI teammate).\n4. Nothing in mods/logs/ is expected: the pack has no Lua and no loader API to fail.'),
        ('uninstall', 'Remove the folder, or toggle the mod off in the main-menu list. Nothing is written anywhere else; removal is complete.'),
        ('if_a_line_still_sounds_vanilla', 'It is one of: (a) the 27 Vorbis ids (format tab) — no pack can fix those; (b) a slot left vanilla by rule (removed_slots; slots with no take); (c) another pack installed after this one writing the same ids — last wins; (d) Rust barks from char_rust, not regular_vox — the shared bank pack then changes everyone else, not Rust (open question O1; docs/pd2-las/in-game-checklist.md 1e).'),
        ('verify_offline', 'make -sC tools/pd2-las voices_stream   # rebuild + print state (is: tracked)\nunzip -p <pack>.zip "<folder>/soundbanks/streamed/regular_vox/712675.stream" > 712675.stream\npython tools/pd2-las/wwise_ima.py 712675.stream --wav 712675.wav   # header, duration, audio'),
        ('', ''),
        ('TROUBLESHOOTING THE INSTALL (from the dropped-route post-mortem, still applies to the .stream route)', ''),
        ('t1_layout', 'mods/<folder>/main.xml must exist exactly one folder deep. BeardLib (when present) scans only mods/* — no recursion, no other roots.'),
        ('t2_superblt_log', 'mods/logs/: if anything about the BLT build failed to load the folder it will say so there. The .stream pack logs nothing on success — silence is normal.'),
        ('t3_mod_list', 'Main menu → Mods: the pack (from mod.txt) is listed and enabled. BeardLib needs no entries for this pack.'),
        ('t4_hear_it', 'A replaced id sounds like the pack voice; a vanilla id sounds like Hila/Rust/whoever. There is no per-line log line — check by ear, one slot at a time.'),
        ('t5_double_nesting', 'The zips are named with underscores; the folder inside uses spaces — extract into mods/ directly and do not create a folder after the zip\'s name.'),
        ('t6_one_pack_only', 'With several packs installed the last loaded wins for the ids they share; uninstall the others to reason about one pack at a time.'),
        ('', ''),
        ('THE ROUTE THAT WAS TRIED AND DROPPED (record)', ''),
        ('beardlib_route', 'Miranda_Lawson_VO_over_Hila.zip (dropped 2026-11-25, D61) keyed BeardLib <Sounds prefix="rb21"> on PD2 bark EVENT names (g18 …) with OGG clips. It re-verified correct against the loaders (Frameworks.lua FindMods; SoundsModule; SoundManager:CheckSoundID; tweak_data rb21 for player and AI teammate; BeardLibSetSwitch maps the robber switch into engine_source prefixes and ComparePrefixes matches on them) — and it never made a line play. Kept on 2026-11-24/25 as evidence; removed from dist/ on 2026-11-25. The .stream route is what the game itself uses (the reference pack proves it) and is the only one heard working.'),
        ('why_dropped', 'Not because the keying was wrong — because nothing came out of it in game. The investigation (loader internals, Lua paths, tweak_data) is recorded in D61 (docs/pd2-las/DECISIONS.md); the HISTORICAL packaging analysis of that route was deleted with the install doc on 2026-11-28 and its load-bearing facts live here (T-rows) and in the format tab.'),
        ('xp', 'If you ever rebuild a BeardLib/OGG pack: prerequisites were SuperBLT (blt.xaudio — vanilla BLT/BLT4 errors "Sounds module requires the XAudio API!") and BeardLib 5.x; SoundsModule resolves paths relative to the mod folder, substitutes <id>.ogg for missing <path>, and CheckSoundID intercepts every posted sound comparing (id, prefixes). The pack shipped 78 clips over 176 bark events with mod.txt present. It still did not play. Do not resurrect it without a new reason.'),
        ('', ''),
        ('PACK NOTES', ''),
        ('hila_pack', 'Miranda over Hila: 699 .stream files (661 s), all of Hila\'s 885 ids minus 27 Vorbis and the 162 below-fit ids of the 17 removed slots. Manifest hila_stream_map.csv. Heard in game (user, 2026-11-25): works; two clips were re-cut after that report (civ.down, call_teammate.hey_you), so the tracked bytes are newer than what was heard.'),
        ('geralt_vo_rust', 'Geralt_VO_over_Rust (D97): 36 mono 44.1 kHz Ogg Vorbis takes across 29 bark slots (<random> on civ.down x4, inspire.faster x2, mask.go x2) + 2 summon shouts (f21ab_sin Hila, f21d_sin Old Hoxton) = 45 bark events on prefix="rb16", mirroring Marine VO for Rust\'s <Sounds> layout plus hooks/beardlib_sound_fix.lua so BeardLib 5.2.0 keeps XAudio buffers alive across Setup:unload_packages into heists. Extract into PAYDAY 2/assets/mod_overrides/Geralt VO over Rust/ (or mods/). Uncovered Rust lines stay vanilla.'),
        ('geralt_pack', 'Geralt_VO_over_Rust_Stream (historical): 315 .stream files for the 29 slots the set carries (alternate takes civ.down (2..4), mask.go (2), inspire.faster (2) left unused). Retired and deleted from dist/ 2026-11-28 (D89); superseded by Geralt_VO_over_Rust (D97).'),
        ('arivus_pack', 'Arivus over Old Hoxton: 324 .stream files — 18 slots the set carries plus call_teammate.hey_you, which plays the GERALT \'Hoxton.\' callout (borrowed per the user\'s 2026-11-25 decision); that slot is Geralt\'s voice. The pack otherwise is Arivus\'s. Hog: Old Hoxton is on the shared bank, so the pack replaces the line for every heister on regular_vox, not for Hoxton alone. Retired and deleted from dist/ 2026-11-28 (D89); never heard in game.'),
        ('rekey', 'A re-keyed Geralt build (same takes into soundbanks/streamed/char_rust/) is wired as make -sC tools/pd2-las voices_char_rust and refuses until voice_lines_vox/geralt/char_rust_ids.csv names every id (D76). The name would make the pack change Rust alone. Do not ship it until the map is filled from a game extraction.'),
    ]
    return KV_FIELDS, [dict(key=k, value=v) for k, v in B]

COV_FIELDS = ['metric', 'value', 'notes']

def tab_coverage(data, stats):
    t = data['transcripts']
    def cnt(pred):
        return sum(1 for r in t if pred(r))
    comm = read_csv(SHEETS / 'regular_vox.csv')
    speakers = {}
    for r in comm:
        speakers[r['who']] = speakers.get(r['who'], 0) + 1
    top = ' · '.join(f"{k} {v:,}" for k, v in sorted(speakers.items(), key=lambda kv: -kv[1])[:3])
    match = stats['regular_match']
    R = [
        ('regular_vox — community export declares', '20,343 rows (20,293 complete · 50 partial · 0 incomplete · 32 marked (?))', 'status block of the export; the block is stale — rows were added after it was written'),
        ('regular_vox — rows held / distinct ids', f"{stats['regular_rows']:,} / {stats['regular_distinct']:,}", 'one repeated id (1052460785) kept, not merged; 29 rows carry needs_review'),
        ('regular_vox — speakers (top 3)', top, '22 speakers in the export'),
        ('regular_vox ∩ Hila pack bank (885)', '0', 'MEASURED: the pack bank\'s 885 ids appear nowhere in the community export — the export is a different bank than the one the packs write (finding F1)'),
        ('Hila pack bank — in this workbook', f"{stats['hila_rows']} rows, all 885 ids", 'two of the list\'s 887 rows repeat ids; all 885 appear as hila-dlc-bank rows'),
        ('Tokoyami regular_vox transcription', f"{stats['tokoyami_regular']} of 887 files, {stats['tokoyami_nonempty']} non-empty drafts", 'pocketsphinx; cross-checked against hila_regular_vox speech text — see match columns'),
        ('…high match (≥0.6 word overlap)', str(match['high']), 'text and draft agree'),
        ('…partial match (0.35–0.6)', str(match['partial']), 'directionally right, needs review'),
        ('…low / no match', str(match['low'] + match['no-text']), 'draft does not corroborate the line text'),
        ('robbers_mission_gen — declares', '4,220 rows (1,720 complete · 93 partial · 2,407 incomplete · 14 marked (?))', 'status block of the export; stale the same way'),
        ('robbers_mission_gen — rows held / distinct ids', f"{stats['rob_rows']:,} / {stats['rob_distinct']:,}", '5,499 community rows (+13 pack-only, +1 Sydney .docx-only = 5,513 in this tab); 1,868 rows carry a line after the Sydney .docx backfill, 3,645 carry none (measured)'),
        ('robbers_mission_gen — packs present', f"Tokoyami {stats['rob_tok']} files ({stats['rob_tok_in_sheet']} ids in the community tab) · Marine {stats['rob_mar']} files ({stats['rob_mar_in_sheet']} in it)", 'every pack file transcribed; 6 (Tokoyami) and 7 (Marine) ids appear in no community row'),
        ('robbers_mission_gen — machine drafts', f"Tokoyami {stats['rob_tok_asr']} non-empty · Marine {stats['rob_mar_asr']} non-empty", 'pocketsphinx; unverified; the community text wins where it exists'),
        ('char_rust — measured bank', f"{stats['char_rust']:,} ids", f"Marine VO for Rust.7z.001; 0 shared with community regular_vox; {len(stats['char_rust_rob_overlap'])} shared with community robbers_mission_gen ({', '.join(stats['char_rust_rob_overlap']) or 'none'})"),
        ('char_rust — machine drafts', f"{stats['char_rust_asr']} of {stats['char_rust']:,} non-empty ({stats['char_rust_asr_empty']} files produced no draft)", 'line↔id mapping impossible from the pack; needs a game extraction (D76)'),
        ('char_rust — Vorbis files in the reference pack', str(stats['char_rust_vorbis']), 'MEASURED: Marine char_rust carries this many Wwise Vorbis files (fmt tag 0xFFFF), not decodable with the ADPCM codec — the Tokoyami pack has its own 27 (the hila_vorbis_ids list); a dedicated-bank pack must filter both the same way'),
        ('char_sydney — CSV', f"{stats['sydney_csv']:,} ids (0 needs_review)", 'the complete written-up dedicated bank'),
        ('char_sydney — .docx', f"{stats['sydney_docx']:,} ids (a fuller sheet, not a duplicate; table 0 only — table 1 is mission chatter, in the robbers tab)", f"{stats['sydney_docx_only']} ids beyond the CSV; overlap with CSV is 1,036; {stats['sydney_csv_only']} CSV-only id"),
        ('char_sydney — .pdf', f"{stats['sydney_pdf']:,} ids", 'printed edition of the .docx (both tables); the char_sydney tab holds the char_sydney share; text not re-parsed'),
        ('char_sydney — union in this workbook', f"{stats['sydney_union']:,} ids", 'what the char_sydney tab holds; flags say which source has each'),
        ('char_sydney — pdf-only ids (no line text anywhere)', str(stats['sydney_pdf_only']), 'the print adds no id beyond the .docx; flags only'),
        ('robbers_mission_gen — Sydney .docx lines', f"{stats['sydney_rob_docx']} rows ({stats['sydney_rob_backfilled']} backfilled community audio-only rows, {stats['sydney_rob_new']} new id)", 'Sydney-voiced mission chatter from the same .docx; 223 of the 224 sit in the community export (9 word-identical, 75 sharing ≥1 word; wording is Sydney’s own)'),
        ('Bodhi — rows / distinct ids', f"{stats['bodhi_rows']:,} / {stats['bodhi_distinct']:,}", '25 tabs; the only Bodhi data in the tree; blank tab excluded'),
        ('packs — Miranda_Lawson_VO_over_Hila_Stream', '699 .stream files · 62 slots · 885 ids mapped', 'heard in game 2026-11-25 (user): works'),
        ('packs — Geralt_VO_over_Rust', '36 .ogg files · 29 slots + 2 callouts · 45 bark events on rb16', 'BeardLib <Sounds> + Lua XAudio lifecycle fix (D97); uncovered Rust lines stay vanilla'),
        ('packs — Geralt_VO_over_Rust_Stream', '315 .stream files · 29 slots', 'RETIRED 2026-11-28: deleted from dist/ (D89); never heard in game'),
        ('packs — Arivus_VO_over_Hoxton_Stream', '324 .stream files · 19 slots (18 + call_teammate.hey_you)', 'RETIRED 2026-11-28: deleted from dist/ (D89); never heard in game; carried the borrowed Geralt callout'),
        ('machine transcription — engine', 'pocketsphinx 5.x en-us', 'whisper models unreachable from this environment (HF/Azure blocked); every draft is unverified and flagged'),
        ('machine transcription — coverage', f"{stats['transcripts_total']:,} files, {stats['transcripts_done']:,} transcribed, {stats['transcripts_vorbis']} Vorbis (not decodable)", 'Voices transcribed: Tokoyami regular_vox + robbers_mission_gen, Marine char_rust + robbers_mission_gen, Mira/Geralt/Arivus takes, 4 medic_kill takes'),
        ('Miranda source oggs — transcribed', '866/866 (whisper + hand corrections)', 'miranda_lawson/miranda_transcripts_corrected.csv; corrected_transcript is the text of record'),
        ('needs_review — regular_vox rows', str(sum(1 for r in comm if r['needs_review'] == 'yes')), 'community flags; plus machine-draft rows everywhere'),
        ('needs_review — robbers_mission_gen rows', str(sum(1 for r in read_csv(SHEETS / 'robbers_mission_gen.csv') if r['needs_review'] == 'yes')), 'community flags'),
        ('needs_review — char_sydney rows', '0', 'complete bank'),
    ]
    return COV_FIELDS, [dict(metric=m, value=str(v), notes=n) for m, v, n in R]

TEXT_WRAP_TABS = {'README', 'SOURCES', 'format', 'install', 'coverage'}

def build_all():
    hila = load_hila()
    targets = load_targets()
    transcripts, by_id = load_transcripts()
    stats = {'transcripts_total': len(transcripts),
             'transcripts_done': sum(1 for t in transcripts if t['transcript']),
             'transcripts_vorbis': sum(1 for t in transcripts if t['fmt'] == 'vorbis'),
             'char_rust_rob_overlap': sorted({r['id'] for r in read_csv(TARGETS / 'rust_dedicated_char_rust.csv')}
                                              & {r['id'] for r in read_csv(SHEETS / 'robbers_mission_gen.csv')})}
    data = {'hila': hila, 'targets': targets, 'transcripts': transcripts,
            'transcripts_by_id': by_id}

    tabs = []
    def add(name, fields, rows):
        tabs.append((name, fields, rows))

    # regular_vox first so coverage can quote it
    rv_fields, rv_rows = tab_regular_vox(data)
    add('regular_vox', rv_fields, rv_rows)
    stats['regular_rows'] = len(rv_rows)
    stats['regular_distinct'] = len({r['id'] for r in rv_rows})
    stats['hila_rows'] = sum(1 for r in rv_rows if r['hila_line'] == 'yes')
    stats['regular_match'] = {k: sum(1 for r in rv_rows if r['transcript_match'] == k)
                              for k in ('high', 'partial', 'low', 'no-text')}

    rob_fields, rob_rows = tab_robbers(data)
    add('robbers_mission_gen', rob_fields, rob_rows)
    stats['rob_rows'] = len(rob_rows)
    stats['rob_distinct'] = len({r['id'] for r in rob_rows})
    stats['rob_tok'] = sum(1 for r in rob_rows if r['in_tokoyami'] == 'yes')
    stats['rob_mar'] = sum(1 for r in rob_rows if r['in_marine'] == 'yes')
    comm_rob_ids = {r['id'] for r in read_csv(SHEETS / 'robbers_mission_gen.csv')}
    stats['rob_tok_in_sheet'] = sum(1 for r in rob_rows if r['in_tokoyami'] == 'yes' and r['id'] in comm_rob_ids)
    stats['rob_mar_in_sheet'] = sum(1 for r in rob_rows if r['in_marine'] == 'yes' and r['id'] in comm_rob_ids)
    stats['rob_tok_asr'] = sum(1 for r in rob_rows if r['transcript_tokoyami'])
    stats['rob_mar_asr'] = sum(1 for r in rob_rows if r['transcript_marine'])

    syd_fields, syd_rows = tab_sydney(data)
    add('char_sydney', syd_fields, syd_rows)
    stats['sydney_csv'] = sum(1 for r in syd_rows if r['in_csv'] == 'yes')
    stats['sydney_docx'] = sum(1 for r in syd_rows if r['in_docx'] == 'yes')
    stats['sydney_pdf'] = sum(1 for r in syd_rows if r['in_pdf'] == 'yes')
    stats['sydney_union'] = len(syd_rows)
    stats['sydney_pdf_only'] = sum(1 for r in syd_rows
                                   if r['in_pdf'] == 'yes' and r['in_docx'] != 'yes' and r['in_csv'] != 'yes')
    stats['sydney_csv_only'] = sum(1 for r in syd_rows if r['in_csv'] == 'yes' and r['in_docx'] != 'yes')
    stats['sydney_docx_only'] = sum(1 for r in syd_rows if r['in_docx'] == 'yes' and r['in_csv'] != 'yes')
    stats['sydney_rob_docx'] = sum(1 for r in rob_rows if r['sydney_docx'] == 'yes')
    stats['sydney_rob_backfilled'] = sum(1 for r in rob_rows
                                         if r['sydney_docx'] == 'yes' and 'backfilled' in (r['notes'] or ''))
    stats['sydney_rob_new'] = sum(1 for r in rob_rows
                                  if r['sydney_docx'] == 'yes' and 'only in the Sydney .docx' in (r['notes'] or ''))
    stats['rob_no_text'] = sum(1 for r in rob_rows if not r['what'].strip())

    stats['char_rust'] = len(read_csv(TARGETS / 'rust_dedicated_char_rust.csv'))
    stats['char_rust_vorbis'] = sum(1 for t in transcripts if t['source_archive'].startswith('Marine')
                                   and t['bank'] == 'char_rust' and t['fmt'] == 'vorbis')
    stats['char_rust_asr_empty'] = sum(1 for t in transcripts if t['source_archive'].startswith('Marine')
                                      and t['bank'] == 'char_rust' and not t['transcript'] and t['fmt'] != 'vorbis')
    stats['char_rust_asr'] = sum(1 for r in transcripts if r['source_archive'].startswith('Marine')
                                 and r['bank'] == 'char_rust' and r['transcript'])
    stats['tokoyami_regular'] = sum(1 for r in transcripts if r['source_archive'] == 'Tokoyami Hila.7z'
                                    and r['bank'] == 'regular_vox')
    stats['tokoyami_nonempty'] = sum(1 for r in transcripts if r['source_archive'] == 'Tokoyami Hila.7z'
                                     and r['bank'] == 'regular_vox' and r['transcript'])

    cr_fields, cr_rows = tab_char_rust(data)
    add('char_rust', cr_fields, cr_rows)

    slot_fields, slot_rows = tab_slots(data)
    add('slots', slot_fields, slot_rows)
    pack_fields, pack_rows = tab_packs(data)
    add('packs', pack_fields, pack_rows)
    fmt_fields, fmt_rows = tab_format(data)
    add('format', fmt_fields, fmt_rows)
    add('install', KV_FIELDS, tab_install()[1])
    call_fields, call_rows = tab_callouts()
    add('heister_callouts', call_fields, call_rows)
    bod_fields, bod_rows = tab_bodhi()
    add('bodhi', bod_fields, bod_rows)
    stats['bodhi_rows'] = len(bod_rows)
    stats['bodhi_distinct'] = len({r['id'] for r in bod_rows})
    mir_fields, mir_rows = tab_miranda_transcripts()
    add('miranda_transcripts', mir_fields, mir_rows)
    cov_fields, cov_rows = tab_coverage(data, stats)
    add('coverage', cov_fields, cov_rows)
    add('transcripts', TRANSCRIPT_FIELDS, transcripts)
    add('README', KV_FIELDS, tab_readme(data, stats)[1])
    add('SOURCES', SOURCES_FIELDS, tab_sources(data, stats)[1])

    # reorder: README first
    order = ['README', 'SOURCES', 'regular_vox', 'robbers_mission_gen', 'char_sydney',
             'char_rust', 'slots', 'packs', 'format', 'install', 'heister_callouts',
             'bodhi', 'miranda_transcripts', 'coverage', 'transcripts']
    by_name = {n: (f, r) for n, f, r in tabs}
    tabs = [(n, *by_name[n]) for n in order]

    OUT_DIR.mkdir(exist_ok=True)
    for name, fields, rows in tabs:
        write_csv(OUT_DIR / (name + '.csv'), rows, fields)
    write_xlsx(OUT_XLSX, tabs)
    for name, fields, rows in tabs:
        print(f"{name}: {len(rows)} rows")

def write_xlsx(path, tabs):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    import datetime
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, fields, rows in tabs:
        ws = wb.create_sheet(name)
        ws.append(fields)
        for row in rows:
            ws.append([row.get(f, '') for f in fields])
        header_fill = PatternFill('solid', fgColor='263238')
        for cell in ws[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = header_fill
            cell.alignment = Alignment(vertical='center')
        ws.freeze_panes = 'A2'
        if fields != KV_FIELDS:
            ws.auto_filter.ref = ws.dimensions
        wrap = name in TEXT_WRAP_TABS
        for i, f in enumerate(fields, 1):
            width = _col_width(ws, i, wrap)
            ws.column_dimensions[get_column_letter(i)].width = width
        if wrap:
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    cell.alignment = Alignment(wrap_text=True, vertical='top')
        ws.sheet_view.showGridLines = False
    wb.properties.title = 'PAYDAY 2 VO mods — source of truth'
    wb.properties.creator = 'universal-modder (tools/build_vo_master.py)'
    wb.properties.created = datetime.datetime(2026, 11, 27)
    wb.properties.modified = datetime.datetime(2026, 11, 27)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)

def _col_width(ws, idx, wrap):
    if wrap:
        return 118 if idx == 2 else 34
    longest = len(str(ws.cell(row=1, column=idx).value or ''))
    for row in ws.iter_rows(min_row=2, max_col=idx, values_only=True):
        v = row[idx - 1]
        longest = max(longest, min(len(str(v)) if v is not None else 0, 60))
        if longest >= 60:
            break
    return min(max(longest + 2, 9), 62)

def check():
    import tempfile
    global OUT_DIR, OUT_XLSX
    tmp = Path(tempfile.mkdtemp(prefix='vo_master_check_'))
    saved_dir, saved_xlsx = OUT_DIR, OUT_XLSX
    if not saved_dir.exists() or not any(saved_dir.glob('*.csv')):
        print('voice_lines_vox/vo_master/ is missing — run `python tools/build_vo_master.py` first')
        return 1
    OUT_DIR, OUT_XLSX = tmp, tmp / 'vo_master.xlsx'
    try:
        build_all()
    finally:
        OUT_DIR, OUT_XLSX = saved_dir, saved_xlsx
    bad = []
    for f in sorted(saved_dir.glob('*.csv')):
        other = tmp / f.name
        if not other.exists() or other.read_bytes() != f.read_bytes():
            bad.append(f.name)
    for f in sorted(tmp.glob('*.csv')):
        if not (saved_dir / f.name).exists():
            bad.append(f.name + ' (missing in repo)')
    if bad:
        print('vo_master CSVs out of date:', ', '.join(bad))
        return 1
    print('vo_master: CSVs up to date (xlsx is rebuilt from the same rows)')
    return 0

if __name__ == "__main__":
    sys.exit(main())
