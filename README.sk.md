# ytgrab

Malá multiplatformová aplikácia na sťahovanie videa a zvuku z YouTube,
postavená na [yt-dlp](https://github.com/yt-dlp/yt-dlp) a ffmpeg.

Beží na Linuxe, Windowse, macOS aj Androide (7.0 a novšom). ffmpeg aj QuickJS
(behové prostredie JavaScriptu, ktoré yt-dlp potrebuje pre YouTube) sú
súčasťou balíka, takže nič ďalšie netreba inštalovať.

*Read this in [English](README.md).*

## Stiahnutie

Zostavenú aplikáciu nájdete na stránke [Releases](../../releases):

| Systém | Súbor |
| --- | --- |
| Linux | `ytgrab-linux-x86_64` |
| Windows | `ytgrab-windows-x86_64.exe` |
| macOS (Apple Silicon) | `ytgrab-macos-arm64.zip` |
| macOS (Intel) | `ytgrab-macos-x86_64.zip` |
| Android (väčšina telefónov) | `ytgrab-android-arm64.apk` |
| Android (staršie 32-bitové telefóny) | `ytgrab-android-arm32.apk` |
| Android (neviete, Chromebooky) | `ytgrab-android-universal.apk` |

Na Linuxe súbor najprv označte ako spustiteľný: `chmod +x ytgrab-linux-x86_64`.

Na Androide otvorte stiahnutý súbor APK a keď sa systém spýta, povoľte
prehliadaču alebo správcovi súborov inštalovať aplikácie. Novšie verzie sa
nainštalujú priamo cez staršie. Univerzálny APK spustí každý telefón
s Androidom 7.0+; verzia arm64 je tá istá aplikácia s menej než polovičnou
veľkosťou.

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

## Len časť

Zaškrtnite **Len časť** (v Androide prepínač *Len časť*) a zadajte, kde časť
začína a končí, ako minúty:sekundy – napríklad **Od** `16:15` **Do** `16:45`.
Pri dlhých videách aj hodiny:minúty:sekundy (`1:02:03`) a namiesto dvojbodky
poslúži aj bodka či čiarka (`16.15`), čo sa hodí na číselnej klávesnici
telefónu. Prázdne *Od* znamená od začiatku, prázdne *Do* až do konca.

Stiahne sa len táto časť, nie celé video, a názov súboru hovorí, ktorá časť to
je: `… (16m15s-16m45s).mp3`. Zvuk a video v MP4 začnú presne tam, kde ste
chceli. MKV vie začať video len na kľúčovom snímku, takže časť v MKV môže začať
o chvíľu (zvyčajne o sekundu-dve) skôr.

Ak ffmpeg nedokáže časť stiahnuť sám – niektoré servery to odmietnu – ytgrab
stiahne celé video a časť z neho vystrihne, takže to funguje aj tak, len
pomalšie.

## Viac naraz

Sťahovania idú do zoznamu a bežia **jedno po druhom** v poradí – keď ich beží
viac naraz, YouTube sa skôr pýta, či nie ste robot. Kým jedno beží, tlačidlo
znie **Pridať do frontu**: vyberte ďalšie video a jeho nastavenia a počká na
svoj rad s nastaveniami, ktoré ste mu zvolili.

* **Viac odkazov:** vložte do poľa pre odkaz zoznam odkazov (každý na vlastný
  riadok alebo oddelené medzerou), v Androide ich môžete zdieľať viac naraz.
  Pole ukáže, koľko ich je, a **Stiahnuť N odkazov** ich všetky zaradí s
  nastaveniami pod ním.
* **Playlisty:** načítajte odkaz na video, ktoré je v playliste, a vyberte
  *Len toto video* alebo *Celý playlist*. Odkaz len na playlist (alebo na
  videá kanála) stiahne celý. Odkaz na playlist medzi viacerými odkazmi
  takisto pridá všetky jeho videá.
* Každé sťahovanie v zozname má vlastný priebeh a tlačidlá: **Zrušiť** to,
  ktoré beží, **Odstrániť** to, ktoré čaká, **Skúsiť znova** po chybe,
  **Zobraziť v priečinku** (v Androide *Otvoriť* a *Zdieľať*) po uložení.
  **Zrušiť všetko** všetko zastaví, **Odstrániť dokončené** zoznam upratá.

Keď majú nastavenia spoločné viaceré videá, rozlíšenie je strop: *1080p*
vezme z každého videa najlepšie do 1080p. *Len časť* je pre jedno video, preto
je pri viacerých odkazoch a celých playlistoch vypnutá.

## „Potvrďte, že nie ste robot“

YouTube niekedy zastaví pripojenie, ktorému nedôveruje, a žiada prihlásenie.
Nie je to captcha, ktorú by sa dalo vyriešiť: ytgrab to v tichosti skúsi znova
cez iných klientov YouTube, ktorí väčšinou prejdú, a chybu ukáže, až keď
zastaví aj tých.

Ak sa to na počítači opakuje, prihláste sa do YouTube v prehliadači a vyberte
ho v ponuke
**Možnosti → Použiť prihlásenie do YouTube z prehliadača**. ytgrab potom z neho
v tomto počítači načíta vaše cookies pre YouTube a pošle ich výhradne službe
YouTube. YouTube môže dočasne obmedziť účet, ktorý veľa sťahuje, preto je
bezpečnejší vedľajší účet. Vo Windowse sa z prehliadačov rodiny Chrome cookies
väčšinou načítať nedajú; z Firefoxu áno.

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

## Android

Aplikácia pre Android robí to isté ako tá pre počítač – rovnaké režimy,
možnosti aj sťahovací engine – len s obrazovkou prispôsobenou telefónu:

* V aplikácii YouTube (alebo v prehliadači) video **zdieľajte** a vyberte
  ytgrab; odkaz sa vyplní a hneď načíta.
* Sťahovanie beží ďalej aj na pozadí, jedno po druhom, s priebehom, počtom
  čakajúcich a tlačidlami *Zrušiť* / *Zrušiť všetko* v upozornení.
* Hotové súbory sa uložia do priečinka **Download/ytgrab**, odkiaľ ich otvorí
  ktorýkoľvek prehrávač, správca súborov či tlačidlo *Zdieľať*.
* Riadi sa jazykom telefónu (angličtina alebo slovenčina) a na Androide 13+
  sa dá jazyk pre ytgrab nastaviť samostatne v nastaveniach systému.

Načítanie prvého videa po spustení aplikácie trvá o pár sekúnd dlhšie než na
počítači: telefón rieši JavaScriptovú úlohu YouTube sám a staršie telefóny sú
pri tom pomalšie.

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
GitHub Actions urobí všetky zostavenia na serveroch GitHubu. Keď sa do `main`
zlúči nové číslo verzie v `ytgrab/__init__.py`, vydanie sa vytvorí samo; funguje
aj pushnutie tagu ako `v1.0.0` alebo ručné spustenie v karte Actions.

### Android

`android/` je projekt pre Gradle (Kotlin, Jetpack Compose), ktorý cez
[Chaquopy](https://chaquo.com/chaquopy/) spúšťa ten istý `ytgrab/core.py`.
Potrebuje ffmpeg a QuickJS pre Android pre každú architektúru telefónov,
zostavené pomocou NDK:

```bash
export ANDROID_NDK_HOME=/cesta/k/ndk   # r29
for abi in arm64-v8a armeabi-v7a x86 x86_64; do
  packaging/android/build_natives.sh "$abi" "android/natives/$abi"
done
cd android && ./gradlew assembleRelease
```

Vydania sú podpísané kľúčom z dvoch tajomstiev (secrets) repozitára, aby sa
každá verzia nainštalovala cez predchádzajúcu: `ANDROID_KEYSTORE_BASE64`
(úložisko kľúčov v base64) a `ANDROID_KEYSTORE_PASSWORD`. Bez nich zlyhá časť
workflowu pre Android a vydanie vyjde len so zostaveniami pre počítač.
Úložisko kľúčov si odložte: telefón prijme len aktualizácie podpísané ním.

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
