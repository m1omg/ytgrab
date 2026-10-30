"""PySide6 desktop interface for ytgrab."""

import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QObject, QThread, QTimer, Signal, QUrl, QPoint, QLocale, QSettings
from PySide6.QtGui import (
    QPixmap, QImage, QDesktopServices, QIcon, QPainter, QColor, QPolygon,
    QAction, QActionGroup, QPalette,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QProgressBar,
    QRadioButton, QButtonGroup, QStackedWidget, QFileDialog, QFrame,
    QGroupBox, QMessageBox, QProgressDialog, QScrollArea, QSizePolicy,
)

from . import core, i18n, jobs, updater, __version__
from .i18n import t, tn

ERROR_STYLE = "color: #e53935;"


def muted_style():
    """Style for secondary text: the theme's text colour, faded toward its background.

    palette(mid) all but vanishes on some light themes; this keeps about 5:1
    contrast on light and dark ones alike.
    """
    palette = QApplication.palette()
    text = palette.color(QPalette.WindowText)
    back = palette.color(QPalette.Window)
    mix = [round(a * 0.7 + b * 0.3) for a, b in
           zip(text.getRgb()[:3], back.getRgb()[:3])]
    return "color: #%02x%02x%02x;" % tuple(mix)


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


class ThumbLoader(QObject):
    """Loads a thumbnail on a plain daemon thread, which closing the window
    never has to wait for. The token says which read it belongs to."""

    loaded = Signal(int, bytes)

    def __init__(self, token, urls):
        super().__init__()
        self.token, self.urls = token, urls

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        # Only an image Qt can draw counts; otherwise the next one is tried.
        data = core.fetch_image(self.urls, accept=lambda d: not QImage.fromData(d).isNull())
        if data:
            self.loaded.emit(self.token, data)


class QueueBridge(QObject):
    """Carries the queue's news from its thread to the window's."""

    changed = Signal(object)  # a Job, or None when the list itself changed


class UpdateBridge(QObject):
    """Carries an update's news from its thread to the window's."""

    checked = Signal(object, bool)      # the newer Release or None; asked for by hand
    check_failed = Signal(str, bool)
    progress = Signal(object, object)   # bytes so far, bytes in all
    installed = Signal()
    install_failed = Signal(str)
    cancelled = Signal()


# --------------------------------------------------------------------------
# the download list
# --------------------------------------------------------------------------

class ElidedLabel(QLabel):
    """One line that ends in … when it doesn't fit; the tooltip has it all.

    A long title or link would otherwise widen the whole window.
    """

    def __init__(self):
        super().__init__()
        self._full = ""
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def set_full_text(self, text):
        self._full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        width = max(self.contentsRect().width(), 20)
        self.setText(self.fontMetrics().elidedText(self._full, Qt.ElideRight, width))


