# The tracked packs and the CPU that builds them

Date: 2026-11-12. This page is written in the order the work was done. Its first section was committed before
the check it describes had run anywhere.

## Where this starts

One commit, `5477da7`, was built by two GitHub runners on 2026-11-12. On an AMD EPYC 9V74 (AVX-512) both
Miranda packs came out with all 20 members the same bytes as the tracked ones. On an AMD EPYC 7763 (AVX2, no
AVX-512) the third-person model of each differed in 136 bytes. CI was green both times, because the
comparison (`fresh_check.py`) allowed a model to differ in that way. The other twelve packs have never been
built on a machine that is not an Arena sandbox.

## What the strict check is expected to report (written before its first run)

`tools/pd2-las/fresh.py check` builds all 14 packs in a copy of the checkout and compares each of the 16
tracked zips with its tracked `.sha256` using `sha256sum -c`, with no tolerance. Nothing has been fixed yet.
The expectation comes from the sandbox runs of 2026-11-11, in which numpy and OpenBLAS were held to the code
paths of other CPUs.

- **On a runner with AVX-512** (the EPYC 9V74 kind): all 16 zips are the tracked bytes.
- **On a runner without AVX-512** (the EPYC 7763 kind): 14 of the 16 zips differ. They are `Miranda_LAS` and
  `Miranda_Busty_LAS` (both copies of each), `Christie_LAS`, `Christie_LAS_Slim`, the four
  `Miranda_L4D2_over_*` and the four `Miranda_Romance_over_*`. `lawson_las` and `Geralt_over_Rust` are the
  tracked bytes. A Miranda model differs in 136 bytes, a head atlas in 8 or 9.
- **What would make this wrong:** a difference between the sandbox and a runner that is not the CPU's
  instruction set. A runner has four threads where the sandbox has two, and its own C library; the Christie
  and head builders have met neither.
