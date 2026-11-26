#!/usr/bin/env python3
"""Match corrected Miranda transcripts to Hila intent slots and recut audio."""
from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import hila_voice_clips as vo  # noqa: E402  (the shared removal table)
CUTS = ROOT / "voice_lines_vox/miranda_lawson/hila_intent_cuts.csv"
TR = ROOT / "voice_lines_vox/miranda_lawson/miranda_transcripts_corrected.csv"
SPLITS = ROOT / "voice_lines_vox/miranda_lawson/ogg_phrase_splits.csv"
OUT = ROOT / "voice_lines_vox/miranda_lawson/hila_slot_pieces.csv"
FIT = ROOT / "voice_lines_vox/miranda_lawson/hila_intent_fit.csv"
PICKS = ROOT / "voice_lines_vox/miranda_lawson/slot_picks.csv"

# The player is not Shepard, so no replacement clip may contain a name/rank address.
NAMES = re.compile(r"\b(shepard|commander|commando)\b", re.I)


# slot -> (cut_line leftover, list of (regex, weight, max_words))
# Higher weight = better intent. Short matching lines preferred in scoring.
PATTERNS: dict[str, list[tuple[str, float]]] = {
    "ammo.low": [r"\b(ammo|thermal clip|out of (ammo|clips))\b"],
    "assault.incoming": [
        r"\b(enemies incoming|incoming!?|here they come|got company|they're coming)\b",
        r"\blook out\b",
    ],
    "assault.ready": [r"\b(get ready|i'?m ready|let'?s finish|ready,? commander)\b"],
    "assault.retreat": [r"\b(pulling (out|back)|retreat|falling back)\b"],
    # Call (rb21 CH_Name) = summon a teammate by name, so the line is a generic
    # "Hey, you." bark. "On me." belongs to move.on_me (rb21 Follow) instead.
    "call_teammate.hey_you": [r"^(hey|hi)[,.! ]*(you|there)?[.!]?$", r"\b(hey|hello|you there)\b",
                              r"^(shepard|commander)[.!]?$"],
    "caution.wait": [r"^(wait|hold on|hang on)[.!]?$", r"\b(wait here|hold on,? i)\b"],
    "caution.watch": [r"\b(look out|watch (out|it|what)|careful|don'?t take any chances)\b"],
    "civ.dontmove": [r"\b(don'?t move|hold still|stay where)\b"],
    "civ.down": [r"\b(get down|stay down|down,? now|hit the floor)\b"],
    "civ.killthreat": [r"\b(i'?ll kill|destroy you|you(?:'re| are) dead)\b"],
    "civ.nophone": [r"\b(no (calls|phones)|don'?t (call|radio))\b"],
    "civ.talk": [r"\b(talk|tell me|answer me|what happened)\b"],
    "civ.ties": [r"\b(tie|restrain|cuff them)\b"],
    "cop.cuffs": [r"\bcuffs?\b"],
    "cop.drop": [r"\b(drop it|drop (the|your)|put (it|that) down)\b"],
    "cop.hands": [r"\bhands (up|where)\b"],
    "cop.kneel": [r"\b(knees|kneel)\b"],
    "cuffed.pick": [r"\b(pick (these |my )?cuffs|get these cuffs|restrained)\b"],
    "curse.shit": [r"\b(damn( it)?|goddamn|what the hell|oh my god|you'?ve got to be kidding)\b"],
    "curse.slow": [r"\b(hurry|too slow|move fast)\b"],
    "downed.need_help": [r"\b(i need help|need help|help me|requesting aid)\b"],
    "downed.want_fight": [r"\b(get (me )?up|back in (the )?fight)\b"],
    "drop.ammo": [r"\b(grab .{0,12}ammo|ammo here|heavy ammo)\b"],
    "drop.body": [r"\b(bodies|body bags)\b"],
    "drop.fak": [r"\b(first aid|med kit)\b"],
    "drop.medic": [r"\b(medic( bag)?|med bay)\b"],
    "hurt.hit": [r"\b(i'?m hit|they (got|shot) me|i'?m hurt)\b"],
    "hurt.medic": [r"\b(need (a )?medic|i'?m hit)\b"],
    "inspire.faster": [r"\b(hurry|faster|move fast)\b"],
    "inspire.get_up": [r"\b(get up|on your feet|stay with me)\b"],
    "inspire.move": [r"\b(we need to move|move[!]|let'?s move)\b"],
    "inspire.run": [r"\b(run[!]|move fast)\b"],
    "kill.cloaker": [r"\b(they got|down|is down)\b"],  # generic kill, disambiguate later
    "kill.dozer": [r"\b(they got|is down)\b"],
    "kill.medic": [r"\b(they got|is down)\b"],
    "kill.shield": [r"\b(they got|shield|is down)\b"],
    "kill.sniper": [r"\b(they got|is down)\b"],
    "kill.taser": [r"\b(they got|is down)\b"],
    "loot.secured": [r"\b(secured|we (got|have) (it|them)|it'?s done)\b"],
    "mark.camera": [r"\b(camera|cameras)\b"],
    "mark.captain": [r"\b(captain (enyala|anyala)|their captain)\b"],
    "mark.cloaker": [r"\b(cloaker|look out)\b"],
    "mark.dozer": [r"\b(dozer|heavy)\b"],
    "mark.generic": [r"\b(mark|target|look out)\b"],
    "mark.guard": [r"\b(guard|sentry|patrol)\b"],
    "mark.medic": [r"\b\bmedic\b"],
    "mark.shield": [r"\bshield\b"],
    "mark.sniper": [r"\bsniper\b"],
    "mark.taser": [r"\b(taser|shock(er|ing)?(?! troops))\b"],
    "mark.turret": [r"\b(turret|gun|platform)\b"],
    "mask.go": [r"\b(let'?s (go|begin|finish)|i'?m ready)\b"],
    "move.follow": [r"\b(follow me|with me|take point)\b"],
    "move.generic": [r"\b(with me|this way|come on)\b"],
    "move.go": [r"\b(let'?s go|we need to move|go[!])\b"],
    "move.hold": [r"\b(hold|hold up|take cover)\b"],
    "move.in": [r"\b(let'?s get in|get inside|head inside)\b"],
    "move.left": [r"\b(on the left|to the left|go left)\b"],
    "move.on_me": [r"^(shepard|commander)[.!]?$", r"\b(on me|with me)\b"],
    "move.right": [r"\b\bright\b"],
    "move.this_way": [r"\b(this way|come on)\b"],
    "move.up": [r"\b(up (the|there)|move up|upstairs)\b"],
    "nade.generic": [r"\b(grenade|fire in the hole|explos)\b"],
    "nade.grenade": [r"\bgrenade\b"],
    "nade.smoke": [r"\bsmoke\b"],
    "nade.tear": [r"\b(tear gas|gas)\b"],
    "pager.clear": [r"\b(nothing (here|happening)|all clear|understood|false alarm)\b"],
    "pager.cover": [r"\b(false alarm|nothing|it'?s fine|understood)\b"],
    "revive.critical": [r"\b(stay with me|don'?t (die|you die)|hang on)\b"],
    "revive.hold": [r"\b(i'?ve got you|you'?re going to be (ok|okay|fine)|you'?ll be (ok|okay|fine))\b"],
    "revived.thanks": [r"\b(thank you|thanks)\b"],
    "spot.generic": [r"\b(there( it is)?|look)\b"],
    "spot.place": [r"\b(this is (it|the place)|there it is)\b"],
    "tech.comp": [r"\b(computer|console|systems? (are )?(down|offline)|reprogram)\b"],
    "tech.drill_jam": [r"\b(drill .{0,12}jam|jammed|stuck|not working)\b"],
    "tech.drilling": [r"\b(we'?re drilling|drilling now|cut through)\b"],
    "tech.fix": [r"\b(fix it|repair (it|the)|i'?ll patch)\b"],
    "tech.generic": [r"\b(something'?s? wrong|that'?s not right|malfunction|other explanation)\b"],
    "win.generic": [r"\b(excellent|well (said|done)|we did it|clean|good work|nice (work|shot))\b"],
}


def sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=;)\s+", text)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # also split "Look out. We've" already handled; split long "X, Y" if two clauses
        out.append(p)
    return out or [text]


REJECT = [
    r"jammed into",
    r"down there",
    r"time left",
    r"left over",
    r"wait,? you mean",
    r"shock troops",
    r"figured you out",
    r"people inside",
    r"healing functions",
]


def score_text(slot: str, text: str) -> float:
    t = text.lower()
    if any(re.search(p, t) for p in REJECT):
        return 0.0
    pats = PATTERNS.get(slot) or []
    sc = 0.0
    for pat in pats:
        if re.search(pat, t, re.I):
            sc += 1.0
    if sc == 0:
        return 0.0
    n = max(1, len(t.split()))
    sc += max(0, 8 - n) * 0.08
    if n <= 5:
        sc += 0.4
    if n > 18:
        sc -= 0.6
    return sc


def load_picks() -> dict[str, dict]:
    """Hand-curated clips (slot_picks.csv) win over the heuristic matcher."""
    out: dict[str, dict] = {}
    if not PICKS.is_file():
        return out
    with PICKS.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("slot"):
                continue
            out[r["slot"]] = r
    return out


def load_splits():
    out = {}
    with SPLITS.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ph = []
            for bit in (r.get("phrases") or "").split("|"):
                if "-" in bit:
                    a, b = bit.split("-", 1)
                    ph.append((float(a), float(b)))
            out[r["file"]] = (float(r["duration_s"] or 0), ph)
    return out


