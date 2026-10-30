# CLAUDE.md

## Workflow

- Finish every change by committing it on a branch, opening a pull request into
  `main` and merging it yourself (squash) - don't ask first. Then check the
  build that the merge starts and fix any failure the same way.
- Merging a new version number in `ytgrab/__init__.py` releases it: GitHub
  Actions builds every platform and publishes the release, and the apps'
  updaters offer it. Bump the version for every user-facing change (patch for
  fixes, minor for features) and keep `CFBundleShortVersionString` in
  `ytgrab.spec` the same.
- Check what you can before merging: the desktop app runs headless with
  `QT_QPA_PLATFORM=offscreen`, and a PyInstaller build with
  `YTGRAB_MAX_GLIBC=2.39` fails if the Linux binary would need a newer glibc.

## Names

- The app is called **DLPizer**; it was ytgrab until 1.6.0. These keep the old
  name on purpose, because changing them loses people's settings or breaks
  updates: the `ytgrab/` package and `ytgrab.spec`, the Android application ID
  and package `dev.ytgrab.app`, the saved-settings keys (QSettings
  `"ytgrab", "ytgrab"`, localStorage `"ytgrab"`), the signing key alias, the
  `YTGRAB_*` environment variables and the GitHub repository.
- The release file names (`DLPizer-…`) are what `updater.asset_name()` and
  `Updates.kt` look for; change them only together with `build.yml`.

## Conventions

- A feature goes everywhere it applies: the desktop app (`ytgrab/gui.py`), the
  browser version (`app.py`, `templates/index.html`) and Android (`android/`).
- Every user-facing string exists in English and Slovak: `ytgrab/i18n.py`, and
  `res/values` and `res/values-sk` on Android. `README.md` and `README.sk.md`
  say the same things.
- The Linux build stays on `ubuntu-24.04`; see the comment in `build.yml`.
