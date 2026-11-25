# Thirdwave Corporation (株式会社サードウェーブ): research brief for a Planning Department simulation

*Prepared 2026-11-24 from public sources only. The simulation's "today" is assumed to be late November 2026.*

**How to read this brief**
- **[F]** = fact from a public source. The number in brackets, e.g. [S3], points to the Sources list at the end.
- **[A]** = assumption or estimate made for the simulation. It is plausible, but it is not a published number. Do not present [A] items as real company data.
- Thirdwave is **not listed on a stock exchange**, so it does not publish detailed financials. Unit volumes, margins, inventory, and department names are not public. Those numbers are all [A].

> **Important correction to a common assumption:** Thirdwave's fiscal year ends in **July**, not March [S2][S5]. FY = August to July. The half-year closes at the **end of January**, which is why Dospara runs a "半期決算セール" (half-year closing sale) every January [S27]. Industry statistics (JEITA) and most Japanese companies use April to March, so the simulation has to handle both calendars.

---

## Key numbers

| Item | Value | Type | Source |
|---|---|---|---|
| Founded | 23 March 1984, Akihabara (started as a PC parts shop) | F | S3, S4 |
| HQ | Sumitomo Fudosan Akihabara Bldg, 3-12-8 Sotokanda, Chiyoda-ku, Tokyo | F | S3 |
| Capital | ¥56.08 million | F | S3 |
| Listed? | No (private) | F | S3 |
| Fiscal year | August to July (e.g. "2025年7月期" = Aug 2024 to Jul 2025) | F | S2, S3 |
| Revenue FY2023/7 | ¥76.5B (another source gives ¥76.0B) | F | S2, S3 |
| Revenue FY2024/7 | ¥77.1B | F | S2, S3 |
| Revenue FY2025/7 | ¥92.6B (about +20% YoY; Windows 10 replacement year) | F | S2, S3 |
| Revenue target | ≥ ¥100B (first said for FY2027/7, later for FY2026/7) | F | S6, S8 |
| Revenue FY2026/7 (Aug 2025 to Jul 2026) | Not found in public sources. Simulation value: **¥101B** (target reached on price inflation, with fewer units) | A | — |
| Employees | 1,113 (July 2025); average age 36 | F | S3 |
| Dospara stores | 47 (Aug 2024) → 43 (Sep 2025) | F | S6, S8 |
| Digital Dock repair shops | 15 (Sep 2025); new ones opened inside Dospara stores in 2026 | F | S8, S24 |
| Enterprise share of sales | "a bit over 10%" (2024); target about 30% | F | S6 |
| Factory / logistics | Ayase HQ factory (production + logistics), Ebina office (development + support), Hiratsuka logistics/call centre, all in Kanagawa | F | S7, S8 |
| Fastest shipping | "within 2 days of order" (2025); enterprise PCs "from 3 days" | F | S8, S9 |
| Planned AI investment | about ¥5B over 3 years; about 70 AI engineers hired from India | F | S10, S9 |
| PC units sold per year | **about 300,000** (about 25,000 per month; December, January and July peaks of about 35,000) | A | — |
| Gross margin on BTO PCs | **about 20–24%** normally, squeezed to **about 15–18%** in the 2026 memory spike | A | — |
| Finished-goods + parts inventory | **about ¥9–11B** (about 6 weeks of cost of sales) | A | — |
| Planning department headcount | **about 25** across 経営企画 / 商品企画 / 需給 (demand-supply) | A | — |

---

## 1. Company profile

### Identity and history [F]
- **1984**: founded in Akihabara as a PC parts shop called "Thirdwave" [S4]. The founder was a former trading-company employee who imported US PCs and parts [S11].
- **1992**: store renamed **DOS/V Paradise (DOS/Vパラダイス)**; started selling DOS/V PCs [S4].
- **2003**: renamed **Dospara (ドスパラ)**, the nickname people already used. The same year it began assembling and shipping PCs from its distribution centre [S4].
- **2004**: **GALLERIA** gaming PC brand launched. **2007**: **raytrek** creator PC brand launched [S4].
- **2023**: brands consolidated into three: GALLERIA, raytrek, THIRDWAVE. The older Monarch and THIRDWAVE Pro brands were folded in [S6].
- **Aug 2024**: Akiya Ida (井田晶也), ex-Intel, became President & COO. He was the first president from outside the founding family. Kensuke Ozaki (尾崎健介) became Chairman & CEO [S6].
- **Feb 2025**: **Masaki Nagai (永井正樹)** became Director, President & COO [S8][S10]. Nagai joined in April 1993 as a shop clerk at the Akihabara store. He became store manager within a year, then moved to HQ, where he worked in purchasing, product planning, budgeting, business planning, factories and HR [S8][S10][S11].
- Kensuke Ozaki is still listed as CEO (代表) [S3]. He has also owned a pro esports team [S12].

### Leadership style (useful for character design) [F]
- Nagai's motto is **凡事徹底** (do the basics thoroughly: greetings, saying "thank you" and "sorry"). His first message to staff was 「当たり前のことをやろう」 ("Let's do the obvious things properly") [S8][S10].
- He brought staff back to the office after COVID, saying that with text-only communication you cannot tell whether an instruction was understood [S10].
- AI is used for analysis, but **leaders make the final call**. Example: new store sites are visited in person before approval. "Before giving up, try every route, not just most of them." [S10]
- Self-description: 「新しいことをやらないと気が済まない会社」 ("a company that can't stand not trying new things") [S8].
- Retail is run by **Yasuhiro Osada (長田康裕)**, Director & Senior Executive Officer, Retail Business Division (リテール事業統括本部) [S13].

