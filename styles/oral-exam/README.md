# 血專口試快答 卡片設計規範

`01_血專口試快答` 牌組（note type `血專口試快答 (Basic)`）的版面、配色與寫法。
目標：**口試現場的節奏**——一眼看到題目，翻面先看「要講出的關鍵字」，再看「理想答案」，
延伸內容放後面、必要時摺疊。

| 檔案 | 用途 |
| --- | --- |
| `style.css` | note type 的 Styling（淺色＋深色） |
| `front.html` / `back.html` | Front / Back template |
| `make_fields.py` | 從 JSON 產生欄位 HTML；`--add` 直接加卡、`--preview` 產生預覽頁 |
| `example.json` | 三張真實卡片：短卡、長卡（自動摺疊）、及格線與紅旗 |

在 repo 根目錄執行 `make preview` 會產生 `preview.html`（不進版控）：左欄跟隨系統主題，右欄是 `.nightMode`。
用瀏覽器打開它、切換系統深淺色即可比對兩種模式。

## 1. 卡片結構

```
Front ─ .qid     110-001・Q1                  小字、灰、字距寬：題號
        .topic   von Willebrand disease 的…   次要灰：這組題目的主題
        .ask     門診來了一個 25 歲女生…？     22px 粗體：題目本身（主角）
─────── hr#answer
Back  ─ .kw      關鍵字（琥珀色色塊）            先看：口試要「講到」的詞
        .ans     理想答案                      主體：一段話或 <ul>
        .fu      追問（虛線分隔）               考官的下一句
        .note    主考官想確認的是：…（斜體灰）    這題在測什麼
        details  素材註記等延伸（永遠摺疊）
```

Template 只負責骨架，**樣式 class 寫在欄位 HTML 裡**：

- Front：`{{Front}}`
- Back：`{{FrontSide}}<hr id=answer>{{Back}}`

所以同一個 note type 也能裝不同變體（例如沒有關鍵字、答案是條列）。

### 兩種卡

| 類型 | qid | 理想答案 | 其他 |
| --- | --- | --- | --- |
| 問答卡 | `110-001・Q1`…`Q5` | 一段 `<p>` | 關鍵字、追問、主考官想確認 |
| 及格線與紅旗 | `110-001・及格線與紅旗` | `<ul>`：「及格：…」＋多條「<span class="flag">紅旗</span>：如果他說…」 | 無關鍵字；tag 加 `及格線紅旗` |

Tag 慣例：`<年度> <題號> <領域> 口試快答`，例如 `110 110-001 凝血 口試快答`。

## 2. 視覺原則

1. **一個主角**：只有 `.ask`（22px、600）和內文（20px）是大字；其他標籤都是 13px、字距 `.1em` 的「小標」，
   讓眼睛直接落在內容上。
2. **顏色只用來分層，不用來裝飾**：
   - 琥珀（`--kw-*`）＝關鍵字，唯一有底色的區塊，翻面第一眼就看到。
   - 藍（`--label`）＝「理想答案／追問」小標與摺疊標題。
   - 橘（`--flag`）＝紅旗。
   - 其餘全是灰階。
3. **分隔線分輕重**：題目與答案之間 2px 實線；答案內部（追問、摺疊）用 1px 虛線。
4. **閱讀舒適**：行高 1.75、左對齊、中文字型優先 `PingFang TC → Noto Sans TC → Microsoft JhengHei`。

## 3. 深淺色模式

所有顏色都是 `.card` 上的 CSS 變數；深色只換變數值，元件規則寫一次就好。深色由兩種訊號觸發：

| 環境 | 深色怎麼來 |
| --- | --- |
| Anki 桌面版、AnkiDroid、AnkiMobile | App 開夜間模式時會加 `.nightMode` / `.night_mode` class |
| **AnkiWeb** | **不會加任何 class**、自己的頁面也永遠是白底；只能靠 `@media (prefers-color-scheme: dark)` 跟隨系統 |

原本線上的 CSS 只認 `.nightMode`，所以在 AnkiWeb 上永遠是淺色；`style.css` 補上了 media query。
在 AnkiWeb 深色模式下，卡片會是「白頁面上的一塊深色卡」，因此 `.card` 自帶背景與內距。