class JobRow(QFrame):
    """One download in the list: what it is, how far it has got, what can be done."""

    def __init__(self, job, window):
        super().__init__()
        self.job, self.window = job, window
        self.setFrameShape(QFrame.StyledPanel)
        grid = QGridLayout(self)
        grid.setContentsMargins(10, 6, 10, 8)
        grid.setVerticalSpacing(3)

        self.title = ElidedLabel()
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setMaximumHeight(6)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.error.setStyleSheet(ERROR_STYLE)
        self.error.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.retry_btn = QPushButton()
        self.retry_btn.clicked.connect(lambda: window.queue.retry(job))
        self.action_btn = QPushButton()
        self.action_btn.clicked.connect(self._act)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        buttons.addWidget(self.retry_btn)
        buttons.addWidget(self.action_btn)

        grid.addWidget(self.title, 0, 0)
        grid.addLayout(buttons, 0, 1, 2, 1, Qt.AlignVCenter)
        grid.addWidget(self.detail, 1, 0)
        grid.addWidget(self.bar, 2, 0, 1, 2)
        grid.addWidget(self.error, 3, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        self.restyle()
        self.refresh()

    def restyle(self):
        self.detail.setStyleSheet(muted_style())

    def _act(self):
        job = self.job
        if job.state == jobs.RUNNING:
            self.window.queue.cancel(job)
        elif job.state == jobs.DONE:
            self.window.show_file(job)
        else:
            self.window.queue.remove(job)

    def refresh(self):
        job = self.job
        self.title.set_full_text(job.title or job.url)
        state, numbers = jobs.status(job)
        self.detail.setText("   ·   ".join(b for b in (jobs.summary(job), state, numbers) if b))

        running = job.state == jobs.RUNNING
        self.bar.setVisible(running)
        if running:
            if job.percent >= 0 and not (job.stage or job.cancelling):
                self.bar.setRange(0, 100)
                self.bar.setValue(int(job.percent))
            else:
                self.bar.setRange(0, 0)  # busy until there's a size to count against

        failed = job.state == jobs.FAILED
        self.error.setVisible(failed)
        if failed:
            self.error.setText(core.clean_error(job.error, login=job.login))

        self.retry_btn.setVisible(job.state in (jobs.FAILED, jobs.CANCELLED))
        self.retry_btn.setText(t("queue_retry"))
        self.action_btn.setEnabled(not job.cancelling)
        self.action_btn.setText(t("cancel") if running
                                else t("show_in_folder") if job.state == jobs.DONE
                                else t("queue_remove"))


class QueuePanel(QWidget):
    """Every download, in the order they run - one at a time."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.rows = {}            # job id -> JobRow
        self._running_id = None
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        head = QHBoxLayout()
        self.title = QLabel()
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        self.summary = QLabel()
        self.cancel_all_btn = QPushButton()
        self.cancel_all_btn.clicked.connect(window.cancel_all)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(lambda: window.queue.clear_finished())
        head.addWidget(self.title)
        head.addSpacing(8)
        head.addWidget(self.summary)
        head.addStretch(1)
        head.addWidget(self.cancel_all_btn)
        head.addWidget(self.clear_btn)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setMinimumHeight(150)
        holder = QWidget()
        self.list = QVBoxLayout(holder)
        self.list.setContentsMargins(0, 0, 0, 0)
        self.list.setSpacing(6)
        self.list.addStretch(1)
        self.scroll.setWidget(holder)

        col.addLayout(head)
        col.addWidget(self.scroll, 1)
        self.retranslate()

    def sync(self, job_list):
        """Match the rows to the queue: new jobs get one, gone ones lose theirs."""
        holder = self.scroll.widget()
        holder.setUpdatesEnabled(False)
        wanted = {job.id for job in job_list}
        for job_id in [key for key in self.rows if key not in wanted]:
            row = self.rows.pop(job_id)
            self.list.removeWidget(row)
            row.deleteLater()
        for index, job in enumerate(job_list):
            row = self.rows.get(job.id)
            if row is None:
                row = self.rows[job.id] = JobRow(job, self.window)
            if self.list.indexOf(row) != index:
                self.list.removeWidget(row)
                self.list.insertWidget(index, row)
        holder.setUpdatesEnabled(True)
        self.update_header(job_list)

    def refresh(self, job):
        row = self.rows.get(job.id)
        if row is None:
            return
        row.refresh()
        if job.state == jobs.RUNNING and job.id != self._running_id:
            # Follow the queue down a long list.
            self._running_id = job.id
            self.scroll.ensureWidgetVisible(row)
        self.update_header(self.window.queue.jobs())

    def update_header(self, job_list):
        done = sum(job.state == jobs.DONE for job in job_list)
        self.summary.setText(t("queue_summary", done=done, total=len(job_list)))
        self.cancel_all_btn.setVisible(any(job.state in (jobs.WAITING, jobs.RUNNING)
                                           for job in job_list))
        self.clear_btn.setVisible(any(job.state in jobs.FINISHED for job in job_list))

    def retranslate(self):
        self.title.setText(t("queue_title"))
        self.summary.setStyleSheet(muted_style())
        self.cancel_all_btn.setText(t("queue_cancel_all"))
        self.clear_btn.setText(t("queue_clear"))
        for row in self.rows.values():
            row.restyle()
            row.refresh()
        self.update_header(self.window.queue.jobs())


# --------------------------------------------------------------------------
# main window
# --------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"DLPizer {__version__}")
        self.setMinimumWidth(620)
        # Still filed under the app's old name, so choices made before the
        # rename to DLPizer carry over.
        self.settings = QSettings("ytgrab", "ytgrab")
        # The folder chosen last time, while it still exists.
        saved_dir = self.settings.value("save_dir")
        self.dest_dir = (Path(saved_dir) if saved_dir and Path(saved_dir).is_dir()
                         else core.default_download_dir())
        # The resolution picked last, a ceiling: a video without it gets the
        # highest one under it, and the choice survives for the next video.
        saved_height = str(self.settings.value("video_height", "best"))
        self.video_height = saved_height if saved_height.isdigit() else "best"
        self.info_worker = None
        self.thumb_token = 0      # which read the thumbnail on screen belongs to
        self.info = None          # last metadata read, for relabelling
        self.links = []           # the links in the box, when there are several
        self.transcripts = []     # subtitle tracks offered by the last read
        self.fetching = False
        # Browser to borrow the YouTube login from, or None for no login.
        saved = QSettings("ytgrab", "ytgrab").value("cookies_browser")
        self.cookies_browser = saved if saved in core.COOKIE_BROWSERS else None

        self.bridge = QueueBridge()
        self.bridge.changed.connect(self._on_queue_changed)
        self.queue = jobs.DownloadQueue(on_change=self.bridge.changed.emit,
                                        login=lambda: self.cookies_browser)

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
        self.queue_panel = QueuePanel(self)
        self.queue_panel.setVisible(False)
        layout.addWidget(self.queue_panel)
        layout.addStretch(1)
        self.root_layout = layout

        self._restore_choices()
        self.retranslate()
        self._sync_mode()

        self.update_bridge = UpdateBridge()
        self.update_bridge.checked.connect(self._on_update_checked)
        self.update_bridge.check_failed.connect(self._on_update_check_failed)
        self.update_bridge.progress.connect(self._on_update_progress)
        self.update_bridge.installed.connect(self._on_update_installed)
        self.update_bridge.install_failed.connect(self._on_update_failed)
        self.update_bridge.cancelled.connect(self._on_update_cancelled)
        # Checking, asking or installing: one at a time, so the check at start
        # can't open a second question over one asked for by hand.
        self.update_busy = False
        self.update_dialog = None
        self.pending_update = None   # offered once the downloads have finished
        # A packaged build looks for a newer one shortly after it opens;
        # from source there's nothing it could replace.
        if updater.install_target() is not None:
            threading.Thread(target=updater.clean_up, daemon=True).start()
            if self.update_auto_action.isChecked():
                QTimer.singleShot(3000, self.check_updates)

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

        self.options_menu.addSeparator()
        self.update_auto_action = QAction(self)
        self.update_auto_action.setCheckable(True)
        self.update_auto_action.setChecked(
            self.settings.value("check_updates", True, type=bool))
        self.update_auto_action.toggled.connect(
            lambda on: self.settings.setValue("check_updates", on))
        self.update_now_action = QAction(self)
        self.update_now_action.triggered.connect(lambda: self.check_updates(manual=True))
        self.options_menu.addAction(self.update_auto_action)
        self.options_menu.addAction(self.update_now_action)

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
        self.meta_label.setWordWrap(True)
        self.meta_label.setStyleSheet(muted_style())
        text_col.addWidget(self.title_label)
        text_col.addWidget(self.meta_label)

        # A video that sits in a playlist: that video, or the whole list.
        self.playlist_box = QWidget()
        choice = QVBoxLayout(self.playlist_box)
        choice.setContentsMargins(0, 4, 0, 0)
        choice.setSpacing(2)
        self.playlist_this = QRadioButton()
        self.playlist_whole = QRadioButton()
        self.playlist_this.setChecked(True)
        self.playlist_group = QButtonGroup(self)
        for button in (self.playlist_this, self.playlist_whole):
            self.playlist_group.addButton(button)
            choice.addWidget(button)
        self.playlist_whole.toggled.connect(self._on_playlist_choice)
        # The list's name wraps under its option, however long it is.
        self.playlist_name = QLabel()
        self.playlist_name.setWordWrap(True)
        self.playlist_name.setContentsMargins(24, 0, 0, 0)
        choice.addWidget(self.playlist_name)
        self.playlist_box.setVisible(False)
        text_col.addWidget(self.playlist_box)
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
        self.res_combo.activated.connect(self._on_height_chosen)

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
        col.addWidget(self._build_part_row())
        return wrapper

    def _build_part_row(self):
        """'Only a part' with its From and To times, and what they come to."""
        self.part_box = QWidget()
        col = QVBoxLayout(self.part_box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        row = QHBoxLayout()
        self.part_check = QCheckBox()
        self.part_check.toggled.connect(self._sync_part)
        self.part_from_label = QLabel()
        self.part_to_label = QLabel()
        self.part_from = QLineEdit()
        self.part_to = QLineEdit()
        for label, edit in ((self.part_from_label, self.part_from),
                            (self.part_to_label, self.part_to)):
            edit.setMaximumWidth(90)
            edit.textChanged.connect(self._sync_part)
            label.setBuddy(edit)
        self.part_from.setPlaceholderText(core.format_time(0))
        row.addWidget(self.part_check)
        row.addSpacing(12)
        row.addWidget(self.part_from_label)
        row.addWidget(self.part_from)
        row.addSpacing(6)
        row.addWidget(self.part_to_label)
        row.addWidget(self.part_to)
        row.addStretch(1)

        self.part_summary = QLabel()
        self.part_summary.setWordWrap(True)
        col.addLayout(row)
        col.addWidget(self.part_summary)
        return self.part_box

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
        self.download_btn = QPushButton()
        self.download_btn.setMinimumHeight(38)
        self.download_btn.setDefault(True)
        self.download_btn.clicked.connect(self.start_download)
        return self.download_btn

    # -- remembered choices ------------------------------------------------

    def _remembered_combos(self):
        return [(self.container_combo, "container"), (self.acodec_combo, "audio_stream"),
                (self.bitrate_combo, "mp3_quality"), (self.tfmt_combo, "transcript_format")]

    def _restore_choices(self):
        """Put back what was chosen last time, and keep each new choice.

        Every choice is saved the moment it is made, so a crash or a closed
        laptop doesn't lose it. Anything unknown keeps its default.
        """
        settings = self.settings
        mode = settings.value("mode")
        if mode in self.mode_buttons:
            self.mode_buttons[mode].setChecked(True)
        self.mode_group.buttonClicked.connect(
            lambda _button: settings.setValue("mode", self.current_mode()))

        for combo, key in self._remembered_combos():
            index = combo.findData(settings.value(key))
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.activated.connect(
                lambda _index, c=combo, k=key: settings.setValue(k, c.currentData()))

        self.embed_check.setChecked(settings.value("embed_thumbnail", True, type=bool))
        self.embed_check.toggled.connect(
            lambda on: settings.setValue("embed_thumbnail", on))
        # Nothing is read yet, so every standard resolution is on offer.
        self._fill_resolutions(core.STANDARD_HEIGHTS)

    def _on_height_chosen(self):
        self.video_height = self.res_combo.currentData()
        self.settings.setValue("video_height", self.video_height)

    def _height_for(self, heights):
        """The remembered resolution, or the highest of these under it."""
        if self.video_height == "best":
            return "best"
        fitting = [h for h in heights if h <= int(self.video_height)]
        return str(max(fitting)) if fitting else "best"

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
            self.tlang_combo.addItem(core.transcript_label(entry), entry["code"])
        if not self.transcripts:
            self.tlang_combo.addItem(t("transcript_none"), "")
            return
        found = self.tlang_combo.findData(previous)
        self.tlang_combo.setCurrentIndex(
            found if found >= 0 else self._default_transcript_index())

    def _fill_resolutions(self, heights):
        """Offer these heights after "Best", showing the remembered choice."""
        self.res_combo.clear()
        self.res_combo.addItem(t("best_available"), "best")
        for h in heights:
            self.res_combo.addItem(f"{h}p", str(h))
        found = self.res_combo.findData(self._height_for(heights))
        self.res_combo.setCurrentIndex(max(found, 0))

    def retranslate(self):
        """Apply the active language to every widget that shows text."""
        self.lang_menu.setTitle(t("menu_language"))
        for code, action in self.lang_actions.items():
            action.setChecked(code == i18n.language())
        self.options_menu.setTitle(t("menu_options"))
        self.login_menu.setTitle(t("login_menu"))
        self.login_actions[None].setText(t("login_off"))
        self.update_auto_action.setText(t("menu_updates_auto"))
        self.update_now_action.setText(t("menu_updates_now"))

        self.link_label.setText(t("link"))
        self.url_edit.setPlaceholderText(t("url_placeholder"))
        self.fetch_btn.setText(t("fetching") if self.fetching else t("fetch"))
        self.fetch_btn.setToolTip(t("read_one_link") if self.links else "")
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
        self.part_check.setText(t("part_check"))
        self.part_from_label.setText(t("part_from"))
        self.part_to_label.setText(t("part_to"))
        for edit in (self.part_from, self.part_to):
            edit.setToolTip(t("part_tip"))
        self.part_from.setAccessibleName(t("part_from").rstrip(":"))
        self.part_to.setAccessibleName(t("part_to").rstrip(":"))
        self._sync_part_video()

        self.tlang_label.setText(t("transcript_lang"))
        self.tfmt_label.setText(t("transcript_format"))
        self._relabel(self.tfmt_combo,
                      [t("transcript_txt"), t("transcript_srt"), t("transcript_vtt")])
        # "(automatic)" is translated, so the list is rebuilt, not just relabelled.
        self._fill_transcript_langs()

        self.dest_label.setText(t("save_to"))
        self.browse_btn.setText(t("change"))
        self._show_panel()
        self._sync_download_btn()
        self.queue_panel.retranslate()
        self.statusBar().showMessage(self._ffmpeg_status())

    # -- behaviour ---------------------------------------------------------

    def _ffmpeg_status(self):
        loc = core.ffmpeg_location()
        if not loc:
            return t("ffmpeg_status_missing")
        # The one inside a packaged app lives in a temporary folder whose name
        # means nothing to anyone.
        unpacked = getattr(sys, "_MEIPASS", None)
        if unpacked and Path(loc).resolve().is_relative_to(Path(unpacked).resolve()):
            return t("ffmpeg_bundled")
        return t("ffmpeg_at", path=loc)

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
        # A transcript is always the whole thing.
        self.part_box.setVisible(mode != "transcript")

    def _whole_playlist(self):
        """Whether Download takes the playlist the link names rather than one video."""
        info = self.info
        if self.links or not info or not info.get("playlist"):
            return False
        return not info.get("video", True) or self.playlist_whole.isChecked()

    def _several(self):
        """Whether Download adds more than one video: several links, or a playlist."""
        return bool(self.links) or self._whole_playlist()

    def _on_playlist_choice(self):
        self._sync_part_video()
        self._sync_download_btn()

    def _part_section(self):
        """The part to download, as (start, end) seconds; ValueError if it doesn't fit."""
        duration = self.info["duration"] if self.info else 0
        return core.parse_section(self.part_from.text(), self.part_to.text(), duration)

    def _sync_part_video(self):
        """Fit the part row to what's on screen: the video's length, a live
        stream, or several videos at once."""
        live = bool(self.info and self.info["is_live"])
        several = self._several()
        if live or several:
            self.part_check.setChecked(False)
        self.part_check.setEnabled(not (live or several))
        self.part_check.setToolTip(t("part_live") if live
                                   else t("part_one_video") if several
                                   else t("part_check_tip"))
        duration = self.info["duration"] if self.info else 0
        self.part_to.setPlaceholderText(core.format_time(duration) if duration else "")
        self._sync_part()

    def _sync_part(self):
        """Enable the times with the box, and say what they come to."""
        on = self.part_check.isChecked() and self.part_check.isEnabled()
        self.part_from.setEnabled(on)
        self.part_to.setEnabled(on)
        self.part_summary.setVisible(on)
        if not on:
            return
        try:
            start, end = self._part_section()
        except ValueError as exc:
            # Two empty fields are where everyone starts: a hint, not an error.
            empty = not (self.part_from.text().strip() or self.part_to.text().strip())
            self.part_summary.setStyleSheet(muted_style() if empty else ERROR_STYLE)
            self.part_summary.setText(str(exc))
            return
        self.part_summary.setStyleSheet(muted_style())
        if end is None:
            self.part_summary.setText(t("part_summary_open", start=core.format_time(start)))
        else:
            self.part_summary.setText(t("part_summary", start=core.format_time(start),
                                        end=core.format_time(end),
                                        length=core.format_time(end - start)))

    def _sync_download_btn(self):
        """Download now, or join the queue - for one video, a playlist or several links."""
        busy = self.queue.busy()
        if self.links:
            text = tn("queue_add_links" if busy else "download_links", len(self.links))
        elif self._whole_playlist():
            count = self.info["playlist"]["count"]
            text = tn("queue_add_n" if busy else "download_n", count)
        else:
            text = t("queue_add" if busy else "download")
        self.download_btn.setText(text)

    def _on_url_changed(self):
        text = self.url_edit.text()
        if "\n" in text or "\r" in text:
            # A pasted list stays on one line, a space between links.
            self.url_edit.setText(" ".join(text.split()))
            return
        found = core.find_links(text)
        several = found if len(found) > 1 else []
        if self.info is not None or several != self.links:
            # A new link invalidates whatever metadata is on screen.
            self.info = None
            self.links = several
            self.thumb_token += 1  # a thumbnail still loading belongs to the old link
            self.thumb_label.clear()
            # Until a video is read its own resolutions aren't known; each
            # standard one is a ceiling that fits any video.
            self._fill_resolutions(core.STANDARD_HEIGHTS)
            self.transcripts = core.common_transcripts(i18n.language()) if several else []
            self._fill_transcript_langs()
            # Times typed for one video rarely fit the next; they stay in the
            # fields, but the next download is whole until asked otherwise.
            self.part_check.setChecked(False)
            self._sync_part_video()
            self._show_panel()
        self.fetch_btn.setEnabled(not self.fetching and not self.links)
        self.fetch_btn.setToolTip(t("read_one_link") if self.links else "")
        self._sync_download_btn()

    def paste_and_fetch(self):
        text = QApplication.clipboard().text().strip()
        if not text:
            return
        found = core.find_links(text)
        if len(found) > 1:
            self.url_edit.setText(" ".join(found))
        else:
            self.url_edit.setText(found[0] if found else text)
            self.fetch_info()

    def fetch_info(self):
        text = self.url_edit.text().strip()
        found = core.find_links(text)
        if len(found) > 1:
            return  # several links download as they are
        url = found[0] if found else text
        if not core.is_supported_url(url):
            self.statusBar().showMessage(t("invalid_link"), 5000)
            return
        if self.info_worker and self.info_worker.isRunning():
            return
        if url != text:
            self.url_edit.setText(url)  # "Watch this: https://..." becomes the link

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
        self.fetch_btn.setEnabled(not self.links)
        self.fetch_btn.setText(t("fetch"))

    def _show_panel(self):
        """Fill the panel under the link: several links, a playlist, or a video."""
        if self.links:
            self.thumb_label.setVisible(False)
            self.title_label.setText(tn("batch_title", len(self.links)))
            self.meta_label.setText(t("batch_note"))
            self.playlist_box.setVisible(False)
            self.info_panel.setVisible(True)
            return
        info = self.info
        if not info:
            self.info_panel.setVisible(False)
            return
        playlist = info.get("playlist")
        self.thumb_label.setVisible(True)
        self.title_label.setText(info["title"])
        if info.get("video", True):
            bits = (info["uploader"], core.format_duration(info["duration"]),
                    t("live") if info["is_live"] else "")
        else:
            bits = (t("playlist_label"), info["uploader"],
                    tn("playlist_videos", playlist["count"]))
        self.meta_label.setText("  ·  ".join(b for b in bits if b))
        offer = bool(playlist) and info.get("video", True)
        self.playlist_box.setVisible(offer)
        if offer:
            self.playlist_this.setText(t("playlist_this"))
            self.playlist_whole.setText(tn("playlist_whole", playlist["count"]))
            self.playlist_name.setText(t("playlist_name", title=playlist["title"]))
            self.playlist_name.setStyleSheet(muted_style())
            self.playlist_name.setVisible(bool(playlist["title"]))
        self.info_panel.setVisible(True)

    def _on_info(self, info):
        self.info = info
        self.playlist_this.setChecked(True)  # the link names this video; the list is the option
        self._fill_resolutions(info["heights"])
        self.transcripts = info.get("transcripts") or (
            [] if info.get("video", True) else core.common_transcripts(i18n.language()))
        self._fill_transcript_langs()
        self._sync_part_video()
        self._show_panel()
        self._sync_download_btn()

        self.thumb_label.clear()
        urls = info.get("thumbnails") or [info["thumbnail"]]
        self.thumb_token += 1
        if any(urls):
            loader = ThumbLoader(self.thumb_token, urls)
            loader.loaded.connect(self._on_thumb)
            loader.start()

        self.statusBar().showMessage(t("ready"), 4000)

    def _on_thumb(self, token, data):
        if token != self.thumb_token:
            return  # a video read before the one on screen
        pix = QPixmap()
        if pix.loadFromData(data):
            self.thumb_label.setPixmap(pix)

    def _on_info_failed(self, message):
        self.info = None
        self._show_panel()
        self._sync_download_btn()
        self.statusBar().showMessage(t("read_failed"), 6000)
        QMessageBox.warning(self, t("read_failed_title"), message)

    def choose_dest(self):
        chosen = QFileDialog.getExistingDirectory(self, t("choose_dir"), str(self.dest_dir))
        if chosen:
            self.dest_dir = Path(chosen)
            self.dest_edit.setText(chosen)
            self.settings.setValue("save_dir", chosen)

    def show_file(self, job):
        target = job.path.parent if job.path else Path(job.dest)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def start_download(self):
        text = self.url_edit.text().strip()
        found = core.find_links(text)
        if not found and core.is_supported_url(text):
            found = [text]
        if not found:
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

        section = None
        if mode != "transcript" and self.part_check.isChecked() and self.part_check.isEnabled():
            try:
                section = self._part_section()
            except ValueError as exc:
                QMessageBox.warning(self, t("part_invalid_title"), str(exc))
                return

        # txt is parsed here and vtt is served as-is, so neither needs ffmpeg.
        if (mode != "transcript" or container == "srt") and not core.ffmpeg_location():
            QMessageBox.critical(self, t("ffmpeg_missing_title"), t("ffmpeg_missing_body"))
            return

        def job(url, title=""):
            return jobs.Job(url, self.dest_dir, mode, quality, container,
                            self.embed_check.isChecked(), section, title)

        if len(found) > 1:
            new = [job(url) for url in found]
        elif self._whole_playlist():
            new = [job(entry["url"], entry["title"]) for entry in self.info["playlist"]["entries"]]
        else:
            known = self.info and self.info.get("video", True)
            new = [job(found[0], self.info["title"] if known else "")]

        was_busy = self.queue.busy()
        self.queue.add(new)
        if was_busy or len(new) > 1:
            self.statusBar().showMessage(tn("queued_n", len(new)), 5000)

    def cancel_all(self):
        answer = QMessageBox.question(self, t("queue_cancel_all"), t("queue_cancel_all_ask"))
        if answer == QMessageBox.Yes:
            self.queue.cancel_all()

    def _on_queue_changed(self, job):
        if job is None:
            job_list = self.queue.jobs()
            self.queue_panel.sync(job_list)
            self._show_queue(bool(job_list))
        else:
            self.queue_panel.refresh(job)
            if job.state == jobs.DONE and job.path:
                self.statusBar().showMessage(t("saved_to", path=job.path), 8000)
            elif job.state == jobs.FAILED:
                self.statusBar().showMessage(t("failed"), 6000)
        self._sync_download_btn()
        if self.pending_update and not self.queue.busy():
            release, self.pending_update = self.pending_update, None
            QTimer.singleShot(0, lambda: self._offer_update(release))

    def _show_queue(self, visible):
        """The list takes the window's spare height while there's anything in it."""
        self.queue_panel.setVisible(visible)
        layout = self.root_layout
        layout.setStretchFactor(self.queue_panel, 1 if visible else 0)
        layout.setStretch(layout.count() - 1, 0 if visible else 1)

    # -- updates -----------------------------------------------------------

    def check_updates(self, manual=False):
        """Ask GitHub for a newer release, off the window's thread."""
        if self.update_busy:
            return
        self.update_busy = True
        if manual:
            self.statusBar().showMessage(t("update_checking"))
        bridge = self.update_bridge

        def run():
            try:
                bridge.checked.emit(updater.check(), manual)
            except Exception as exc:  # noqa: BLE001 - reported, or ignored if automatic
                bridge.check_failed.emit(str(exc), manual)

        threading.Thread(target=run, daemon=True).start()

    def _on_update_checked(self, release, manual):
        if manual:
            self.statusBar().showMessage(self._ffmpeg_status())
        if release is None:
            self.update_busy = False
            if manual:
                QMessageBox.information(self, t("update_none_title"),
                                        t("update_latest", version=__version__))
            return
        self._offer_update(release)

    def _on_update_check_failed(self, error, manual):
        self.update_busy = False
        # A check made by itself stays quiet: no network is no news.
        if manual:
            self.statusBar().showMessage(self._ffmpeg_status())
            QMessageBox.warning(self, t("update_check_failed_title"),
                                t("update_check_failed", error=error))

    def _offer_update(self, release):
        self.update_busy = True
        if self.queue.busy():
            # Restarting would cut the downloads short; ask once they're done.
            self.update_busy = False
            self.pending_update = release
            self.statusBar().showMessage(t("update_after_downloads", version=release.version), 8000)
            return
        target = updater.install_target()
        installable = bool(target and release.url and updater.can_replace(target))

        text = t("update_available", new=release.version, current=__version__)
        if release.changes:
            text += "\n\n" + t("update_changes") + "\n" + "\n".join(
                "• " + change for change in release.changes[:8])
        size = core.format_size(release.size)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(t("update_title"))
        box.setText(text)
        box.setInformativeText(
            (t("update_ask", size=size) if size else t("update_ask_plain")) if installable
            else t("update_ask_page"))
        go = box.addButton(t("update_now") if installable else t("update_open_page"),
                           QMessageBox.AcceptRole)
        box.addButton(t("update_later"), QMessageBox.RejectRole)
        box.setDefaultButton(go)
        box.exec()
        if box.clickedButton() is go and installable:
            self._install_update(release, target)  # busy until it ends
            return
        self.update_busy = False
        if box.clickedButton() is go:
            QDesktopServices.openUrl(QUrl(release.page))

    def _install_update(self, release, target):
        """Download the new version with a progress window, then swap and restart."""
        self.update_release, self.update_target = release, target
        dialog = QProgressDialog(t("update_downloading", version=release.version),
                                 t("cancel"), 0, 0, self)
        dialog.setWindowTitle(t("update_title"))
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        stop = threading.Event()
        dialog.canceled.connect(stop.set)
        self.update_dialog = dialog
        dialog.show()
        bridge = self.update_bridge

        def run():
            try:
                updater.install(release, target,
                                progress=lambda done, total: bridge.progress.emit(done, total),
                                cancelled=stop.is_set)
            except updater.Cancelled:
                bridge.cancelled.emit()
            except Exception as exc:  # noqa: BLE001 - shown to the person
                bridge.install_failed.emit(str(exc))
            else:
                bridge.installed.emit()

        threading.Thread(target=run, daemon=True).start()

    def _on_update_progress(self, done, total):
        dialog = self.update_dialog
        if dialog is None:
            return
        label = t("update_downloading", version=self.update_release.version)
        if total:
            dialog.setMaximum(100)
            dialog.setValue(min(100, done * 100 // total))
            label += f"\n{core.format_size(done)} / {core.format_size(total)}"
        dialog.setLabelText(label)

    def _close_update_dialog(self):
        self.update_busy = False
        dialog, self.update_dialog = self.update_dialog, None
        if dialog is not None:
            dialog.canceled.disconnect()
            dialog.close()
            dialog.deleteLater()

    def _on_update_installed(self):
        self._close_update_dialog()
        try:
            updater.relaunch(self.update_target)
        except OSError:
            QMessageBox.information(self, t("update_title"),
                                    t("update_restart_failed", version=self.update_release.version))
        self.close()
        QApplication.quit()

    def _on_update_failed(self, error):
        self._close_update_dialog()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(t("update_failed_title"))
        box.setText(t("update_failed", error=error))
        page = box.addButton(t("update_open_page"), QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is page:
            QDesktopServices.openUrl(QUrl(self.update_release.page))

    def _on_update_cancelled(self):
        self._close_update_dialog()

    def closeEvent(self, event):
        pending = [job for job in self.queue.jobs()
                   if job.state in (jobs.WAITING, jobs.RUNNING)]
        if pending:
            answer = QMessageBox.question(self, t("quit_busy_title"),
                                          tn("quit_busy_body", len(pending)))
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self.queue.close(3.0)
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
    # No display name: Qt would add it to the title, as "DLPizer 1.6.0 - DLPizer".
    app.setApplicationName("DLPizer")
    app.setWindowIcon(make_icon())
    i18n.set_language(startup_language())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