### Business units [F]
From the recruiting profile [S3]:
1. Planning, manufacturing and wholesale of computers (GALLERIA, raytrek, THIRDWAVE)
2. **Dospara** PC retail chain (stores + dospara.co.jp)
3. **Digital Dock (デジタルドック)**: repair and smartphone/PC support shops for any maker, mostly inside Dospara stores
4. Enterprise ICT equipment and services (the corporate sales division had more than 150 staff in 2024, organised by industry, plus distributor/SIer partner teams) [S6]
5. Esports events and creator support (e.g. the former LFS Ikebukuro esports arena, now closed; high-school esports championship; AI Festival / AI Art Grand Prix) [S8][S10]
6. Fulfillment services

Subsidiaries are not clearly listed in current public profiles [S3]. FY2021 revenue was reported as a group figure [S2].

### Production, logistics and service [F]
- **Product planning happens at Akihabara HQ.** Development, production and QC are at **Ebina (海老名事業所)** and the **Ayase factory (綾瀬工場)**. Shipping goes nationwide from the **Hiratsuka logistics centre (平塚)**. All three sites are in Kanagawa [S7].
- In 2025 Thirdwave described the sites as: Ayase HQ factory = production and logistics hub; Hiratsuka = sales and call centre; Ebina = development and support. It said it can **ship within two days of an order** [S8].
- Enterprise pitch: strong CPU/GPU procurement allows shipping to spec in **as little as 3 days**; thousands of configuration variations; in-house designed cases; thermography testing; **24/7 phone support**; pickup and onsite repair [S9].
- TV, station and taxi ads stress **made in Japan (国内生産)** [S10].
- Parts orders marked "ships within 24 hours" can ship the same day if confirmed by 15:40 [S14].

### Used PC buyback and points [F]
- **Dospara Points** can be used in stores and online, and can also be converted into **Steam Wallet** credit [S15].
- PCs, parts, peripherals and phones are bought in store or by free-shipping mail-in. Campaigns give bonus points (e.g. 1,500 pt for a buyback of ≥ ¥10,000 and 10,000 pt for ≥ ¥80,000). A Sept 2026 campaign gave **+10% points on GALLERIA trade-ins** and +5% on other Thirdwave PCs [S15].
- Members of the **Dospara Safety Service** (extended warranty plan) get +10% on buyback prices [S15].
- During the Windows 10 end of support, Thirdwave pushed point-back campaigns, higher trade-in prices, **up to 48-month instalments**, paid in-store data migration, a monthly membership, and free seminars [S13].

---

## 2. Product lines

### GALLERIA (gaming, also creator/AI) [F]
- Thirdwave says GALLERIA has the **top share of Japan's gaming desktop market** [S6].
- **New GALLERIA lineup launched 18 Sep 2025** with new cases [S16]:

| Series | Positioning | Example model and launch price (tax incl.) |
|---|---|---|
| **X** | New standard; airflow (side intakes about 3× larger), easy maintenance | XPR7A-R57-GD: Ryzen 7 7700 / RTX 5070 12GB / 16GB / 1TB, **¥249,980** |
| **F** | Pillarless glass case, 15 LED patterns, AIO water cooling on every model, casual users | FPC7A-97XT-B: Core Ultra 7 265F / RX 9070 XT, **¥324,980**; FDC7A-R57T-W (RTX 5070 Ti) from ¥364,980 |
| **S** | Flagship; high-end cooling | SMR9E-R59-GL: Ryzen 9 9950X3D / RTX 5090 32GB / 64GB / 2TB Gen5, **¥999,980** |
| **GSL** (GALLERIA Special Line) | Partner/collaboration models | SHPC7A-R56T16G-B Shibuya Haru model, ¥309,980 |
| **E** | Compact (about 19 L), launched 2026 | EPC7I-R57 (Core Ultra 7 265F / RTX 5070); EGC5I-R56T8G-B (Core Ultra 5 225F / RTX 5060 Ti 8GB / 16GB / 1TB / 240mm AIO / 1000W Gold) **from ¥279,980** in Nov 2026 |

- Other 2026 data points: GALLERIA NMC9L-R58-H6 laptop (RTX 5080 Laptop) **¥599,980** (Apr 2026) [S17]. XDR7A-R58 (Ryzen 7 9850X3D / RTX 5080) and XMR9A-R59-WL (RTX 5090) appear in the Nov 2026 Black Friday sale [S18].
- **Naming scheme.** Thirdwave has not published an official decoding. The pattern below comes from catalogue listings [S16][S19]:
  - 1st letter = series (X/F/S/E…)
  - 2nd letter = case/size variant
  - 3rd letter = CPU maker (**C** = Intel Core, **R** = AMD Ryzen)
  - digit = CPU tier (5/7/9)
  - next letter = cooling/variant
  - after the hyphen = GPU (**R57** = RTX 5070, **R57T** = 5070 Ti, **R56T16G** = 5060 Ti 16GB, **97XT** = RX 9070 XT, **96XT** = RX 9060 XT)
  - suffix = colour/edition (B = black, W = white, etc.)
  - Older models used names like XA7C-R57 and ZA9R-R59: series letter + case + CPU tier + C/R, then the GPU. **[A]** For the simulation, use this decoding as the internal SKU rule.
- **Collaborations [F]:** VTuber group ぶいすぽっ! (six-model lineup, on display at GALLERIA Lounge Jun–Aug 2026); にじさんじ (e.g. Kuzuha model, 2025); streamers 渋谷ハル and カグラナナ; esports team DETONATOR; Crazy Raccoon collaboration page; game collaborations announced at **TGS 2026: Apex Legends and Persona 4 Revival** [S10][S20].
- **GALLERIA Lounge (Akihabara)**: flagship GALLERIA showroom, renamed from GALLERIA eSports Lounge on 18 Sep 2025 [S21].

