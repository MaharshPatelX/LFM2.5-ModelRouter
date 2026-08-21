# Scripts

Scripts remain thin command wrappers around reusable package code. Planned
commands include canonical table construction, offline training, profile
creation, static evaluation, and churn simulation.

`download_xroutebench.py` downloads and verifies the smallest pinned
xRouteBench sample by default. Pass `--all` to download all manifest files.
Real data is written only under ignored `data/raw/` storage.