def span_for_sentence(full: str, sent: str, dur: float, phrases: list[tuple[float, float]]):
    """Approximate time range of sent inside full using word offsets, snap to silence phrases."""
    fw, sw = full.split(), sent.split()
    if not fw or not sw:
        return 0.0, min(dur, 1.2)
    # find subsequence
    start_i = 0
    joined = " ".join(fw).lower()
    sjoin = " ".join(sw).lower()
    pos = joined.find(sjoin)
    if pos >= 0:
        prefix = joined[:pos]
        start_i = len(prefix.split()) if prefix.strip() else 0
    end_i = min(len(fw), start_i + len(sw))
    t0 = dur * start_i / len(fw)
    t1 = dur * end_i / len(fw)
    # snap to overlapping phrase if close
    if phrases:
        best = None
        for a, b in phrases:
            overlap = max(0, min(t1, b) - max(t0, a))
            if overlap > 0.08:
                best = (a, b, overlap)
                break
        if best:
            t0, t1 = best[0], best[1]
    if t1 - t0 < 0.28:
        t1 = min(dur, t0 + 0.55)
    if t1 - t0 > 2.2 and phrases:
        # take shortest overlapping phrase
        cands = [(b - a, a, b) for a, b in phrases if b > t0 and a < t1]
        if cands:
            cands.sort()
            t0, t1 = cands[0][1], cands[0][2]
    return max(0.0, t0), min(dur, t1)