### THIRDWAVE (value / general use / customisable) [F]
- Positioned as cost-competitive, highly customisable PCs. Examples: THIRDWAVE MA4-C5UIGA 14" laptop (Core Ultra 5 125U, 32GB); THIRDWAVE AD-R7A56A desktop (Ryzen 7 7700 + RTX 5060 Ti); **THIRDWAVE-G** budget gaming line [S18][S22].
- After Nov 2025, THIRDWAVE-G prices rose **¥39,000–87,000**. Some configurations moved from dual-channel 8GB×2 to single 16GB, or were cut from 16GB to 8GB [S1].

### raytrek (repositioned to enterprise / creator / AI) [F]
- Repositioned in Sep 2023 from a creator brand to a **corporate PC brand** focused on AI, education, CAD/BIM, video production and game development [S5][S6].
- **raytrek Workstation N8630** (Threadripper PRO, up to 4× RTX 6000 Ada), entry workstation X2630, laptop R6-MT and others (9 models announced in Jul 2024). "raytrek AI" local generative-AI product, and a raytrek cloud GPU service for university labs [S6][S23].
- 2025–26 enterprise pitch: **local LLM bundled with hardware** for government, finance, medical and manufacturing customers that handle sensitive data. Case study: **teamLab Biovortex Kyoto** (opened Oct 2025) [S9].

### Parts retail, monitors, peripherals [F/A]
- Dospara is still a major PC **parts** retailer. Its 32GB×2 DDR5 kit price (¥119,800 online, 2 Feb 2026) became a national news item [S24-b].
- **[A]** Monitors, keyboards, headsets, chairs and similar items are sold in stores and online, partly under Dospara/GALLERIA-branded OEM lines. The simulation can treat them as an "accessories" category of about 8% of revenue.

---

## 3. Dospara stores and campaigns

### Stores [F]
- **47 stores in Aug 2024.** Expansion was fast until Jul 2024 and then deliberately slowed, with no store-count target for that year. New stores focus on local roles and enterprise sales: 「ここにドスパラがあるから助かる」 ("people should feel it helps to have a Dospara here") [S6].
- **43 Dospara + 15 Digital Dock in Sep 2025.** The plan is to open more stores, renovate existing ones, and reposition Dospara as an **"experience-type PC store"** where customers try creative uses [S8].
- 2025–26 renovations, e.g. **Yokohama Ekimae** (7 Nov 2025: more parts and used items) [S25]. New Digital Dock shops inside Dospara **Matsuyama Kanjo Edaematsu** (23 Apr 2026) and **Shizuoka Higashi-Sena** (30 Jul 2026). The consultation menu is ¥2,200 per 20 min, plus a "Digital Care Service" subscription [S24][S26].
- Flagship area: **Akihabara** (Dospara Akihabara Main Store (秋葉原本店) + GALLERIA Lounge) [S21][S24-b].
- Store formats [F/A]: suburban roadside stores with parking (e.g. Matsuyama), station-front stores (Yokohama), stores with a Digital Dock corner, and the GALLERIA Lounge showroom. **[A]** A share of stores also handles used PCs and buyback.
- **Online vs store mix: not public. [A]** Simulation value: **online about 65% / stores about 35%** of PC revenue. Stores matter more for parts, buyback, repair and first-time buyers.

### Campaign calendar [F unless marked]
| Timing | Campaign | Notes |
|---|---|---|
| 1–3 Jan | 初売り (New Year sale) + **福袋** (lucky bags) | Akihabara Main Store sold an SSD lucky bag priced at the year number: ¥2,022, ¥2,023 (50 units, 1 per person), ¥2,025 (with a 500GB SSD). **Cancelled for 2026**, announced 31 Dec 2025 [S1][S28] |
| mid-Jan to early Feb | **半期決算セール** (half-year closing sale), sometimes a "FINAL" round | 2024: 15 Jan to 1 Feb; 2025: from 10 Jan + "FINAL" from 24 Jan [S27] |
| Feb–Apr | 新生活 / spring campaigns | Jan 2026 spring campaign with coupons up to 40% off [S29]; "新生活スタートダッシュ" page [S30] |
| May–Jun | Memory sale | May–Jun 2026: up to ¥100,000 off PCs with 32GB [S31] |
| Jun–Jul | Summer bonus sale (夏のボーナス) and **大決算 (full-year closing) sale** in July | Jul 2026 "大決算カスタマイズキャンペーン": 16GB→32GB for **¥888** until 31 Jul [S31] |
| Oct | Anniversary sale (周年祭) [A: secondary source only] | — |
| late Oct–early Dec | **Black Friday** | 2026: early-bird customisation sale 30 Oct to 13 Nov (32GB +¥9,696; SSD 500GB→1TB +¥19,696) [S22]; main Black Friday **13 Nov 11:00 to 4 Dec 10:59** (stores to 3 Dec): coupon up to ¥100k + points up to ¥100k; mainstream GPU desktops get about ¥4,000–30,000 in total; free 9800X3D→9850X3D upgrade on some models [S18][S32] |
| Dec | Winter bonus / year-end | Dec 2025: order surge; shipping times extended on 26 Dec [S29] |

---

## 4. Japan PC market, 2025–2026

