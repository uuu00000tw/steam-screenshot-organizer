# Steam Screenshot Organizer

[中文](#中文)

Put pictures into a Steam game screenshots folder, or split a folder of screenshots by game.

Download [SteamScreenshotOrganizer.exe](https://github.com/uuu00000tw/steam-screenshot-organizer/releases/latest), put it in its own folder, and open it. Settings are saved next to it in `settings.json`.

## Import screenshots

Turn bmp, jpg, jpeg, and png files into the files Steam uses for screenshots. Only pictures in the selected folder are used. Subfolders are left alone. Files whose names end in `_vr` are skipped.

1. Open **Import screenshots**.
2. Set **Image source** to the pictures you want to import.
3. Set **Game screenshots** to that game's screenshots folder. It is often `Steam\userdata\<account>\760\remote\<AppID>\screenshots`.
4. Click **Preview** and check the list. A picture is skipped when a `_vr.jpg` with the same name already exists.
5. Click **Import**.

Each picture becomes two files: `name.jpg` and `name_vr.jpg`. Files that are not jpg are converted to jpg.

If the two paths are different, the source files stay where they are. If both paths are the same folder, files that are not jpg are deleted after a successful conversion. jpg files are kept. The confirm dialog asks again before this happens.

## Sort external screenshots

File names must start with the game's App ID. The part before the first `_` has to be a number, for example `730_20240101120000_1.png`. Only files in the top level of the selected folder are moved. Files already inside a subfolder stay there. Files that do not match stay where they are.

1. Open **Sort external screenshots**.
2. Set **External screenshots** to that folder.
3. Set **Steam folder** to the Steam install folder. It is used to look up game names. If it is empty, the registry is used. If that folder has no game list, names are looked up on the Steam store.
4. Click **Preview**. A game with no name is shown as Unknown, and its folder uses the App ID.
5. Click **Sort**. Files are moved into the matching game folder.

An existing folder with the same name is reused. A second folder is not created.

## 中文

[English](#steam-screenshot-organizer)

把圖片放進 Steam 的遊戲截圖資料夾，或把一份截圖依遊戲分開。

下載 [SteamScreenshotOrganizer.exe](https://github.com/uuu00000tw/steam-screenshot-organizer/releases/latest)，放在自己的資料夾後直接打開。設定會存在同一個資料夾的 `settings.json`。

### 匯入截圖

把 bmp、jpg、jpeg、png 做成 Steam 截圖用的檔案。只看所選資料夾裡的圖片，不進子資料夾。檔名結尾是 `_vr` 的檔案會略過。

1. 打開 **Import screenshots**。
2. **Image source** 選要匯入的圖片。
3. **Game screenshots** 選遊戲的截圖資料夾。常見位置是 `Steam\userdata\<帳號>\760\remote\<AppID>\screenshots`。
4. 按 **Preview**，確認清單。已經有同名 `_vr.jpg` 的圖片會略過。
5. 按 **Import**。

每張圖會產生兩個檔案：`檔名.jpg` 和 `檔名_vr.jpg`。原本不是 jpg 的會轉成 jpg。

兩個路徑如果不同，來源檔案會留下。如果選的是同一個資料夾，轉換成功後會刪除不是 jpg 的原檔，jpg 會保留。確認視窗會再問一次。

### 分類外部截圖

檔名要以遊戲的 App ID 開頭，第一個 `_` 之前都是數字，例如 `730_20240101120000_1.png`。只處理所選資料夾最外層的檔案。已經在子資料夾裡的檔案不會動，檔名不符合的也留在原處。

1. 打開 **Sort external screenshots**。
2. **External screenshots** 選那份截圖。
3. **Steam folder** 選 Steam 安裝目錄，用來查遊戲名稱。沒填的話會讀登錄檔。這個目錄裡沒有遊戲清單時，改查 Steam 商店。
4. 按 **Preview**。查不到名稱的會顯示 Unknown，資料夾就用 App ID。
5. 按 **Sort**。檔案會移進對應的遊戲資料夾。

同名資料夾如果已經存在，會沿用，不會另外開一個。