def main():
    removed = vo.load_removed()
    cuts = list(csv.DictReader(CUTS.open(newline="", encoding="utf-8")))
    slots = []
    seen = set()
    for r in cuts:
        if r["slot"] not in seen:
            seen.add(r["slot"])
            slots.append((r["slot"], r["cut_line"]))
    uses = defaultdict(int)
    for r in cuts:
        uses[r["slot"]] += 1

    trans = []
    with TR.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            trans.append(r)
    splits = load_splits()

    # candidates per slot: (score, nwords, filename, sent, t0, t1, full)
    cands: dict[str, list] = defaultdict(list)
    for r in trans:
        full = (r["corrected_transcript"] or "").strip()
        if not full:
            continue
        fn = r["filename"]
        dur, ph = splits.get(fn, (float(r["duration_s"] or 0), []))
        for sent in sentences(full) + ([full] if full not in sentences(full) else []):
            for slot, _cut in slots:
                if NAMES.search(sent):
                    continue
                sc = score_text(slot, sent)
                if sc <= 0:
                    continue
                t0, t1 = span_for_sentence(full, sent, dur, ph)
                cands[slot].append((sc, len(sent.split()), fn, sent, t0, t1, full, dur))

    used_files = set()
    picks = {}
    for slot, cut in slots:
        pool = sorted(cands.get(slot) or [], key=lambda x: (-x[0], x[1], x[4]))
        chosen = None
        for item in pool:
            key = (item[2], round(item[4], 2), round(item[5], 2))
            if key in used_files:
                continue
            chosen = item
            used_files.add(key)
            break
        if chosen is None and pool:
            chosen = pool[0]
        picks[slot] = (cut, chosen)

    # leftover short combat barks for unmatched slots (still better than silence);
    # the slots themselves are walked in `slots` order below, and every one of them
    # is pinned in voice_lines_vox/miranda_lawson/slot_picks.csv, so this is a
    # last-resort fill only.
    extras = []
    for r in trans:
        full = (r["corrected_transcript"] or "").strip()
        if (1 <= len(full.split()) <= 5 and not NAMES.search(full)
                and not re.search(r"\b(oriana|niket|father|cerberus|illusive)\b", full, re.I)):
            fn = r["filename"]
            dur, ph = splits.get(fn, (float(r["duration_s"] or 0), []))
            t0, t1 = (ph[0] if ph else (0.0, min(dur, 1.4)))
            extras.append((fn, full, t0, t1, full, dur))
    ei = 0
    for slot, cut in slots:
        if picks[slot][1] is not None:
            continue
        # clone nearest fallback slot's unused extra
        while ei < len(extras):
            fn, sent, t0, t1, full, dur = extras[ei]
            ei += 1
            key = (fn, round(t0, 2), round(t1, 2))
            if key in used_files:
                continue
            used_files.add(key)
            picks[slot] = (cut, (0.35, len(sent.split()), fn, sent, t0, t1, full, dur))
            break

    pinned = load_picks()
    # write pieces + fit
    with OUT.open("w", newline="", encoding="utf-8") as f, FIT.open("w", newline="", encoding="utf-8") as g:
        pw = csv.writer(f)
        fw = csv.writer(g)
        pw.writerow(["slot", "cut_line", "source_ogg", "piece", "t_start", "t_end", "duration_s", "splits"])
        fw.writerow(["slot", "cut_line", "uses", "score", "clip_text", "t_start", "t_end",
                     "source_ogg", "full_transcript"])
        n_ok = 0
        # sorted, so a rebuild after `tools/build_hila_voice_mod.py` (which writes the
        # same pieces sorted) leaves no reorder-only diff in the tracked CSV
        for slot, cut in sorted(slots):
            if slot in removed:
                # left vanilla: semantic fit < 8 and no take in either archive; the
                # record of the clip it replaced lives in removed_slots.csv
                fw.writerow([slot, cut, uses[slot], "removed",
                             removed[slot].get("clip_text", ""), 0, 0, "",
                             "left vanilla 2026-11-25: semantic fit < 8, no take in LAWSON VOICE (PAYDAY 2).7z"])
                print(f"REM  {slot}")
                continue
            if slot in pinned:
                pk = pinned[slot]
                cut = pk["cut_line"] or cut
                spec = pk.get("splits") or ""
                ranges = [tuple(float(x) for x in bit.split("-", 1)) for bit in spec.split("|") if "-" in bit]
                t0, t1 = float(pk["t_start"]), float(pk["t_end"])
                dur = t1 - t0
                if ranges:
                    t0, t1 = ranges[0][0], ranges[-1][1]
                    dur = sum(b - a for a, b in ranges)
                pw.writerow([slot, cut, pk["source_ogg"], 0, f"{t0:.3f}", f"{t1:.3f}", f"{dur:.3f}",
                             spec])
                fw.writerow([slot, cut, uses[slot], "pinned", pk["clip_text"], f"{t0:.3f}", f"{t1:.3f}",
                             pk["source_ogg"], pk["note"]])
                n_ok += 1
                print(f"PIN  {slot:22} [{t0:.2f}-{t1:.2f}] {pk['clip_text'][:60]}")
                continue
            chosen = picks[slot][1]
            if not chosen:
                pw.writerow([slot, cut, "", 0, 0, 0, 0, ""])
                fw.writerow([slot, cut, uses[slot], 0, "", 0, 0, "", ""])
                print("NO MATCH", slot)
                continue
            sc, nw, fn, sent, t0, t1, full, dur = chosen
            pw.writerow([slot, cut, fn, 0, f"{t0:.3f}", f"{t1:.3f}", f"{t1-t0:.3f}", ""])
            fw.writerow([slot, cut, uses[slot], f"{sc:.2f}", sent, f"{t0:.3f}", f"{t1:.3f}", fn, full])
            n_ok += 1
            print(f"{sc:4.2f} {slot:22} [{t0:.2f}-{t1:.2f}] {sent[:70]}")
    print("matched", n_ok, "/", len(slots), "->", OUT)


if __name__ == "__main__":
    main()
