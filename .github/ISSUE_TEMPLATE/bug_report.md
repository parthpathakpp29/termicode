---
name: Bug report
about: Something didn't work the way it should
title: ""
labels: bug
---

**What did you run?**
The exact command or slash command (e.g. `/model budget`, or the prompt you sent).

**What did you expect to happen?**

**What actually happened?**
Paste the real output, not a paraphrase. If TermiCode showed an error message or panel, include the whole thing.

**Environment**
- OS: (Windows / macOS / Linux, and version)
- Python version: (`python --version`)
- TermiCode version: (`pip show termicode`, or the commit if installed from source)
- Repowise installed? (yes/no — relevant if this involves `/heal`, `/report`, or `/guard`)

TermiCode's sandbox boundary and the `/guard` git hook both have OS-specific code paths (symlink/junction resolution, POSIX permission bits), so the platform often matters here.

**Anything else?**
Anything you tried that didn't fix it, or anything unusual about your setup.
