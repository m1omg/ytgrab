# DLPizer

Malá multiplatformová aplikácia na sťahovanie videa a zvuku z YouTube,
postavená na [yt-dlp](https://github.com/yt-dlp/yt-dlp) a ffmpeg.

Beží na Linuxe, Windowse, macOS aj Androide (7.0 a novšom). ffmpeg aj QuickJS
(behové prostredie JavaScriptu, ktoré yt-dlp potrebuje pre YouTube) sú
súčasťou balíka, takže nič ďalšie netreba inštalovať.

Do verzie 1.6.0 sa DLPizer volal **ytgrab**. Nastavenia sa prenesú; na Androide
sa hotové súbory odteraz ukladajú do **Download/DLPizer** (staré zostávajú
v Download/ytgrab) a na Linuxe `install-linux.sh` nahradí starú položku v ponuke.
Verzie 1.5.0 a 1.5.1 hľadajú súbory vydania pod starým názvom, preto namiesto
samočinnej aktualizácie ponúknu stránku na stiahnutie – stačí raz stiahnuť 1.6.0
a ďalšie aktualizácie sú opäť automatické.

*Read this in [English](README.md).*

## Stiahnutie

Zostavenú aplikáciu nájdete na stránke [Releases](../../releases):

| Systém | Súbor |
| --- | --- |
| Linux | `DLPizer-linux-x86_64` |
| Windows | `DLPizer-windows-x86_64.exe` |
| macOS (Apple Silicon) | `DLPizer-macos-arm64.zip` |
| macOS (Intel) | `DLPizer-macos-x86_64.zip` |
| Android (väčšina telefónov) | `DLPizer-android-arm64.apk` |
| Android (staršie 32-bitové telefóny) | `DLPizer-android-arm32.apk` |
| Android (neviete, Chromebooky) | `DLPizer-android-universal.apk` |

Na Linuxe súbor najprv označte ako spustiteľný: `chmod +x DLPizer-linux-x86_64`.
Potrebuje glibc 2.39 alebo novšiu: Ubuntu 24.04, Debian 13, LMDE 7, Fedora 40,
Linux Mint 22 a novšie, alebo priebežne aktualizovanú distribúciu ako Arch,
CachyOS či openSUSE Tumbleweed (vašu verziu ukáže `ldd --version`).

Na Androide otvorte stiahnutý súbor APK a keď sa systém spýta, povoľte
prehliadaču alebo správcovi súborov inštalovať aplikácie. Novšie verzie sa
nainštalujú priamo cez staršie. Univerzálny APK spustí každý telefón
s Androidom 7.0+; verzia arm64 je tá istá aplikácia s menej než polovičnou
veľkosťou.

Zostavenia pre macOS a Windows **nie sú digitálne podpísané**, pretože
certifikáty stoja peniaze. Systém vás pri prvom spustení upozorní: na macOS
kliknite na aplikáciu pravým tlačidlom a vyberte *Otvoriť*, na Windowse kliknite
na *Ďalšie informácie* a potom na *Spustiť napriek tomu*.

## Aktualizácie

Aplikácia pár sekúnd po spustení zistí, či nevyšla novšia verzia. Ak áno,
povie, čo je nové, a ponúkne *Aktualizovať a reštartovať*: novú verziu stiahne,
overí podľa kontrolného súčtu SHA-256 z vydania, nahradí ňou starú a znova sa
spustí, s nastaveniami tak, ako boli. *Teraz nie* sa spýta nabudúce. Kým
prebieha sťahovanie, počká, kým sa dokončí.

*Možnosti → Hľadať aktualizácie teraz* sa pozrie hneď a *Automaticky hľadať
aktualizácie* kontrolu pri spustení vypne. Ak sa aplikácia nemôže sama nahradiť,
napríklad v priečinku, kam nemôže zapisovať, alebo na Macu spustená priamo zo
stiahnutého súboru, ponúkne namiesto toho stránku s vydaním.

Na Androide aktualizáciu ponúkne karta navrchu; APK pre váš telefón sa stiahne
a overí rovnako a Android sa pred inštaláciou spýta (prvýkrát aj na to, či
aplikácii DLPizer dovolíte inštalovať aplikácie).

## Zapamätané nastavenia

Čo sťahujete (video, zvuk, MP3 alebo prepis), rozlíšenie, kontajner, zvuková
stopa, dátový tok MP3, formát prepisu a vkladanie obalu sa zapamätajú do
ďalšieho spustenia – v aplikácii pre počítač, na Androide aj vo verzii pre
prehliadač – a v aplikácii pre počítač aj priečinok na sťahovanie. Rozlíšenie funguje ako strop: pri zvolenom 1080p sa video,
ktoré má najviac 720p, stiahne v 720p a ďalšie opäť v 1080p.

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
titulkov, takže je hotový za pár sekúnd. V zozname sú:

* titulky *napísané ľuďmi*, ak ich video má;
* *pôvodné* – automatické titulky YouTubu v jazyku, ktorým sa vo videu hovorí;
* *automatické preklady* YouTubu: najprv slovenčina a angličtina, potom
  všetky ďalšie jazyky, do ktorých YouTube prekladá.

Aplikácia vyberie svoj jazyk, ak sa dá, potom angličtinu, a pôvodné titulky
uprednostní pred prekladom – anglické video teda dostane pôvodné anglické
titulky (`en-orig`) a v slovenčine je vybraný slovenský preklad, pôvodné titulky
sú o riadok vyššie. Pri viacerých videách naraz je tu aj *Pôvodný jazyk
každého videa*.

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

Ak ffmpeg nedokáže časť stiahnuť sám – niektoré servery to odmietnu – DLPizer
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
Nie je to captcha, ktorú by sa dalo vyriešiť: DLPizer to v tichosti skúsi znova
cez iných klientov YouTube, ktorí väčšinou prejdú, a chybu ukáže, až keď
zastaví aj tých.

Ak sa to na počítači opakuje, prihláste sa do YouTube v prehliadači a vyberte
ho v ponuke
**Možnosti → Použiť prihlásenie do YouTube z prehliadača**. DLPizer potom z neho
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
  DLPizer; odkaz sa vyplní a hneď načíta.
* Sťahovanie beží ďalej aj na pozadí, jedno po druhom, s priebehom, počtom
  čakajúcich a tlačidlami *Zrušiť* / *Zrušiť všetko* v upozornení.
* Hotové súbory sa uložia do priečinka **Download/DLPizer**, odkiaľ ich otvorí
  ktorýkoľvek prehrávač, správca súborov či tlačidlo *Zdieľať*.
* Riadi sa jazykom telefónu (angličtina alebo slovenčina) a na Androide 13+
  sa dá jazyk pre DLPizer nastaviť samostatne v nastaveniach systému.

Načítanie prvého videa po spustení aplikácie trvá o pár sekúnd dlhšie než na
počítači: telefón rieši JavaScriptovú úlohu YouTube sám a staršie telefóny sú
pri tom pomalšie.

## Linux: položka v ponuke aplikácií

`packaging/install-linux.sh` skopíruje zostavený súbor do `~/.local/bin`,
vykreslí ikonu vo veľkostiach, aké očakáva téma ikon, a zapíše súbor `.desktop`,
takže sa DLPizer objaví v ponuke aplikácií. Všetko zostáva pod `~/.local`, takže
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
