"""Interface strings for ytgrab, in English and Slovak.

The whole app reads its text through :func:`t`. The active language is a
module-level setting so the download engine can produce localised error
messages without every caller having to thread a language code through it;
the web app, which serves one request at a time per language, passes the code
explicitly instead.
"""

import locale
import os
import sys

DEFAULT_LANGUAGE = "en"

# Shown in the language menu, in each language's own name.
LANGUAGE_NAMES = {"en": "English", "sk": "Slovenčina"}

STRINGS = {
    "en": {
        # -- window chrome --
        "menu_language": "&Language",
        "menu_options": "&Options",
        "login_menu": "Use YouTube login from browser",
        "login_off": "Off",
        "login_note_title": "Using your YouTube login",
        "login_note_body": ("ytgrab will read your YouTube cookies from {browser} on this "
                            "computer and send them only to YouTube, so its requests go out "
                            "signed in - which is what YouTube's bot check asks for.\n\n"
                            "You need to be signed in to YouTube in {browser}. YouTube can "
                            "temporarily restrict an account that downloads a lot, so a "
                            "secondary account is the safer choice.\n\n"
                            "On Windows, Chrome, Edge and other Chromium-based browsers usually "
                            "can't be read; Firefox can."),

        # -- link row --
        "link": "Link:",
        "url_placeholder": "https://www.youtube.com/watch?v=...",
        "fetch": "Fetch",
        "fetching": "Reading…",
        "paste": "Paste",
        "paste_tip": "Paste a link from the clipboard and read its details",

        # -- info panel --
        "live": "LIVE",

        # -- mode picker --
        "mode_title": "What do you want?",
        "mode_video": "Video",
        "mode_video_tip": "Video and audio together, muxed without re-encoding",
        "mode_audio": "Audio (original)",
        "mode_audio_tip": "The audio stream exactly as YouTube stores it - no quality loss",
        "mode_mp3": "MP3",
        "mode_mp3_tip": "The audio converted to MP3 (a second lossy step)",
        "mode_transcript": "Transcript",
        "mode_transcript_tip": "The subtitle track as text - no video or audio is downloaded",

        # -- options --
        "resolution": "Resolution:",
        "container": "Container:",
        "best_available": "Best available",
        "container_mp4": "MP4 - plays everywhere",
        "container_mkv": "MKV - keeps the highest-quality streams as-is",
        "container_tip": ("YouTube serves 4K only as VP9/AV1, which MP4 can't always hold.\n"
                          "Choose MKV if you want maximum quality."),
        "stream": "Stream:",
        "audio_best": "Best available (no re-encoding)",
        "audio_opus": "Prefer Opus (.opus)",
        "audio_m4a": "Prefer AAC (.m4a)",
        "bitrate": "Bitrate:",
        "bitrate_v0": "VBR V0 - best quality (~245 kbps)",
        "bitrate_cbr": "{kbps} kbps CBR",
        "embed": "Embed cover art and metadata",

        # -- transcript --
        "transcript_lang": "Language:",
        "transcript_format": "Format:",
        "transcript_txt": "Plain text - one flowing transcript",
        "transcript_srt": "SRT - timed subtitles",
        "transcript_vtt": "WebVTT - timed subtitles",
        "transcript_auto": "{code} (automatic)",
        "transcript_none": "This video has no transcript.",

        # -- destination --
        "save_to": "Save to:",
        "change": "Change…",
        "choose_dir": "Save downloads to",

        # -- actions --
        "download": "Download",
        "cancel": "Cancel",
        "show_in_folder": "Show in folder",

        # -- status bar --
        "ffmpeg_at": "ffmpeg: {path}",
        "ffmpeg_status_missing": "ffmpeg not found - conversion will fail",
        "invalid_link": "Enter a valid http(s) link.",
        "reading_details": "Reading video details…",
        "ready": "Ready.",
        "read_failed": "Could not read that link.",
        "read_failed_title": "Could not read that link",
        "saved_to": "Saved to {path}",

        # -- dialogs --
        "no_link_title": "No link",
        "no_link_body": "Paste a video link first.",
        "ffmpeg_missing_title": "ffmpeg missing",
        "ffmpeg_missing_body": "ffmpeg could not be found, so merging and conversion cannot run.",
        "download_failed_title": "Download failed",

        # -- progress --
        "starting": "Starting…",
        "cancelling": "Cancelling…",
        "downloading": "Downloading",
        "downloading_percent": "Downloading  {percent}%",
        "eta_left": "{time} left",
        "saved": "Saved",
        "failed": "Failed",
        "cancelled": "Cancelled",

        # -- postprocessing stages --
        "stage_processing": "Processing",
        "stage_ExtractAudio": "Extracting audio",
        "stage_Merger": "Merging video and audio",
        "stage_VideoRemuxer": "Remuxing",
        "stage_VideoConvertor": "Converting",
        "stage_EmbedThumbnail": "Embedding cover art",
        "stage_Metadata": "Writing metadata",
        "stage_MoveFiles": "Finishing up",
        "stage_SubtitlesConvertor": "Converting subtitles",

        # -- engine errors --
        "err_bot": ("YouTube asked this machine to confirm it isn't a bot, and stopped the "
                    "other ways ytgrab tried as well. Waiting a while or switching networks "
                    "usually clears it. If it keeps happening, sign in to YouTube in your "
                    "browser and pick that browser under Options → Use YouTube login from "
                    "browser."),
        "err_bot_login": ("YouTube still asked to confirm this isn't a bot, even with the login "
                          "from {browser}. Check that you're signed in to YouTube in {browser}, "
                          "or try again later."),
        "err_cookies": "Couldn't read the YouTube login from {browser}: {reason}",
        "err_unavailable": "That video is unavailable - it may be private, removed or region locked.",
        "err_unsupported": "That link isn't one yt-dlp recognises.",
        "err_no_video": "No downloadable video found at that link.",
        "err_no_output": "yt-dlp finished but produced no output file.",
        "err_no_transcript": "No transcript is available in that language.",

        # -- browser version --
        "web_tagline": "Download a video, or pull the audio stream straight out untouched.",
        "web_mode_video": "Video",
        "web_mode_audio": "Audio",
        "web_mode_mp3": "MP3",
        "web_mode_video_sub": "with audio",
        "web_mode_audio_sub": "original stream",
        "web_mode_mp3_sub": "converted",
        "web_mode_transcript": "Transcript",
        "web_mode_transcript_sub": "subtitles as text",
        "web_transcript_lang": "Language",
        "web_transcript_format": "Format",
        "web_resolution": "Resolution",
        "web_container": "Container",
        "web_container_mp4": "MP4 — most compatible",
        "web_container_mkv": "MKV — keeps the highest-quality streams as-is",
        "web_stream": "Stream",
        "web_bitrate": "Bitrate",
        "web_done": "Ready",
        "web_save_file": "Save file",
        "web_save_named": "Save {name}",
        "web_downloading": "Downloading… {percent}%",
        "web_footer": "Runs locally via yt-dlp + ffmpeg. For content you have the right to download.",
        "decimal_separator": ".",
        "err_unknown_mode": "Unknown download mode.",
        "err_unknown_container": "Unknown container.",
        "err_unknown_job": "Unknown job.",
        "err_file_not_ready": "File is not ready.",
        "err_file_missing": "File is missing.",
    },

    "sk": {
        # -- window chrome --
        "menu_language": "&Jazyk",
        "menu_options": "&Možnosti",
        "login_menu": "Použiť prihlásenie do YouTube z prehliadača",
        "login_off": "Vypnuté",
        "login_note_title": "Použitie vášho prihlásenia do YouTube",
        "login_note_body": ("ytgrab načíta vaše cookies pre YouTube z prehliadača {browser} "
                            "v tomto počítači a pošle ich výhradne službe YouTube, takže jeho "
                            "požiadavky pôjdu ako od prihláseného používateľa – presne to "
                            "kontrola robotov vyžaduje.\n\n"
                            "V prehliadači {browser} musíte byť prihlásení do YouTube. YouTube "
                            "môže dočasne obmedziť účet, ktorý veľa sťahuje, preto je "
                            "bezpečnejší vedľajší účet.\n\n"
                            "Vo Windowse sa z Chrome, Edge a iných prehliadačov založených na "
                            "Chromiu cookies väčšinou načítať nedajú; z Firefoxu áno."),

        # -- link row --
        "link": "Odkaz:",
        "url_placeholder": "https://www.youtube.com/watch?v=...",
        "fetch": "Načítať",
        "fetching": "Načítava sa…",
        "paste": "Prilepiť",
        "paste_tip": "Prilepí odkaz zo schránky a načíta jeho údaje",

        # -- info panel --
        "live": "NAŽIVO",

        # -- mode picker --
        "mode_title": "Čo chcete stiahnuť?",
        "mode_video": "Video",
        "mode_video_tip": "Video aj zvuk v jednom súbore, spojené bez opätovného kódovania",
        "mode_audio": "Zvuk (pôvodný)",
        "mode_audio_tip": "Zvuková stopa presne v tej podobe, v akej ju ukladá YouTube – bez straty kvality",
        "mode_mp3": "MP3",
        "mode_mp3_tip": "Zvuk prevedený do MP3 (ďalšia stratová konverzia)",
        "mode_transcript": "Prepis",
        "mode_transcript_tip": "Titulky ako text – video ani zvuk sa nesťahujú",

        # -- options --
        "resolution": "Rozlíšenie:",
        "container": "Kontajner:",
        "best_available": "Najlepšie dostupné",
        "container_mp4": "MP4 – prehrá sa všade",
        "container_mkv": "MKV – ponechá najkvalitnejšie stopy bez zmeny",
        "container_tip": ("YouTube ponúka 4K len v kodekoch VP9/AV1, ktoré sa do MP4 nie vždy dajú zabaliť.\n"
                          "Ak chcete najvyššiu kvalitu, vyberte MKV."),
        "stream": "Stopa:",
        "audio_best": "Najlepšia dostupná (bez prekódovania)",
        "audio_opus": "Uprednostniť Opus (.opus)",
        "audio_m4a": "Uprednostniť AAC (.m4a)",
        "bitrate": "Dátový tok:",
        "bitrate_v0": "VBR V0 – najvyššia kvalita (~245 kb/s)",
        "bitrate_cbr": "{kbps} kb/s CBR",
        "embed": "Vložiť obal a metaúdaje",

        # -- prepis --
        "transcript_lang": "Jazyk:",
        "transcript_format": "Formát:",
        "transcript_txt": "Čistý text – súvislý prepis",
        "transcript_srt": "SRT – titulky s časovaním",
        "transcript_vtt": "WebVTT – titulky s časovaním",
        "transcript_auto": "{code} (automatické)",
        "transcript_none": "Toto video nemá prepis.",

        # -- destination --
        "save_to": "Uložiť do:",
        "change": "Zmeniť…",
        "choose_dir": "Kam ukladať stiahnuté súbory",

        # -- actions --
        "download": "Stiahnuť",
        "cancel": "Zrušiť",
        "show_in_folder": "Zobraziť v priečinku",

        # -- status bar --
        "ffmpeg_at": "ffmpeg: {path}",
        "ffmpeg_status_missing": "ffmpeg sa nenašiel – konverzia zlyhá",
        "invalid_link": "Zadajte platný odkaz http(s).",
        "reading_details": "Načítavajú sa údaje o videu…",
        "ready": "Hotovo.",
        "read_failed": "Odkaz sa nepodarilo načítať.",
        "read_failed_title": "Odkaz sa nepodarilo načítať",
        "saved_to": "Uložené do {path}",

        # -- dialogs --
        "no_link_title": "Chýba odkaz",
        "no_link_body": "Najprv prilepte odkaz na video.",
        "ffmpeg_missing_title": "Chýba ffmpeg",
        "ffmpeg_missing_body": "ffmpeg sa nepodarilo nájsť, takže spájanie ani konverzia nemôžu prebehnúť.",
        "download_failed_title": "Sťahovanie zlyhalo",

        # -- progress --
        "starting": "Spúšťa sa…",
        "cancelling": "Ruší sa…",
        "downloading": "Sťahovanie",
        "downloading_percent": "Sťahovanie  {percent} %",
        "eta_left": "zostáva {time}",
        "saved": "Uložené",
        "failed": "Zlyhalo",
        "cancelled": "Zrušené",

        # -- postprocessing stages --
        "stage_processing": "Spracovanie",
        "stage_ExtractAudio": "Extrahovanie zvuku",
        "stage_Merger": "Spájanie videa a zvuku",
        "stage_VideoRemuxer": "Prebaľovanie",
        "stage_VideoConvertor": "Konverzia",
        "stage_EmbedThumbnail": "Vkladanie obalu",
        "stage_Metadata": "Zapisovanie metaúdajov",
        "stage_MoveFiles": "Dokončovanie",
        "stage_SubtitlesConvertor": "Konverzia titulkov",

        # -- engine errors --
        "err_bot": ("YouTube žiada od tohto počítača potvrdenie, že nie je robot, a zastavil "
                    "aj ostatné spôsoby, ktoré ytgrab skúsil. Zvyčajne pomôže chvíľu počkať "
                    "alebo prejsť na inú sieť. Ak sa to opakuje, prihláste sa do YouTube "
                    "v prehliadači a vyberte ho v ponuke Možnosti → Použiť prihlásenie do "
                    "YouTube z prehliadača."),
        "err_bot_login": ("YouTube aj s prihlásením z prehliadača {browser} žiada potvrdenie, "
                          "že nejde o robota. Skontrolujte, či ste v prehliadači {browser} "
                          "prihlásení do YouTube, alebo to skúste neskôr."),
        "err_cookies": "Prihlásenie do YouTube sa z prehliadača {browser} nepodarilo načítať: {reason}",
        "err_unavailable": "Toto video nie je dostupné – môže byť súkromné, odstránené alebo blokované vo vašej krajine.",
        "err_unsupported": "Tento odkaz yt-dlp nepozná.",
        "err_no_video": "Na tomto odkaze sa nenašlo žiadne video na stiahnutie.",
        "err_no_output": "yt-dlp skončil, ale nevytvoril žiadny výstupný súbor.",
        "err_no_transcript": "V tomto jazyku nie je k dispozícii žiadny prepis.",

        # -- browser version --
        "web_tagline": "Stiahnite si video alebo z neho vytiahnite zvukovú stopu v pôvodnej podobe.",
        "web_mode_video": "Video",
        "web_mode_audio": "Zvuk",
        "web_mode_mp3": "MP3",
        "web_mode_video_sub": "so zvukom",
        "web_mode_audio_sub": "pôvodná stopa",
        "web_mode_mp3_sub": "konvertované",
        "web_mode_transcript": "Prepis",
        "web_mode_transcript_sub": "titulky ako text",
        "web_transcript_lang": "Jazyk",
        "web_transcript_format": "Formát",
        "web_resolution": "Rozlíšenie",
        "web_container": "Kontajner",
        "web_container_mp4": "MP4 – najkompatibilnejší",
        "web_container_mkv": "MKV – ponechá najkvalitnejšie stopy bez zmeny",
        "web_stream": "Stopa",
        "web_bitrate": "Dátový tok",
        "web_done": "Hotovo",
        "web_save_file": "Uložiť súbor",
        "web_save_named": "Uložiť {name}",
        "web_downloading": "Sťahovanie… {percent} %",
        "web_footer": "Beží lokálne cez yt-dlp + ffmpeg. Určené na obsah, ktorý máte právo stiahnuť.",
        "decimal_separator": ",",
        "err_unknown_mode": "Neznámy režim sťahovania.",
        "err_unknown_container": "Neznámy kontajner.",
        "err_unknown_job": "Neznáma úloha.",
        "err_file_not_ready": "Súbor ešte nie je pripravený.",
        "err_file_missing": "Súbor chýba.",
    },
}

