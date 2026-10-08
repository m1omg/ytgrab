"""PySide6 desktop interface for ytgrab."""

import sys
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QPoint, QLocale, QSettings
from PySide6.QtGui import (
    QPixmap, QDesktopServices, QIcon, QPainter, QColor, QPolygon,
    QAction, QActionGroup,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QProgressBar,
    QRadioButton, QButtonGroup, QStackedWidget, QFileDialog, QFrame,
    QGroupBox, QMessageBox,
)

from . import core, i18n, __version__
from .i18n import t


# yt-dlp reports postprocessor names with the "FFmpeg" prefix stripped.
KNOWN_STAGES = ("ExtractAudio", "Merger", "VideoRemuxer", "VideoConvertor",
                "EmbedThumbnail", "Metadata", "MoveFiles", "SubtitlesConvertor")


def stage_key(name):
    """Translation key for a postprocessor, so the label follows the language."""
    return f"stage_{name}" if name in KNOWN_STAGES else "stage_processing"


class Cancelled(Exception):
    """Raised inside a yt-dlp hook to abort a download."""


# --------------------------------------------------------------------------
# workers
# --------------------------------------------------------------------------

class InfoWorker(QThread):
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, url, cookies_browser=None):
        super().__init__()
        self.url = url
        self.cookies_browser = cookies_browser

    def run(self):
        try:
            self.finished_ok.emit(core.fetch_info(self.url, self.cookies_browser))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(core.clean_error(exc, login=self.cookies_browser))


class ThumbWorker(QThread):
    loaded = Signal(bytes)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent": "ytgrab"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                self.loaded.emit(resp.read())
        except Exception:  # noqa: BLE001 - a missing thumbnail is not an error
            pass


class DownloadWorker(QThread):
    progress = Signal(dict)
    stage = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, url, dest, mode, quality, container, embed, cookies_browser=None):
        super().__init__()
        self.url, self.dest = url, dest
        self.mode, self.quality = mode, quality
        self.container, self.embed = container, embed
        self.cookies_browser = cookies_browser
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _on_progress(self, d):
        if self._cancel:
            raise Cancelled()
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            self.progress.emit({
                "percent": (done / total * 100) if total else 0,
                "downloaded": done,
                "total": total,
                "speed": d.get("speed") or 0,
                "eta": d.get("eta") or 0,
            })
        elif d.get("status") == "finished":
            self.stage.emit("stage_processing")

    def _on_postprocess(self, d):
        if self._cancel:
            raise Cancelled()
        if d.get("status") == "started":
            # The key travels, not the text, so a language switch mid-download
            # relabels the stage that is already showing.
            self.stage.emit(stage_key(d.get("postprocessor") or ""))

    def run(self):
        try:
            path = core.download(
                self.url, self.dest, self.mode, self.quality,
                self.container, self.embed,
                progress_hook=self._on_progress,
                postprocessor_hook=self._on_postprocess,
                cookies_browser=self.cookies_browser,
            )
            self.finished_ok.emit(str(path))
        except Cancelled:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            if self._cancel:
                self.cancelled.emit()
            else:
                self.failed.emit(core.clean_error(exc, login=self.cookies_browser))