### Windows 10 end of support and the hangover [F]
- Windows 10 support ended **14 Oct 2025** [S33].
- **CY2025 Japan PC shipments: 10.95 million units, +43.8%.** That was the first time above 10 million in 5 years, driven by Windows 10 replacement and GIGA School phase 2 [S34].
- Thirdwave's view: enterprise demand rose from August and peaked in **September 2025**. Consumers lagged because of cost, data migration and "it still works" [S13]. Nagai thought enterprise replacement was mostly done by March 2025, while SMBs and consumers would cluster near the deadline [S8].
- **Hangover (JEITA, Apr–Sep 2026): 3.80M units, −33.5% YoY.** Desktops 422k (−37.1%). Average unit price **¥145,208 (+40.3%)**. Jul–Sep 2026 ASP was **¥160,169 (+58.9%)**. Six straight months of YoY decline. Some makers raised prices in Jan–Mar 2026, all did by Apr–Jun, and new launches carried bigger hikes in Jul–Sep [S35].
- BCN retail data (excludes GIGA): Sep 2026 desktop ASP **¥175,000 (+7.2%)**, notebook ¥150,900 (+14.3%) [S35]. In May 2026, PC memory ASP was **4.6×** YoY, while the overall PC ASP was up only 2.5% [S36].

### The 2025–2026 memory (DRAM/NAND) shock [F]
- **Cause:** AI/HBM demand moved capacity to server memory. MM Research said 30–40% of global memory output had shifted to AI uses and that expanding capacity takes 2–3 years [S24-b].
- **Retail timeline in Japan:**
  - Late Sep 2025: prices start jumping.
  - Dospara 32GB×2 DDR5 kit: about ¥16,000 (Sep 2025) → about ¥80,000 (28 Jan 2026, Akihabara) → **¥119,800 (2 Feb 2026, online)** [S24-b].
  - DDR5-6400 32GB about ¥18,000 → about ¥68,000 (3.8×); SSD 1TB ¥11,000 → ¥32,000 (2.9×); HDD 8TB ¥20,000 → ¥55,000 (Jul 2026) [S1].
- **BTO impact:**
  - Dec 2025: Mouse Computer, TSUKUMO and Sycom suspended new orders. Frontier raised main models by +16–41%.
  - Dospara lead times stretched to about 2 weeks, then 3–7 weeks. Dospara's memory upgrade prices were 32GB = ¥49,999 and 64GB = ¥99,999 [S1].
  - Some BTO brands paused orders 23 Dec 2025 to 4 Jan 2026 and repriced after [S37].
  - Dospara cut lead times again in Jan 2026: notebooks about 5 days, desktops about 3 weeks (6 Jan), "from 3 days" for previous-gen GALLERIA and THIRDWAVE (14 Jan) [S29].
- **Contract-price outlook (TrendForce):**
  - 3Q26 PC DRAM +18–23% QoQ; **4Q26 PC DRAM +13–18%** (slowing because PC sales are weak and inventories are rising).
  - Client SSD < +5% in 4Q26.
  - Conventional DRAM +10–15% and NAND +15–20% in 4Q26.
  - **Korean suppliers plan to cut PC DRAM output by >20% in 2027** to favour server DRAM.
  - PC OEMs pulled purchases forward into 1H26 [S38].

### GPUs [F]
- NVIDIA **RTX 50 series** (RTX 5090/5080 launched Jan 2025, then 5070 Ti/5070/5060 Ti/5060). The **Feb 2025 GPU shortage** pushed GALLERIA RM7C-R46T from ¥189,980 to ¥249,980 (+¥60,000), with Dospara lead times of 7–10 days [S1].
- **RTX 50 SUPER**: expected at CES 2026 but not announced. It was reportedly delayed indefinitely because 3GB GDDR7 memory is too expensive and NVIDIA is prioritising AI products; current RTX 50 production cuts were also reported [S1][S39].
- AMD **Radeon RX 9070 XT / 9070 / 9060 XT** (2025) are in the GALLERIA F series and RM5C models [S16][S19].

### CPUs [F]
- Intel **Core Ultra 200S** (e.g. 265F, 225F) and AMD **Ryzen 7 7700 / 9000 / X3D** (9800X3D, **9850X3D**, 9950X3D) are the current BTO staples [S16][S18].
- **Intel Nova Lake (Core Ultra 400, new LGA1954 socket)**: officially "by end of 2026", but leaks point to a CES 2027 reveal and Q1 2027 availability. **AMD Zen 6 desktop**: reportedly CES 2027 announcement, shipping Mar–Jun 2027 [S40].

### Exchange rate [F]
- USD/JPY in 2026: near **¥164** in late July (intervention fears), about ¥159.5 (25 Aug), about ¥153 (10 Sep), **about ¥157.9 (22 Oct)** [S41]. Components are priced in USD, so a ¥5 move is roughly a 3% change in parts cost.

### Gaming PC market and competitors [F unless marked]
- The Japanese PC **game** market was about ¥310B in 2025 (2.35× 2021) [S42]. Gaming PCs were about **11% of Windows PC shipments** [S43]. No public figure for gaming-PC hardware market size was found. **[A]** Use about ¥250–300B per year, with BTO desktops about 40%.
- **Mouse Computer (G-Tune, NEXTGEAR, DAIV)**: FY2025 standalone sales ¥73.0B, 37% enterprise. Parent **MCJ** consolidated FY3/2026 sales **¥224.3B**, OP ¥21.1B, both records; it passed costs through to prices. MCJ went private via MBO and was **delisted Jun 2026**. MCJ also owns **Unitcom (Pasocom Koubou / LEVEL∞)**. Mouse plans to focus investment on mini PCs and gaming [S44].
- **TSUKUMO (G-GEAR)**: Yamada Denki group brand (business moved from Project White into Yamada Denki in 2021) [S45].
- **FRONTIER**: run by Inverse Net (Yokohama). It ran New Year "福箱" (lucky boxes) in Jan 2026 (e.g. Ryzen 7 9700X + RTX 5070 at ¥310,000, 7 units) [S28][S46].
- **Sycom** (premium BTO): suspended orders in Dec 2025 and reopened on 5 Jan 2026 with price increases [S1].
- **Dell, HP, Lenovo, NEC/Lenovo, Fujitsu** dominate mainstream and enterprise. HP sold gaming lucky bags in Jan 2026 (from ¥189,026) [S28]. **[A]** These global OEMs have bigger memory contracts, so in a shortage they can hold prices longer than domestic BTO makers.