| Token | 淺色 | 深色 | 用途 |
| --- | --- | --- | --- |
| `--fg` / `--bg` | `#1b1b1f` / `#fdfdfb` | `#e6e6ea` / `#16171a` | 內文 / 卡片底 |
| `--muted` | `#8a8a94` | `#8a8a94` | 題號、摺疊箭頭 |
| `--sub` | `#5c5c68` | `#a0a0ac` | 主題 |
| `--note` | `#6a6a76` | `#9a9aa6` | 主考官想確認 |
| `--line` | `#d8d8de` | `#35363c` | 分隔線 |
| `--kw-bg` / `--kw-bar` / `--kw-label` | `#fff6e0` / `#e0a800` / `#96700a` | `#2c2513` / `#c9971c` / `#d9ab2e` | 關鍵字區塊 |
| `--label` | `#4a6fa5` | `#7fa3d8` | 小標、摺疊標題 |
| `--flag` | `#b5651d` | `#e0a060` | 紅旗 |

新增顏色時：在**三處**（淺色 `.card`、`.nightMode` 區塊、`@media` 區塊）各加一個變數，元件裡只用 `var(--x)`。

> 未實測：桌面版若「App 設淺色、作業系統設深色」，media query 可能讓卡片變深色。
> 遇到時把 Anki 的主題設成「跟隨系統」即可一致。

## 4. 長答案：`<details>` 摺疊

沿用「哲學基礎」（醫學知識概念卡）的摺疊樣式：沒有原生三角形，改用 `▸`，展開時旋轉 90°，
摺疊標題與小標同一種藍色小字。

```html
<details class="fu"><summary>追問</summary><div class="body">…</div></details>
```

規則（`make_fields.py` 自動套用）：

- **關鍵字、理想答案永遠展開**——那是口試要講出來的東西，不能藏。
- 背面純文字超過 `FOLD_AT = 500` 字時，**追問**與**主考官想確認**改成摺疊。
  （現有卡背面 285–948 字；一般問答卡維持原樣，只有長卡會摺。）
- 補充資料（素材註記、出處、爭議）放 `details` 陣列，**一律摺疊**。

## 5. 寫卡

```bash
# 預覽（輸出 HTML，不動帳號）
python3 styles/oral-exam/make_fields.py styles/oral-exam/example.json

# 產生預覽頁（= make preview）
python3 styles/oral-exam/make_fields.py styles/oral-exam/example.json --preview styles/oral-exam/preview.html

# 加進牌組（用 repo 根目錄的 anki.py，note type 固定為「血專口試快答 (Basic)」）
python3 styles/oral-exam/make_fields.py cards.json --add -d "01_血專口試快答::110::110-001 …"
```

JSON 欄位：`qid`、`topic`、`ask`、`keywords`（陣列或字串）、`answer`（字串 → `<p>`，陣列 → `<ul>`）、
`followup`、`note`、`details`（`[{summary, body}]`）、`tags`。值會直接當 HTML 插入，
所以可以用 `<b>`、`<i>`、`<span class="flag">`。

寫作要點（從現有卡歸納）：

- `.ask` 用**口試官的口吻**出題，帶情境（「門診來了一個 25 歲女生…你從哪一步開始？」）。
- 關鍵字是「要講到的詞」，不是摘要；英文術語保留原文。
- 理想答案先給結論再給理由；易混淆處直接點破（「理由是『更穩』，不是『更準』」）。
- 追問附答案，寫在括號裡：「（答：…）」。
- 「主考官想確認的是：…」同一題組的每張卡用同一句，串起整組題目。

## 6. 套用到 Anki

AnkiWeb 的網頁 API 不能改 note type 的模板與 CSS，請在桌面版：
**工具 → 管理筆記類型 → 血專口試快答 (Basic) → 卡片…**，
把 `front.html`、`back.html`、`style.css` 分別貼進正面模板、背面模板、樣式，再同步。
既有卡片的欄位不用改——新 CSS 完全相容舊的 `.kw/.ans/.fu/.note` 寫法。