# --------------------------------------------------------------------------
# main window
# --------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ytgrab {__version__}")
        self.setMinimumWidth(620)
        self.dest_dir = core.default_download_dir()
        self.info_worker = None
        self.thumb_worker = None
        self.dl_worker = None
        self.last_file = None
        self.info = None          # last metadata read, for relabelling
        self.transcripts = []     # subtitle tracks offered by the last read
        self.fetching = False
        # Browser to borrow the YouTube login from, or None for no login.
        saved = QSettings("ytgrab", "ytgrab").value("cookies_browser")
        self.cookies_browser = saved if saved in core.COOKIE_BROWSERS else None
        # The two progress labels re-render themselves on a language switch,
        # so each one keeps the callable that produced its current text.
        self._state_text = None
        self._stats_text = None

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self._build_menu()
        layout.addWidget(self._build_url_row())
        layout.addWidget(self._build_info_panel())
        layout.addWidget(self._build_mode_box())
        layout.addWidget(self._build_options())
        layout.addWidget(self._build_dest_row())
        layout.addWidget(self._build_actions())
        layout.addWidget(self._build_progress())
        layout.addStretch(1)

        self.retranslate()
        self._sync_mode()

    # -- construction ------------------------------------------------------

    def _build_menu(self):
        self.lang_menu = self.menuBar().addMenu("")
        group = QActionGroup(self)
        group.setExclusive(True)
        self.lang_actions = {}
        for code in i18n.languages():
            action = QAction(i18n.language_name(code), self)
            action.setCheckable(True)
            action.setChecked(code == i18n.language())
            action.triggered.connect(lambda _checked=False, c=code: self.set_language(c))
            group.addAction(action)
            self.lang_menu.addAction(action)
            self.lang_actions[code] = action

        self.options_menu = self.menuBar().addMenu("")
        self.login_menu = self.options_menu.addMenu("")
        login_group = QActionGroup(self)
        login_group.setExclusive(True)
        self.login_actions = {}
        for key, name in [(None, "")] + list(core.COOKIE_BROWSERS.items()):
            action = QAction(name, self)  # "Off" is labelled in retranslate()
            action.setCheckable(True)
            action.setChecked(key == self.cookies_browser)
            action.triggered.connect(lambda _checked=False, k=key: self.set_login(k))
            login_group.addAction(action)
            self.login_menu.addAction(action)
            self.login_actions[key] = action

    def _build_url_row(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)

        self.link_label = QLabel()
        self.url_edit = QLineEdit()
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.returnPressed.connect(self.fetch_info)
        self.url_edit.textChanged.connect(self._on_url_changed)

        self.fetch_btn = QPushButton()
        self.fetch_btn.clicked.connect(self.fetch_info)

        self.paste_btn = QPushButton()
        self.paste_btn.clicked.connect(self.paste_and_fetch)

        row.addWidget(self.link_label)
        row.addWidget(self.url_edit, 1)
        row.addWidget(self.paste_btn)
        row.addWidget(self.fetch_btn)
        return box

    def _build_info_panel(self):
        self.info_panel = QFrame()
        self.info_panel.setFrameShape(QFrame.StyledPanel)
        self.info_panel.setVisible(False)
        row = QHBoxLayout(self.info_panel)

        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(160, 90)
        self.thumb_label.setScaledContents(True)
        self.thumb_label.setAlignment(Qt.AlignCenter)

        text_col = QVBoxLayout()
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        self.meta_label = QLabel()
        self.meta_label.setStyleSheet("color: palette(mid);")
        text_col.addWidget(self.title_label)
        text_col.addWidget(self.meta_label)
        text_col.addStretch(1)

        row.addWidget(self.thumb_label)
        row.addLayout(text_col, 1)
        return self.info_panel

    def _build_mode_box(self):
        self.mode_box = QGroupBox()
        row = QHBoxLayout(self.mode_box)
        self.mode_group = QButtonGroup(self)

        self.mode_buttons = {}
        for i, key in enumerate(("video", "audio", "mp3", "transcript")):
            btn = QRadioButton()
            btn.setChecked(key == "video")
            self.mode_group.addButton(btn, i)
            self.mode_buttons[key] = btn
            btn.toggled.connect(self._sync_mode)
            row.addWidget(btn)
        return self.mode_box

    def _build_options(self):
        self.opt_stack = QStackedWidget()

        # video
        video = QWidget()
        g = QGridLayout(video)
        g.setContentsMargins(0, 0, 0, 0)
        self.res_combo = QComboBox()
        self.res_combo.addItem("", "best")
        self.container_combo = QComboBox()
        self.container_combo.addItem("", "mp4")
        self.container_combo.addItem("", "mkv")
        self.res_label = QLabel()
        self.container_label = QLabel()
        g.addWidget(self.res_label, 0, 0)
        g.addWidget(self.res_combo, 0, 1)
        g.addWidget(self.container_label, 1, 0)
        g.addWidget(self.container_combo, 1, 1)
        g.setColumnStretch(1, 1)
        self.opt_stack.addWidget(video)

        # audio
        audio = QWidget()
        g = QGridLayout(audio)
        g.setContentsMargins(0, 0, 0, 0)
        self.acodec_combo = QComboBox()
        for value in ("best", "opus", "m4a"):
            self.acodec_combo.addItem("", value)
        self.stream_label = QLabel()
        g.addWidget(self.stream_label, 0, 0)
        g.addWidget(self.acodec_combo, 0, 1)
        g.setColumnStretch(1, 1)
        self.opt_stack.addWidget(audio)

        # mp3
        mp3 = QWidget()
        g = QGridLayout(mp3)
        g.setContentsMargins(0, 0, 0, 0)
        self.bitrate_combo = QComboBox()
        for value in ("0", "320", "256", "192", "128"):
            self.bitrate_combo.addItem("", value)
        self.bitrate_combo.setCurrentIndex(3)
        self.bitrate_label = QLabel()
        g.addWidget(self.bitrate_label, 0, 0)
        g.addWidget(self.bitrate_combo, 0, 1)
        g.setColumnStretch(1, 1)
        self.opt_stack.addWidget(mp3)

        # transcript
        transcript = QWidget()
        g = QGridLayout(transcript)
        g.setContentsMargins(0, 0, 0, 0)
        self.tlang_combo = QComboBox()
        self.tfmt_combo = QComboBox()
        for value in ("txt", "srt", "vtt"):
            self.tfmt_combo.addItem("", value)
        self.tlang_label = QLabel()
        self.tfmt_label = QLabel()
        g.addWidget(self.tlang_label, 0, 0)
        g.addWidget(self.tlang_combo, 0, 1)
        g.addWidget(self.tfmt_label, 1, 0)
        g.addWidget(self.tfmt_combo, 1, 1)
        g.setColumnStretch(1, 1)
        self.opt_stack.addWidget(transcript)

        wrapper = QWidget()
        col = QVBoxLayout(wrapper)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.opt_stack)
        self.embed_check = QCheckBox()
        self.embed_check.setChecked(True)
        col.addWidget(self.embed_check)
        return wrapper

    def _build_dest_row(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        self.dest_edit = QLineEdit(str(self.dest_dir))
        self.dest_edit.setReadOnly(True)
        self.dest_label = QLabel()
        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self.choose_dest)
        row.addWidget(self.dest_label)
        row.addWidget(self.dest_edit, 1)
        row.addWidget(self.browse_btn)
        return box

    def _build_actions(self):
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        self.download_btn = QPushButton()
        self.download_btn.setMinimumHeight(38)
        self.download_btn.setDefault(True)
        self.download_btn.clicked.connect(self.start_download)
        self.cancel_btn = QPushButton()
        self.cancel_btn.setMinimumHeight(38)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_download)
        row.addWidget(self.download_btn, 1)
        row.addWidget(self.cancel_btn)
        return box

    def _build_progress(self):
        self.progress_panel = QWidget()
        col = QVBoxLayout(self.progress_panel)
        col.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.state_label = QLabel("")
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: palette(mid);")
        self.stats_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self.state_label)
        top.addStretch(1)
        top.addWidget(self.stats_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(10)

        self.open_btn = QPushButton()
        self.open_btn.setVisible(False)
        self.open_btn.clicked.connect(self.open_dest)

        col.addLayout(top)
        col.addWidget(self.progress_bar)
        col.addWidget(self.open_btn)
        self.progress_panel.setVisible(False)
        return self.progress_panel

    # -- language ----------------------------------------------------------

    def set_language(self, code):
        if code == i18n.language():
            return
        i18n.set_language(code)
        QSettings("ytgrab", "ytgrab").setValue("language", code)
        self.retranslate()

    def set_login(self, browser):
        if browser == self.cookies_browser:
            return
        self.cookies_browser = browser
        settings = QSettings("ytgrab", "ytgrab")
        settings.setValue("cookies_browser", browser or "")
        # Explain once what borrowing a login means, the first time it is used.
        if browser and not settings.value("login_note_shown", False, type=bool):
            settings.setValue("login_note_shown", True)
            QMessageBox.information(
                self, t("login_note_title"),
                t("login_note_body", browser=core.COOKIE_BROWSERS[browser]))

    @staticmethod
    def _relabel(combo, labels):
        """Retitle combo items in place, keeping the current selection."""
        for index, text in enumerate(labels):
            combo.setItemText(index, text)

    def _default_transcript_index(self):
        """Prefer the interface language, then English, then whatever is first."""
        codes = [entry["code"] for entry in self.transcripts]
        for wanted in (i18n.language(), "en"):
            for index, code in enumerate(codes):
                if code == wanted or code.split("-")[0] == wanted:
                    return index
        return 0

    def _fill_transcript_langs(self):
        """Rebuild the language list, keeping the current choice if it survives."""
        previous = self.tlang_combo.currentData()
        self.tlang_combo.clear()
        for entry in self.transcripts:
            label = (t("transcript_auto", code=entry["code"]) if entry["auto"]
                     else entry["code"])
            self.tlang_combo.addItem(label, entry["code"])
        if not self.transcripts:
            self.tlang_combo.addItem(t("transcript_none"), "")
            return
        found = self.tlang_combo.findData(previous)
        self.tlang_combo.setCurrentIndex(
            found if found >= 0 else self._default_transcript_index())

    def retranslate(self):
        """Apply the active language to every widget that shows text."""
        self.lang_menu.setTitle(t("menu_language"))
        for code, action in self.lang_actions.items():
            action.setChecked(code == i18n.language())
        self.options_menu.setTitle(t("menu_options"))
        self.login_menu.setTitle(t("login_menu"))
        self.login_actions[None].setText(t("login_off"))

        self.link_label.setText(t("link"))
        self.url_edit.setPlaceholderText(t("url_placeholder"))
        self.fetch_btn.setText(t("fetching") if self.fetching else t("fetch"))
        self.paste_btn.setText(t("paste"))
        self.paste_btn.setToolTip(t("paste_tip"))

        self.mode_box.setTitle(t("mode_title"))
        for key, btn in self.mode_buttons.items():
            btn.setText(t(f"mode_{key}"))
            btn.setToolTip(t(f"mode_{key}_tip"))

        self.res_label.setText(t("resolution"))
        self.container_label.setText(t("container"))
        self.stream_label.setText(t("stream"))
        self.bitrate_label.setText(t("bitrate"))
        # Only the first resolution entry is a word; the rest are "1080p".
        self.res_combo.setItemText(0, t("best_available"))
        self._relabel(self.container_combo, [t("container_mp4"), t("container_mkv")])
        self.container_combo.setToolTip(t("container_tip"))
        self._relabel(self.acodec_combo,
                      [t("audio_best"), t("audio_opus"), t("audio_m4a")])
        self._relabel(self.bitrate_combo,
                      [t("bitrate_v0")] + [t("bitrate_cbr", kbps=k)
                                           for k in ("320", "256", "192", "128")])
        self.embed_check.setText(t("embed"))

        self.tlang_label.setText(t("transcript_lang"))
        self.tfmt_label.setText(t("transcript_format"))
        self._relabel(self.tfmt_combo,
                      [t("transcript_txt"), t("transcript_srt"), t("transcript_vtt")])
        # "(automatic)" is translated, so the list is rebuilt, not just relabelled.
        self._fill_transcript_langs()

        self.dest_label.setText(t("save_to"))
        self.browse_btn.setText(t("change"))
        self.download_btn.setText(t("download"))
        self.cancel_btn.setText(t("cancel"))
        self.open_btn.setText(t("show_in_folder"))

        if self.info:
            self._show_meta(self.info)
        if self._state_text:
            self.state_label.setText(self._state_text())
        if self._stats_text:
            self.stats_label.setText(self._stats_text())
        self.statusBar().showMessage(self._ffmpeg_status())

    # -- behaviour ---------------------------------------------------------

    def _set_state(self, render):
        """Show progress text, remembering how to redraw it in another language."""
        self._state_text = render
        self.state_label.setText(render())

    def _set_stats(self, render):
        self._stats_text = render
        self.stats_label.setText(render())

    def _ffmpeg_status(self):
        loc = core.ffmpeg_location()
        return t("ffmpeg_at", path=loc) if loc else t("ffmpeg_status_missing")

    def current_mode(self):
        for key, btn in self.mode_buttons.items():
            if btn.isChecked():
                return key
        return "video"

    def _sync_mode(self):
        mode = self.current_mode()
        self.opt_stack.setCurrentIndex(
            {"video": 0, "audio": 1, "mp3": 2, "transcript": 3}[mode])
        self.embed_check.setVisible(mode in ("audio", "mp3"))

    def _on_url_changed(self):
        # A new link invalidates whatever metadata is on screen.
        if self.info_panel.isVisible():
            self.info_panel.setVisible(False)
            self.info = None
            self.res_combo.clear()
            self.res_combo.addItem(t("best_available"), "best")
            self.transcripts = []
            self._fill_transcript_langs()

    def paste_and_fetch(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.url_edit.setText(text)
            self.fetch_info()

    def fetch_info(self):
        url = self.url_edit.text().strip()
        if not core.is_supported_url(url):
            self.statusBar().showMessage(t("invalid_link"), 5000)
            return
        if self.info_worker and self.info_worker.isRunning():
            return

        self.fetching = True
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText(t("fetching"))
        self.statusBar().showMessage(t("reading_details"))

        self.info_worker = InfoWorker(url, self.cookies_browser)
        self.info_worker.finished_ok.connect(self._on_info)
        self.info_worker.failed.connect(self._on_info_failed)
        self.info_worker.finished.connect(self._reset_fetch_btn)
        self.info_worker.start()

    def _reset_fetch_btn(self):
        self.fetching = False
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText(t("fetch"))

    def _show_meta(self, info):
        self.title_label.setText(info["title"])
        bits = [b for b in (info["uploader"],
                            core.format_duration(info["duration"]),
                            t("live") if info["is_live"] else "") if b]
        self.meta_label.setText("  ·  ".join(bits))

    def _on_info(self, info):
        self.info = info
        self._show_meta(info)

        self.res_combo.clear()
        self.res_combo.addItem(t("best_available"), "best")
        for h in info["heights"]:
            self.res_combo.addItem(f"{h}p", str(h))

        self.transcripts = info.get("transcripts") or []
        self._fill_transcript_langs()

        self.thumb_label.clear()
        if info["thumbnail"]:
            self.thumb_worker = ThumbWorker(info["thumbnail"])
            self.thumb_worker.loaded.connect(self._on_thumb)
            self.thumb_worker.start()

        self.info_panel.setVisible(True)
        self.statusBar().showMessage(t("ready"), 4000)

    def _on_thumb(self, data):
        pix = QPixmap()
        if pix.loadFromData(data):
            self.thumb_label.setPixmap(pix)

    def _on_info_failed(self, message):
        self.info = None
        self.info_panel.setVisible(False)
        self.statusBar().showMessage(t("read_failed"), 6000)
        QMessageBox.warning(self, t("read_failed_title"), message)

    def choose_dest(self):
        chosen = QFileDialog.getExistingDirectory(self, t("choose_dir"), str(self.dest_dir))
        if chosen:
            self.dest_dir = Path(chosen)
            self.dest_edit.setText(chosen)

    def open_dest(self):
        target = self.last_file.parent if self.last_file else self.dest_dir
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def start_download(self):
        url = self.url_edit.text().strip()
        if not core.is_supported_url(url):
            QMessageBox.warning(self, t("no_link_title"), t("no_link_body"))
            return
        mode = self.current_mode()
        container = (self.tfmt_combo.currentData() if mode == "transcript"
                     else self.container_combo.currentData())
        quality = {
            "video": lambda: self.res_combo.currentData(),
            "audio": lambda: self.acodec_combo.currentData(),
            "mp3": lambda: self.bitrate_combo.currentData(),
            "transcript": lambda: self.tlang_combo.currentData(),
        }[mode]()

        if mode == "transcript" and not quality:
            QMessageBox.warning(self, t("download_failed_title"), t("transcript_none"))
            return

        # txt is parsed here and vtt is served as-is, so neither needs ffmpeg.
        if (mode != "transcript" or container == "srt") and not core.ffmpeg_location():
            QMessageBox.critical(self, t("ffmpeg_missing_title"), t("ffmpeg_missing_body"))
            return

        self.download_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.progress_panel.setVisible(True)
        self.open_btn.setVisible(False)
        self.progress_bar.setRange(0, 0)  # indeterminate until bytes arrive
        self._set_state(lambda: t("starting"))
        self._set_stats(lambda: "")

        self.dl_worker = DownloadWorker(
            url, self.dest_dir, mode, quality,
            container, self.embed_check.isChecked(),
            self.cookies_browser,
        )
        self.dl_worker.progress.connect(self._on_progress)
        self.dl_worker.stage.connect(self._on_stage)
        self.dl_worker.finished_ok.connect(self._on_done)
        self.dl_worker.failed.connect(self._on_failed)
        self.dl_worker.cancelled.connect(self._on_cancelled)
        self.dl_worker.start()

    def cancel_download(self):
        if self.dl_worker and self.dl_worker.isRunning():
            self.cancel_btn.setEnabled(False)
            self._set_state(lambda: t("cancelling"))
            self.dl_worker.cancel()

    def _on_progress(self, p):
        if p["total"]:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(p["percent"]))
            self._set_state(lambda: t("downloading_percent",
                                      percent=i18n.number(p["percent"])))
        else:
            self.progress_bar.setRange(0, 0)
            self._set_state(lambda: t("downloading"))

        def stats():
            bits = []
            if p["total"]:
                bits.append(f"{core.format_size(p['downloaded'])} / {core.format_size(p['total'])}")
            if p["speed"]:
                bits.append(f"{core.format_size(p['speed'])}/s")
            if p["eta"]:
                bits.append(t("eta_left", time=core.format_duration(p["eta"])))
            return "   ·   ".join(bits)

        self._set_stats(stats)

    def _on_stage(self, key):
        self.progress_bar.setRange(0, 0)
        self._set_state(lambda: t(key) + "…")
        self._set_stats(lambda: "")

    def _finish_ui(self):
        self.download_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)

    def _on_done(self, path):
        self.last_file = Path(path)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._set_state(lambda: t("saved"))
        size = self.last_file.stat().st_size if self.last_file.exists() else 0
        self._set_stats(lambda: f"{self.last_file.name}   ·   {core.format_size(size)}")
        self.open_btn.setVisible(True)
        self.statusBar().showMessage(t("saved_to", path=self.last_file), 8000)
        self._finish_ui()

    def _on_failed(self, message):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_state(lambda: t("failed"))
        self._set_stats(lambda: "")
        self._finish_ui()
        QMessageBox.critical(self, t("download_failed_title"), message)

    def _on_cancelled(self):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_state(lambda: t("cancelled"))
        self._set_stats(lambda: "")
        self._finish_ui()

    def closeEvent(self, event):
        if self.dl_worker and self.dl_worker.isRunning():
            self.dl_worker.cancel()
            self.dl_worker.wait(3000)
        event.accept()


def make_icon():
    """A small red-on-transparent play badge, so there is no binary asset to ship."""
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#ff4b4b"))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 12, 56, 40, 10, 10)
    p.setBrush(QColor("#ffffff"))
    p.drawPolygon(QPolygon([QPoint(26, 20), QPoint(26, 44), QPoint(44, 32)]))
    p.end()
    return QIcon(pix)


def startup_language():
    """A remembered choice wins; otherwise follow the system, then English."""
    saved = i18n.normalise(QSettings("ytgrab", "ytgrab").value("language"))
    # QLocale knows the UI language on macOS, where the env vars are unset.
    return saved or i18n.normalise(QLocale.system().name()) or i18n.detect_language()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ytgrab")
    app.setApplicationDisplayName("ytgrab")
    app.setWindowIcon(make_icon())
    i18n.set_language(startup_language())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