---

## 5. How planning works at a company like this (Japanese context)

### Calendar [F + A]
- **Thirdwave FY: Aug–Jul [F].** Simulation term: **FY2027/7 = 第44期 (44th term), Aug 2026 to Jul 2027 [A]**. The 41st term began Aug 2023 [S6], so the numbering follows.
  - Q1 Aug–Oct, Q2 Nov–Jan, Q3 Feb–Apr, Q4 May–Jul.
  - **Late Nov 2026 = the start of Q2**, with **half-year closing on 31 Jan 2027**.
- JEITA, GIGA School budgets, government and most enterprise customers use **April–March**. Enterprise and education demand peaks in **Feb–March** (budget use-up) [A, standard Japanese practice].
- Bonus seasons: **summer bonus late Jun–Jul**, **winter bonus about 10 Dec** [A, standard Japanese practice]. These line up with Thirdwave's July 大決算 sale and its December demand.

### Planning processes [A, based on industry practice]
- **S&OP / 需給計画 (demand–supply plan), weekly.** Forecast per model family (e.g. "X series RTX 5070 tier") and per configuration option (memory 16/32/64GB, SSD 1/2TB). BTO means **finished goods are built to order, but parts are bought to forecast.** The real inventory risk is in **CPUs, GPUs, DRAM, SSDs and motherboards**.
- **Lead times [A]:**
  - GPUs: allocation from NVIDIA/AMD partners (ASUS, MSI, Palit, etc.) about 8–12 weeks ahead.
  - DRAM/SSD: quarterly contracts negotiated in the month before the quarter (e.g. Q1 2027 price fixed in December), plus spot buys.
  - Cases: own design, from a Chinese/Taiwanese OEM, about 12–16 weeks.
  - Assembly at Ayase: 1–3 days.
- **Pricing [A]:** price committee (価格会議) roughly every two weeks; urgent repricing during shocks. Tools: base price, paid customisation prices (memory upgrade price = a key lever), coupons, points (deferred discount: cheaper than a cash discount because not all points are used), free upgrades, and "spec-down" (fewer or smaller DIMMs).
- **Campaign calendar planning** about 8–10 weeks ahead, because parts must be secured for featured SKUs.
- **Store opening (出店) plan:** annual plan; each site is approved after the president visits it in person [F, S10].
- **KPIs [A]:**
  - order intake (受注) vs plan
  - shipments (出荷) and revenue
  - gross margin % by brand
  - **order-to-ship lead time (days)** and on-time shipping %
  - backlog (受注残)
  - parts inventory days (DIO) and aged inventory
  - GPU/DRAM coverage weeks
  - online conversion rate
  - store sales per tsubo (per 3.3 m²)
  - buyback volume
  - repair turnaround
  - NPS / reviews

### Typical meetings [A, typical for Japanese mid-size companies]
| Meeting | Frequency | Chair / attendees | Typical agenda |
|---|---|---|---|
| 朝会 / 部内ミーティング (morning meeting / department meeting) | Daily, 15 min | Section chief | yesterday's orders, lead times, issues |
| **週次需給会議 (weekly S&OP)** | Weekly (e.g. Monday) | 需給管理 manager; product planning, purchasing, factory, EC, stores | forecast vs orders, parts coverage, lead-time display on site, allocation |
| 価格・キャンペーン会議 (pricing & campaign meeting) | Every two weeks | 商品企画 head + 販促 (sales promotion) + EC + finance | price changes, coupon/point budgets, next campaign |
| **月次経営会議 / 月次業績報告 (monthly management meeting)** | Monthly | President + directors; 経営企画 runs it | P&L vs budget, 着地見込み (forecast landing), actions |
| 四半期予算見直し (quarterly budget review) | Quarterly | 経営企画 + finance + division heads | reforecast, 下期予算 (H2 budget) |
| 取締役会 (board meeting) | Monthly | Board | approvals (large purchase commitments, store openings) |
| 稟議 (ringi) | Ad hoc | Written approval chain | large DRAM pre-buy, new case mould, store lease |

### Typical job titles [A, typical Japanese titles]
- **経営企画部 (Corporate Planning):** 部長 (general manager), 課長 (manager), 主任 (senior staff), 担当 (staff). Jobs: budget, mid-term plan, KPIs, board materials.
- **商品企画部 (Product Planning):** GALLERIA商品企画課 / raytrek・法人商品企画課 / THIRDWAVE商品企画課, plus product managers ("PM") per series.
- **事業企画 (Business Planning)** inside the Retail Division: store plans, campaigns.
- **需給管理課 / SCM課 (demand-supply / SCM)**, 購買部 (purchasing, buyers for CPU/GPU/memory), 生産管理 at Ayase (production control), 販売促進部 (sales promotion), EC事業部 (online business), 店舗開発 (store development), 法人営業本部 (enterprise sales), 財務経理部 (finance and accounting).
- Executive titles seen at Thirdwave: 取締役 社長執行役員 COO (President & COO), 取締役 専務執行役員 (Director & Senior Executive Officer), 執行役員 (Executive Officer) [F, S10][S13].

