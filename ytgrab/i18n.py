"""Interface strings for DLPizer, in English and Slovak.

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
        "login_note_body": ("DLPizer will read your YouTube cookies from {browser} on this "
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

        # -- part of a video --
        "part_check": "Only a part",
        "part_check_tip": "Download just a stretch of the video, such as 16:15 to 16:45",
        "part_from": "From:",
        "part_to": "To:",
        "part_tip": ("Minutes:seconds, like 16:15, or hours:minutes:seconds. An empty From "
                     "starts at the beginning, an empty To runs to the end. Only that part "
                     "is downloaded. Video in MKV starts at the nearest keyframe, a moment "
                     "early; MP4 and audio start exactly."),
        "part_summary": "Saves {start}–{end}, {length} long",
        "part_summary_open": "Saves from {start} to the end",
        "part_bad_time": "“{text}” isn't a time - write it as minutes:seconds, like 16:15.",
        "part_empty": "Enter where the part starts, where it ends, or both.",
        "part_start_late": "The part starts after the video ends ({length}).",
        "part_order": "The part has to end after it starts.",
        "part_invalid_title": "Can't download that part",
        "part_live": "A part can't be cut from a live stream.",

        # -- transcript --
        "transcript_lang": "Language:",
        "transcript_format": "Format:",
        "transcript_txt": "Plain text - one flowing transcript",
        "transcript_srt": "SRT - timed subtitles",
        "transcript_vtt": "WebVTT - timed subtitles",
        "transcript_auto": "{code} (automatic)",
        "transcript_manual": "{code} - written by people",
        "transcript_original": "{code} - original, automatic",
        "transcript_original_any": "Each video's own language (automatic)",
        "transcript_translated": "{code} - automatic translation",
        "transcript_none": "This video has no transcript.",

        # -- destination --
        "save_to": "Save to:",
        "change": "Change…",
        "choose_dir": "Save downloads to",

        # -- actions --
        "download": "Download",
        "cancel": "Cancel",
        "show_in_folder": "Show in folder",

        # -- queue and several at once --
        # Counted strings hold one form per plural; see tn().
        "queue_add": "Add to queue",
        "download_n": ("Download {count} video", "Download {count} videos"),
        "queue_add_n": ("Add {count} video to the queue", "Add {count} videos to the queue"),
        "download_links": ("Download {count} link", "Download {count} links"),
        "queue_add_links": ("Add {count} link to the queue", "Add {count} links to the queue"),
        "batch_title": ("{count} link", "{count} links"),
        "batch_note": ("Each one downloads with the settings below, one after another. "
                       "A playlist link brings all its videos."),
        "read_one_link": "Fetch reads one link at a time; several links download as they are.",
        "playlist_this": "Just this video",
        "playlist_whole": ("Whole playlist - {count} video", "Whole playlist - {count} videos"),
        "playlist_name": "“{title}”",
        "playlist_videos": ("{count} video", "{count} videos"),
        "playlist_label": "Playlist",
        "part_one_video": "A part is cut from one video, so it isn't offered for several at once.",
        "queue_title": "Downloads",
        "queue_summary": "{done} of {total} done",
        "queue_waiting": "Waiting",
        "queue_remove": "Remove",
        "queue_retry": "Try again",
        "queue_clear": "Clear finished",
        "queue_cancel_all": "Cancel all",
        "queue_cancel_all_ask": "Stop the download in progress and remove everything still waiting?",
        "queued_n": ("Added {count} download to the queue", "Added {count} downloads to the queue"),
        "quit_busy_title": "Downloads not finished",
        "quit_busy_body": ("{count} download hasn't finished. Quit anyway? It will be lost.",
                           "{count} downloads haven't finished. Quit anyway? They will be lost."),
        "summary_best": "best quality",
        "summary_up_to": "up to {height}p",
        "summary_kbps": "{kbps} kbps",
        "summary_original": "{code}, original",
        "summary_original_any": "original language",

        # -- updates --
        "menu_updates_auto": "Check for updates automatically",
        "menu_updates_now": "Check for updates now…",
        "update_checking": "Checking for updates…",
        "update_title": "Update available",
        "update_none_title": "No update",
        "update_latest": "You have the newest version, DLPizer {version}.",
        "update_available": "DLPizer {new} is available - you have {current}.",
        "update_changes": "What's new:",
        "update_ask": ("Update now? DLPizer downloads it ({size}), replaces itself and starts "
                       "again. Your settings stay as they are."),
        "update_ask_plain": ("Update now? DLPizer downloads it, replaces itself and starts "
                             "again. Your settings stay as they are."),
        "update_ask_page": "Open the page to download it?",
        "update_now": "Update and restart",
        "update_later": "Not now",
        "update_open_page": "Open download page",
        "update_downloading": "Downloading DLPizer {version}…",
        "update_after_downloads": "DLPizer {version} is out - you'll be asked once the downloads finish.",
        "update_restart_failed": "DLPizer {version} is installed. Start it again to use it.",
        "update_check_failed_title": "Couldn't check for updates",
        "update_check_failed": "GitHub couldn't be reached: {error}",
        "update_failed_title": "Update failed",
        "update_failed": ("DLPizer couldn't update itself: {error}\n\n"
                          "You can download the new version from the release page instead."),
        "update_incomplete": "the download was cut short",
        "update_corrupt": "the downloaded file is damaged",
        "update_bad_reply": "GitHub sent an answer DLPizer doesn't understand",
        "update_cant_write": "it can't write to {folder} ({reason})",

        # -- status bar --
        "ffmpeg_at": "ffmpeg: {path}",
        "ffmpeg_bundled": "ffmpeg: built in",
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
        "stage_Cut": "Cutting out the part",

        # -- engine errors --
        "err_file_locked": ("Windows wouldn't let DLPizer finish the file: another program kept it "
                            "open - usually antivirus or a sync app like OneDrive. Try again; if it "
                            "keeps happening, let that program skip your download folder, or save "
                            "to another folder."),
        "err_bot": ("YouTube asked this machine to confirm it isn't a bot, and stopped the "
                    "other ways DLPizer tried as well. Waiting a while or switching networks "
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
        "login_note_body": ("DLPizer načíta vaše cookies pre YouTube z prehliadača {browser} "
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

        # -- part of a video --
        "part_check": "Len časť",
        "part_check_tip": "Stiahne len úsek videa, napríklad od 16:15 do 16:45",
        "part_from": "Od:",
        "part_to": "Do:",
        "part_tip": ("Minúty:sekundy, napríklad 16:15, alebo hodiny:minúty:sekundy. Prázdne Od "
                     "znamená od začiatku, prázdne Do až do konca. Stiahne sa len táto časť. "
                     "Video v MKV začne na najbližšom kľúčovom snímku, o chvíľu skôr; MP4 a "
                     "zvuk začnú presne."),
        "part_summary": "Uloží {start}–{end}, dĺžka {length}",
        "part_summary_open": "Uloží od {start} do konca",
        "part_bad_time": "„{text}“ nie je čas – napíšte ho ako minúty:sekundy, napríklad 16:15.",
        "part_empty": "Zadajte, kde časť začína, kde končí, alebo oboje.",
        "part_start_late": "Časť začína až po konci videa ({length}).",
        "part_order": "Časť musí skončiť až po svojom začiatku.",
        "part_invalid_title": "Túto časť nemožno stiahnuť",
        "part_live": "Z priameho prenosu sa časť vystrihnúť nedá.",

        # -- prepis --
        "transcript_lang": "Jazyk:",
        "transcript_format": "Formát:",
        "transcript_txt": "Čistý text – súvislý prepis",
        "transcript_srt": "SRT – titulky s časovaním",
        "transcript_vtt": "WebVTT – titulky s časovaním",
        "transcript_auto": "{code} (automatické)",
        "transcript_manual": "{code} – napísané ľuďmi",
        "transcript_original": "{code} – pôvodné, automatické",
        "transcript_original_any": "Pôvodný jazyk každého videa (automatické)",
        "transcript_translated": "{code} – automatický preklad",
        "transcript_none": "Toto video nemá prepis.",

        # -- destination --
        "save_to": "Uložiť do:",
        "change": "Zmeniť…",
        "choose_dir": "Kam ukladať stiahnuté súbory",

        # -- actions --
        "download": "Stiahnuť",
        "cancel": "Zrušiť",
        "show_in_folder": "Zobraziť v priečinku",

        # -- queue and several at once --
        "queue_add": "Pridať do frontu",
        "download_n": ("Stiahnuť {count} video", "Stiahnuť {count} videá", "Stiahnuť {count} videí"),
        "queue_add_n": ("Pridať {count} video do frontu", "Pridať {count} videá do frontu",
                        "Pridať {count} videí do frontu"),
        "download_links": ("Stiahnuť {count} odkaz", "Stiahnuť {count} odkazy", "Stiahnuť {count} odkazov"),
        "queue_add_links": ("Pridať {count} odkaz do frontu", "Pridať {count} odkazy do frontu",
                            "Pridať {count} odkazov do frontu"),
        "batch_title": ("{count} odkaz", "{count} odkazy", "{count} odkazov"),
        "batch_note": ("Každý sa stiahne s nastaveniami nižšie, jeden po druhom. "
                       "Odkaz na playlist pridá všetky jeho videá."),
        "read_one_link": "Načítať sa dá len jeden odkaz; viac odkazov sa stiahne tak, ako sú.",
        "playlist_this": "Len toto video",
        "playlist_whole": ("Celý playlist – {count} video", "Celý playlist – {count} videá",
                           "Celý playlist – {count} videí"),
        "playlist_name": "„{title}“",
        "playlist_videos": ("{count} video", "{count} videá", "{count} videí"),
        "playlist_label": "Playlist",
        "part_one_video": "Časť sa vystrihuje z jedného videa, preto sa pri viacerých naraz neponúka.",
        "queue_title": "Sťahovanie",
        "queue_summary": "Hotovo {done} z {total}",
        "queue_waiting": "Čaká",
        "queue_remove": "Odstrániť",
        "queue_retry": "Skúsiť znova",
        "queue_clear": "Odstrániť dokončené",
        "queue_cancel_all": "Zrušiť všetko",
        "queue_cancel_all_ask": "Zastaviť prebiehajúce sťahovanie a odstrániť všetko, čo ešte čaká?",
        "queued_n": ("Do frontu pribudlo {count} sťahovanie", "Do frontu pribudli {count} sťahovania",
                     "Do frontu pribudlo {count} sťahovaní"),
        "quit_busy_title": "Sťahovanie neskončilo",
        "quit_busy_body": ("{count} sťahovanie ešte neskončilo. Ukončiť aj tak? Stratí sa.",
                           "{count} sťahovania ešte neskončili. Ukončiť aj tak? Stratia sa.",
                           "{count} sťahovaní ešte neskončilo. Ukončiť aj tak? Stratia sa."),
        "summary_best": "najlepšia kvalita",
        "summary_up_to": "do {height}p",
        "summary_kbps": "{kbps} kb/s",
        "summary_original": "{code}, pôvodné",
        "summary_original_any": "pôvodný jazyk",

        # -- aktualizácie --
        "menu_updates_auto": "Automaticky hľadať aktualizácie",
        "menu_updates_now": "Hľadať aktualizácie teraz…",
        "update_checking": "Hľadajú sa aktualizácie…",
        "update_title": "K dispozícii je aktualizácia",
        "update_none_title": "Žiadna aktualizácia",
        "update_latest": "Máte najnovšiu verziu, DLPizer {version}.",
        "update_available": "K dispozícii je DLPizer {new} – vy máte {current}.",
        "update_changes": "Čo je nové:",
        "update_ask": ("Aktualizovať teraz? DLPizer novú verziu stiahne ({size}), nahradí sa ňou "
                       "a znova sa spustí. Nastavenia zostanú tak, ako sú."),
        "update_ask_plain": ("Aktualizovať teraz? DLPizer novú verziu stiahne, nahradí sa ňou "
                             "a znova sa spustí. Nastavenia zostanú tak, ako sú."),
        "update_ask_page": "Otvoriť stránku, kde si ju stiahnete?",
        "update_now": "Aktualizovať a reštartovať",
        "update_later": "Teraz nie",
        "update_open_page": "Otvoriť stránku na stiahnutie",
        "update_downloading": "Sťahuje sa DLPizer {version}…",
        "update_after_downloads": "Vyšiel DLPizer {version} – ponúkne sa po dokončení sťahovania.",
        "update_restart_failed": "DLPizer {version} je nainštalovaný. Spustite ho znova.",
        "update_check_failed_title": "Aktualizácie sa nepodarilo zistiť",
        "update_check_failed": "GitHub sa nepodarilo kontaktovať: {error}",
        "update_failed_title": "Aktualizácia zlyhala",
        "update_failed": ("DLPizer sa nepodarilo aktualizovať: {error}\n\n"
                          "Novú verziu si môžete stiahnuť zo stránky s vydaniami."),
        "update_incomplete": "sťahovanie sa prerušilo",
        "update_corrupt": "stiahnutý súbor je poškodený",
        "update_bad_reply": "GitHub poslal odpoveď, ktorej DLPizer nerozumie",
        "update_cant_write": "nemôže zapisovať do {folder} ({reason})",

        # -- status bar --
        "ffmpeg_at": "ffmpeg: {path}",
        "ffmpeg_bundled": "ffmpeg: zabudovaný",
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
        "stage_Cut": "Vystrihovanie časti",

        # -- engine errors --
        "err_file_locked": ("Windows nedovolil aplikácii DLPizer súbor dokončiť: mal ho otvorený iný program – "
                            "zvyčajne antivírus alebo synchronizácia ako OneDrive. Skúste to znova; "
                            "ak sa to opakuje, nastavte tomu programu, aby váš priečinok na "
                            "sťahovanie vynechal, alebo ukladajte inam."),
        "err_bot": ("YouTube žiada od tohto počítača potvrdenie, že nie je robot, a zastavil "
                    "aj ostatné spôsoby, ktoré DLPizer skúsil. Zvyčajne pomôže chvíľu počkať "
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


def plural_index(count, lang=None):
    """Which form of a counted string fits: English has 1 / more, Slovak
    1 / 2-4 / 5 and up (and 0)."""
    if (lang or _current) == "sk":
        return 0 if count == 1 else 1 if 2 <= count <= 4 else 2
    return 0 if count == 1 else 1


def tn(key, count, lang=None, **fields):
    """A counted string, in the form its count takes: tn("playlist_videos", 3)."""
    lang = lang or _current
    forms = STRINGS.get(lang, {}).get(key)
    if forms is None:
        lang, forms = DEFAULT_LANGUAGE, STRINGS[DEFAULT_LANGUAGE][key]
    form = forms[min(plural_index(count, lang), len(forms) - 1)]
    return form.format(count=count, **fields)


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