_current = DEFAULT_LANGUAGE


def languages():
    """Language codes in menu order, best-known name first."""
    return list(STRINGS)


def language_name(code):
    return LANGUAGE_NAMES.get(code, code)


def language():
    return _current


def set_language(code):
    """Switch the app-wide language. Unknown codes fall back to English."""
    global _current
    _current = code if code in STRINGS else DEFAULT_LANGUAGE
    return _current


def normalise(code):
    """'sk_SK.UTF-8', 'sk-SK', 'SK' -> 'sk', or None if we don't have it."""
    if not code:
        return None
    base = str(code).replace("-", "_").split(".")[0].split("_")[0].lower()
    return base if base in STRINGS else None


def t(key, lang=None, **fields):
    """Look up a string, falling back to English and then to the key itself."""
    table = STRINGS.get(lang or _current, {})
    text = table.get(key) or STRINGS[DEFAULT_LANGUAGE].get(key, key)
    return text.format(**fields) if fields else text


def number(value, digits=1, lang=None):
    """Format a number with the decimal separator the language expects."""
    text = f"{value:.{digits}f}"
    return text.replace(".", ",") if (lang or _current) == "sk" else text


def detect_language():
    """Guess the language from the environment, defaulting to English."""
    for name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        # LANGUAGE holds a colon-separated preference list.
        for part in (os.environ.get(name) or "").split(":"):
            found = normalise(part)
            if found:
                return found

    if sys.platform == "win32":
        # Env vars are normally unset on Windows; ask for the UI language.
        try:
            import ctypes
            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            if lcid & 0x3FF == 0x1B:  # LANG_SLOVAK
                return "sk"
        except Exception:  # noqa: BLE001 - detection must never break startup
            pass

    try:
        found = normalise((locale.getlocale()[0] or ""))
        if found:
            return found
    except (ValueError, TypeError):
        pass

    return DEFAULT_LANGUAGE