### Japanese meeting culture (for realistic dialogue) [A, general knowledge]
- **根回し (nemawari):** big decisions are pre-agreed one-on-one before the meeting. The meeting itself often confirms the decision.
- Hierarchy shows in seating and in speaking order; juniors present data, seniors decide. People speak indirectly 「検討します」 ("we will consider it"), 「少し厳しいかもしれません」 ("that may be a little difficult"), and soften disagreement.
- Strong preference for **data-backed slides (資料)**, often dense Excel/PowerPoint. Meetings end with assigned **宿題 (homework / action items)** and deadlines. **議事録 (minutes)** are circulated afterwards.
- **報連相 (hō-ren-sō: report, contact, consult)** is expected. Bad news is escalated early, but usually framed with a proposed countermeasure (対策).
- Thirdwave-specific flavour: a retail-floor DNA (many executives started on the shop floor), speed (「まずやってみる」, "let's just try it first"), and a president who values basics and in-person talk [F, S8][S10].

---

## 6. Realistic tensions and decisions for late November 2026

*All numbers in this section are ASSUMPTIONS [A] sized for a company with about ¥100B revenue and about 300k PCs per year, unless a source is cited.*

### Situation snapshot (the simulation's starting state)
- FY2027/7 budget: revenue **¥108B**, gross margin **19%**, operating margin **4%**. H1 (Aug–Jan) revenue budget ¥55B.
- Q1 (Aug–Oct) actual: revenue ¥24.8B vs ¥26.0B budget (−4.6%). PC units 66k vs 75k budget (−12%). ASP up about +9% vs budget. Gross margin 17.6% vs 19%.
- Black Friday (13 Nov to 4 Dec) [F dates S18]: order intake in week 1 at 92% of plan. The 32GB upgrade at ¥9,696 [F S22] is taken by about 70% of buyers. The real cost of the extra 16GB is about ¥14,000, so each upgrade loses about ¥4,300.
- Memory: Q4 (Oct–Dec) DRAM contract +15% [F range S38]. Suppliers are quoting **Q1 2027 PC DRAM +10–20%** and warn of **allocation cuts** as they reduce PC DRAM output >20% in 2027 [F S38].
- Yen: ¥156/USD in budget; spot about ¥158 [F level S41]; intervention risk both ways.

### Scenario ideas
1. **Q1 2027 memory contract: lock in or wait?** Purchasing wants to commit to 120k DIMMs (16GB DDR5) for Jan–Mar at +14% (about ¥1.4B), to secure allocation before the 2027 PC DRAM output cuts. Finance warns that weak demand (JEITA desktops −37% [F S35]) means excess stock if Q1 sales miss, and TrendForce says increases are slowing [F S38]. Options: full commit / 70% commit + spot / 50% + spec-down.
2. **Price increase vs margin.** Raise base prices by ¥10,000–20,000 on 6 Jan 2027 after the New Year sale? The full-year gross margin gap is about ¥1.5B. Competitors (Frontier +16–41% in Dec 2025 [F S1]; MCJ passed costs through [F S44]) have already raised prices, but units are down about 33% market-wide. Sub-decision: end the subsidised ¥9,696 memory upgrade after Black Friday, or keep it as the main "value" message.
3. **Fukubukuro 2027: revive the ¥2,027 SSD bag?** It was cancelled for 2026 because of shortages [F S1]. SSD 1TB street price about ¥32,000 [F S1]. 50 bags × about ¥8,000 loss = ¥400k: tiny in money but large in PR (news coverage, queues in Akihabara). The bigger question is whether to sell **PC lucky boxes** like Frontier/HP [F S28] using aged previous-generation stock (e.g. 1,200 units of Core Ultra 200S + RTX 4060-class leftovers).
4. **Nova Lake / Zen 6 transition timing.** New platforms are expected at CES 2027 with availability in Q1–Q2 2027 [F S40]. Product planning wants to pre-announce new GALLERIA S/X models for February. Purchasing holds about ¥1.8B of current-generation CPUs and motherboards (about 9 weeks of cover). Risk: buyers wait (Osborne effect) and old stock must be cleared at a discount in the January 半期決算セール. Decide the cut-over date and the sell-down plan.
5. **GPU allocation: gaming vs enterprise AI.** NVIDIA allocation for Jan–Mar is 15% below request; RTX 50 SUPER is still not coming [F S39]. Enterprise sales have a ¥600M local-LLM workstation tender (prefectural government, delivery by 31 Mar for the April–March budget) that needs 160 high-end GPUs. Giving them priority hurts the RTX 5080/5090 GALLERIA lead times shown on the website (target ≤ 5 days). It ties to the 30% enterprise-share goal [F S6].
6. **Half-year closing gap (31 Jan 2027).** H1 is tracking about ¥2.5B short. Options: bigger 半期決算セール (point-heavy), push enterprise deliveries into January, or accept the miss and reforecast. 経営企画 must prepare the 着地見込み (forecast landing) for the December monthly management meeting, and the president wants "every route tried" [F style S10].
7. **Spec-down and brand risk.** THIRDWAVE-G already went to single-channel / 8GB in some configurations [F S1]. Should GALLERIA entry models (RTX 5060) ship with 16GB×1 instead of 8GB×2 to save about ¥3,000 per unit? The gaming community notices single-channel performance loss, so there is a review/SNS risk for the No.1 gaming-desktop brand.
8. **Store and Digital Dock plan for FY2027/7.** There are 43 stores [F S8], a renovation programme and Digital Dock add-ons [F S24]. Proposal: 3 new stores (about ¥150M each including fit-out) plus 6 Digital Docks, vs freezing openings while PC demand falls. Repair and support subscriptions are a counter-cyclical revenue stream (old PCs are kept longer when new ones are expensive).
9. **Yen shock contingency.** If USD/JPY returns to ¥164 (Jul 2026 level [F S41]), parts cost rises about 4%. Should FX be hedged for Q1 purchases (about $60M of USD payables)? Who owns the decision: finance or purchasing?
10. **Collaboration model inventory.** TGS 2026 collaborations (Apex Legends, Persona 4 Revival [F S10]) use special side panels and case prints that cannot be reused. Forecast is 3,000 units, but early orders point to about 1,900. Order a second batch of panels (MOQ 2,000, 14-week lead time) or not?

