# ytgrab

Malá multiplatformová aplikácia na sťahovanie videa a zvuku z YouTube,
postavená na [yt-dlp](https://github.com/yt-dlp/yt-dlp) a ffmpeg.

Beží na Linuxe, Windowse aj macOS. ffmpeg aj QuickJS (behové prostredie
JavaScriptu, ktoré yt-dlp potrebuje pre YouTube) sú súčasťou balíka, takže nič
ďalšie netreba inštalovať.

*Read this in [English](README.md).*

## Stiahnutie

Zostavenú aplikáciu nájdete na stránke [Releases](../../releases):

| Systém | Súbor |
| --- | --- |
| Linux | `ytgrab-linux-x86_64` |
| Windows | `ytgrab-windows-x86_64.exe` |
| macOS (Apple Silicon) | `ytgrab-macos-arm64.zip` |
| macOS (Intel) | `ytgrab-macos-x86_64.zip` |

Na Linuxe súbor najprv označte ako spustiteľný: `chmod +x ytgrab-linux-x86_64`.

Zostavenia pre macOS a Windows **nie sú digitálne podpísané**, pretože
certifikáty stoja peniaze. Systém vás pri prvom spustení upozorní: na macOS
kliknite na aplikáciu pravým tlačidlom a vyberte *Otvoriť*, na Windowse kliknite
na *Ďalšie informácie* a potom na *Spustiť napriek tomu*.

## Jazyk

Aplikácia sa riadi jazykom systému: na slovenskom systéme sa spustí po
slovensky, inak po anglicky. Jazyk sa dá kedykoľvek prepnúť v ponuke *Jazyk* a
voľba sa zapamätá do ďalšieho spustenia. Verzia pre prehliadač sa riadi jazykom
nastaveným v prehliadači a prepína sa odkazmi v päte stránky.

## Režimy

**Video** — stiahne najlepšiu obrazovú a zvukovú stopu a spojí ich do jedného
súboru. Nedochádza k opätovnému kódovaniu; ffmpeg stopy iba prekopíruje do
kontajnera.

* *MP4* uprednostní H.264 + AAC, takže súbor sa prehrá všade. Pri niektorých
  videách vás to obmedzí pod najvyššie rozlíšenie, lebo YouTube ponúka 4K len vo
  formáte VP9/AV1.
* *MKV* si vezme tie najkvalitnejšie stopy, aké sú k dispozícii (VP9, AV1,
  Opus), a ponechá ich presne tak, ako sú. Túto možnosť zvoľte, ak chcete
  najvyššiu kvalitu.

**Zvuk (pôvodný)** — vyberie zvukovú stopu z kontajnera a uloží ju bez zmeny.
Nič sa nedekóduje ani neprekóduje, takže súbor je bit po bite ten zvuk, ktorý
poslal YouTube, zvyčajne Opus (`.opus`) alebo AAC (`.m4a`). Bezstratovejšie sa
z YouTube sťahovať nedá: samotný zdroj je stratový, ale týmto krokom sa už nič
nestratí.

**MP3** — ten istý zvuk dekóduje a zakóduje do MP3. Ide o ďalšiu stratovú
konverziu, takže výsledok je vždy horší ako *Zvuk (pôvodný)*; použite ju len
vtedy, keď niečo vyžaduje priamo MP3. Najlepšie nastavenie je V0 (VBR);
192 kb/s CBR je rozumná voľba, ak vám ide o kompatibilitu.

Oba zvukové režimy vedia do súboru vložiť náhľadový obrázok ako obal a k tomu
názov a ďalšie údaje.

**Prepis** — namiesto videa uloží stopu s titulkami. Nesťahuje sa nič okrem
titulkov, takže je hotový za pár sekúnd. Najskôr sa ponúkajú ručne vytvorené
titulky, tie automatické od YouTubu sú označené ako *(automatické)*.

* *Čistý text* prevedie titulky na súvislý prepis. Časovanie sa vynechá a
  opakované riadky, ktoré vznikajú pri rolovaní automatických titulkov, sa
  zlúčia. Tento formát nepotrebuje ffmpeg.
* *SRT* a *WebVTT* časovanie zachovajú, takže vzniknú plnohodnotné súbory
  s titulkami.

## Spustenie zo zdrojového kódu

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Na Linuxe môžu chýbať aj runtime knižnice Qt (`libegl1`, `libxkbcommon-x11-0`
a podobne); úplný zoznam nájdete v riadku s `apt-get` v súbore
`.github/workflows/build.yml`.

`python main.py --selftest` vypíše nájdené verzie a overí, že ffmpeg aj
behové prostredie JavaScriptu sú prítomné a spustiteľné — hodí sa, keď sa
zostavená aplikácia správa čudne.

## Linux: položka v ponuke aplikácií

`packaging/install-linux.sh` skopíruje zostavený súbor do `~/.local/bin`,
vykreslí ikonu vo veľkostiach, aké očakáva téma ikon, a zapíše súbor `.desktop`,
takže sa ytgrab objaví v ponuke aplikácií. Všetko zostáva pod `~/.local`, takže
nie sú potrebné práva správcu.

```bash
pyinstaller --noconfirm --clean ytgrab.spec   # ak ste ešte nezostavovali
./packaging/install-linux.sh
```

Nainštalovaný súbor je kópiou aktuálneho stavu, takže po každom novom zostavení
skript spustite znova.

## Zostavenie

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean ytgrab.spec
```

Lokálne zostavenie pribalí QuickJS, ak ho nájde: buď `qjs` v premennej PATH,
alebo pripnuté vydanie stiahnuté príkazom
`python packaging/fetch_qjs.py linux-x86_64 qjsbin` a odovzdané ako
`YTGRAB_QJS=qjsbin/qjs` (ciele: `linux-x86_64`, `windows-x86_64`,
`darwin-arm64`, `darwin-x86_64`). Bez neho sťahovanie z YouTube závisí od
programu deno alebo node nainštalovaného v počítači.

Aplikáciu nemožno zostaviť pre iný systém, než na akom bežíte: `.exe` pre
Windows treba zostaviť na Windowse a `.app` pre macOS na macOS. Workflow
GitHub Actions urobí všetky štyri zostavenia na serveroch GitHubu — vydanie
vytvoríte pushnutím tagu ako `v1.0.0`, prípadne workflow spustíte ručne v karte
Actions.

## Voliteľne: verzia pre prehliadač

`app.py` je staršia verzia toho istého nástroja, ktorá namiesto okna zobrazí
webové rozhranie na adrese `127.0.0.1:5000`. Používa rovnaké jadro na sťahovanie.

```bash
pip install -r requirements-web.txt
python app.py
```

## Poznámky

* Odkazy na playlist sa vyhodnotia ako prvé video v ňom; celé playlisty sa
  hromadne nesťahujú.
* Sťahuje sa z vášho počítača a vášho pripojenia. Na cloudovom serveri to
  zvyčajne zlyhá, pretože YouTube dôsledne preveruje požiadavky z rozsahov IP
  adries patriacich dátovým centrám.
* Používajte len na obsah, ktorý máte právo stiahnuť. Podmienky používania
  služby YouTube sťahovanie obmedzujú.