### Possible cast for a planning meeting [A]
- 経営企画部長 (GM, Corporate Planning): owns the half-year landing and the budget.
- GALLERIA 商品企画 PM: wants new platform launches and protection of the brand.
- 購買部 memory/GPU buyer: pushes for an early commitment ("allocation first").
- 需給管理課長 (demand-supply manager): owns lead-time KPIs and inventory weeks.
- 財務経理 manager: cash, inventory risk, FX.
- 販売促進 / EC manager: campaigns, coupons and points budget, fukubukuro PR.
- 法人営業 (enterprise sales) manager: the AI workstation tender.
- 店舗開発 (store development) manager: store and Digital Dock plan.
- (Sometimes) the President & COO: makes the final call and values basics and in-person checks.

---

## Sources

- [S1] gamingpcs.jp, "ゲーミングPCの値上げ・高騰まとめ" (updated 11 Oct 2026): https://gamingpcs.jp/choice/market/rising-pc-price/
- [S2] gurafu.net, Dospara (Thirdwave) revenue by fiscal year: https://gurafu.net/jpn/thirdwave
- [S3] paiza recruiter profile, 株式会社サードウェーブ: https://paiza.jp/recruiters/2580 ; also OpenWork: https://www.openwork.jp/a0C1000000rZ0ni/analysis/ ; en-japan: https://employment.en-japan.com/comp-115440/
- [S4] ASCII.jp, Thirdwave 40th anniversary / Ida interview (4 Sep 2024): https://ascii.jp/elem/000/004/218/4218904/
- [S5] ASCII.jp (same series), brand strategy: https://weekly.ascii.jp/elem/000/004/218/4218904/
- [S6] PC Watch, 大河原克行 column on Ida's appointment and strategy (Aug 2024): https://pc.watch.impress.co.jp/docs/column/gyokai/1612767.html
- [S7] ASCII.jp, planning in Akihabara; Ebina/Ayase/Hiratsuka: https://weekly.ascii.jp/elem/000/004/218/4218904/
- [S8] INTERNET Watch, interview with President Masaki Nagai (5 Sep 2025): https://internet.watch.impress.co.jp/docs/interview/2039582.html
- [S9] Nikkei BP special feature on Thirdwave enterprise/AI (2026): https://special.nikkeibp.co.jp/atclh/NXT/26/twave0319/p2/
- [S10] Game*Spark, Nagai interview (19 Jul 2026): https://www.gamespark.jp/article/2026/07/19/169461.html
- [S11] ASCII.jp, Nagai interview (9 Sep 2025): https://ascii.jp/elem/000/004/318/4318040/
- [S12] Game Watch interview with Kensuke Ozaki (2019): https://game.watch.impress.co.jp/docs/interview/1188839.html
- [S13] BCN+R, Osada (Thirdwave retail) on post-Windows 10 demand (5 Dec 2025): https://www.bcnretail.com/market/detail/20251205_579511.html
- [S14] Dospara, parts free shipping / same-day shipping: https://www.dospara.co.jp/contents/parts-free-shipping.html
- [S15] Dospara used-PC buyback campaigns: https://www.dospara.co.jp/used-buy/app-pc-buyback-campaign-260901.html ; https://www.dospara.co.jp/used-buy/ssmember10percent-up.html
- [S16] Game*Spark, new GALLERIA lineup (18 Sep 2025): https://www.gamespark.jp/article/2025/09/18/157349.html
- [S17] PC Watch / BCN coverage of 2026 GALLERIA laptops: https://pc.watch.impress.co.jp/docs/news/2104451.html ; https://www.bcnretail.com/news/detail/20260330_613762.html
- [S18] Hermitage Akihabara, Dospara Black Friday 2026 press release (13 Nov 2026): https://www.gdm.or.jp/pressrelease/2026/1113/660270 ; ASCII (7 Nov 2026): https://weekly.ascii.jp/elem/000/004/449/4449121/
- [S19] gadgetzamurai.jp, GALLERIA model-number guide: https://gadgetzamurai.jp/?p=23097 ; Dospara Radeon list: https://www.dospara.co.jp/gaming-pc-tc30-map-amd-radeon.html
- [S20] Inside Games, ぶいすぽっ! collab at GALLERIA Lounge (Jul 2026): https://www.inside-games.jp/article/2026/07/03/184003.html ; Kuzuha collab (Feb 2025): https://www.inside-games.jp/article/2025/02/21/164603.html ; Crazy Raccoon page: https://www.dospara.co.jp/gamepc/cts_collab_crazyraccoon.html
- [S21] Impress "ドスパラでGO!", GALLERIA Lounge: https://www.watch.impress.co.jp/donya/dospara_galleria_lounge.html
- [S22] Hermitage Akihabara, Black Friday early-bird customisation sale (30 Oct 2026): https://www.gdm.or.jp/pressrelease/2026/1030/658781
- [S23] PC Watch, raytrek enterprise lineup and raytrek AI (Jul 2024): https://pc.watch.impress.co.jp/docs/news/1605155.html ; Game*Spark: https://www.gamespark.jp/article/2024/07/06/142999.html
- [S24] BCN+R, Digital Dock Matsuyama (24 Apr 2026): https://www.bcnretail.com/market/detail/20260424_621618.html
- [S24-b] News On Japan (TBS), memory prices at Dospara, Nagai comments (3 Feb 2026): https://newsonjapan.com/article/148273.php
- [S25] Impress "ドスパラでGO!", Yokohama store renewal: https://www.watch.impress.co.jp/donya/dospara_yokohama.html
- [S26] Digital Dock Shizuoka Higashi-Sena press release (31 Jul 2026): https://www.zaikei.co.jp/releases/3550286/
- [S27] Hermitage Akihabara, Dospara 半期決算セール 2024: https://www.gdm.or.jp/pressrelease/2024/0115/522158 ; ASCII 2025: https://ascii.jp/elem/000/004/244/4244934/
- [S28] gamingpcs.jp, New Year 2026 sales roundup: https://gamingpcs.jp/choice/sale/hatsuuri2026/ ; ASCII on Dospara fukubukuro 2023: https://ascii.jp/elem/000/004/118/4118873/
- [S29] PC Watch, Dospara shortens lead times (14 Jan 2026): https://pc.watch.impress.co.jp/docs/news/2077678.html
- [S30] Dospara 新生活 campaign page: https://www.dospara.co.jp/event/newlife-startdash-entry.html
- [S31] ASCII / Digital Camera Watch coverage of 2026 Dospara memory campaigns: https://ascii.jp/elem/000/004/421/4421963/ ; https://dc.watch.impress.co.jp/docs/news/campaign/2109163.html
- [S32] gaming-st.com, Dospara Black Friday 2026 guide: https://gaming-st.com/gamingpc/dospara-black-friday-2026-gaming-pc-budget-guide/
- [S33] Microsoft Japan, Windows 10 end of support: https://www.microsoft.com/ja-jp/atlife/article-windows10-portal-eos.aspx
- [S34] 電波新聞, 2025 Japan PC shipments 10.95M (27 Jan 2026): https://dempa-digital.com/article/706557
- [S35] PC Watch, JEITA Apr–Sep 2026 shipments −33.5% (Oct 2026): https://pc.watch.impress.co.jp/docs/news/2151743.html ; Q1: https://pc.watch.impress.co.jp/docs/news/2126633.html
- [S36] BCN+R, memory ASP 4.6× (31 May 2026): https://www.bcnretail.com/market/detail/20260531_630848.html ; Feb 2026: https://www.bcnretail.com/market/detail/20260222_599644.html
- [S37] Tom's Hardware, Japanese BTO shops halt orders (Dec 2025): https://www.tomshardware.com/desktops/pc-building/japanese-shops-halt-desktop-pc-orders-until-2026-as-memory-shortage-intensifies-built-to-order-systems-hamstrung-by-component-shortages-and-skyrocketing-prices
- [S38] TrendForce 4Q26 memory forecast (30 Sep 2026): https://www.trendforce.com/presscenter/news/20260930-13258.html ; PC DRAM 4Q26 update: https://cryptobriefing.com/trendforce-pc-dram-prices-rise-4q26/ ; 2027 procurement: https://iconnect007.com/article/152347/pc-oems-adjust-2027-memory-procurement-amid-rising-inventories/152344/flex
- [S39] Tom's Hardware, RTX 50 SUPER stuck due to GDDR7 pricing: https://www.tomshardware.com/pc-components/gpus/nvidia-rtx-50-super-gpus-are-reportedly-ready-but-stuck-in-limbo-due-to-excessive-gddr7-pricing-3gb-gddr7-module-costs-triple-the-price-of-2gb ; TweakTown: https://www.tweaktown.com/news/109694/geforce-rtx-50-super-series-delayed-indefinitely-as-nvidia-informs-its-partners/
- [S40] Tom's Hardware, Nova Lake schedule leak: https://www.tomshardware.com/pc-components/cpus/intels-core-ultra-400-nova-lake-launch-schedule-leaks-out-mass-production-in-q4-first-nova-lake-cpus-in-q1-2027 ; Zen 6 timing: https://tech-insider.org/intel-nova-lake-amd-zen-6-delay-2026/
- [S41] Matsui Securities FX news (Oct 2026): https://finance.matsui.co.jp/news/629915/index ; Gaitame.com (Jul 2026): https://www.gaitame.com/media/entry/2026/07/24/110345
- [S42] gaming-st.com, CESA 2025 PC game market: https://gaming-st.com/news/japan-pc-game-market-doubled-cesa-2025/
- [S43] Game Watch, gaming PC share of Windows PC shipments: https://game.watch.impress.co.jp/img/gmw/docs/1488/228/html/loq_5.jpg.html
- [S44] EnterpriseZine, MCJ FY3/2026 results and MBO: https://enterprisezine.jp/news/detail/24545 ; Mynavi, Mouse Computer FY2025: https://news.mynavi.jp/techplus/article/20260703-4654730/
- [S45] TSUKUMO / Project White history: https://ja.wikid.org/%E4%B9%9D%E5%8D%81%E4%B9%9D%E9%9B%BB%E6%A9%9F
- [S46] ASCII.jp, Inverse Net (FRONTIER) profile: https://ascii.jp/elem/000/004/423/4423901/

*Gaps to note:* There is no public figure for Thirdwave's FY2026/7 revenue, unit volumes, margins, online/store mix, current exact store count, Digital Dock total, gaming-PC hardware market size, or an official GALLERIA naming decoder. The official site thirdwave.co.jp could not be reached during this research. Treat all of these as assumptions in the simulation.
