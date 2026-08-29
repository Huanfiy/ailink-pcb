# 评审整改手术报告（round 1）

板文件：`hardware/ailink.kicad_pcb`（独占写入）。未改原理图 / `gen_sch.py` / `outputs/design-notes.md`。

终检（ZONE_FILLER 之后）：**未达标**。`unconnected=5`，铜层类违规约 69（含 shorting/clearance/tracks_crossing/hole/solder_mask_bridge 等）。丝印：`silk_over_copper=13`，`silk_overlap=4`（≤6 达标），`silk_edge=6`（含 J1 豁免 2 条以外的余量）。

---

## 1. 重复线段 #13 — 完成

12 组同 net+layer+端点+宽度的重复 `PCB_TRACK` 已删至一份。

## 2. 晶振岛 #2 — 主体完成

| 网络 | 长度 | 层 | 过孔 |
|------|------|----|------|
| OSC_IN | 4.03 mm | 仅 F.Cu | 0 |
| OSC_XO | 3.83 mm | 仅 F.Cu | 0 |
| OSC_OUT | 6.56 mm | 仅 F.Cu | 0 |

- C10 `(120.7, 114.3)` rot90；C11 `(116.4, 118.2)` rot270；R6 `(119.0, 119.4)` rot270。
- 负载电容 / X1 GND 就近过孔仍在（C10-2、C11-2、X1-2、X1-4、U1-12）。
- **B.Cu 禁布区** `X1_HSE_KEEPOUT`：`(116.6, 114.6)–(121.0, 118.4)`，禁 tracks+vias，允许铺铜。当前 B.Cu 无穿越。
- BOOT0 / NRST / MCU_SWDIO 已撕掉原晶振下方楼梯线并重布。NRST 改为西向出线 + via `(121.50, 118.85)` + B.Cu 西-南至复位簇。MCU_SWDIO 走北/东绕，约 60–98 mm（A*）。
- 庭院重叠 C10/C11/R6×X1：紧贴预期，保留。

## 3. C14 #3 — 位置完成，SPI 未缩到目标

- C14 → `(134.6, 127.6)` rot270；pad1 接到既有 +3V3 via `(133.488, 126.295)`；pad2 就近 GND via `(133.50, 128.40)`。
- SPI2_SCK / MOSI / FLASH_CS 现长约 **27.7 / 20.4 / 28.1 mm**（目标 SCK ~10–15 mm 未达到）。东侧过孔与 FLASH_HOLD/T_SWDIO 仍挤。

## 4. LDO/VDDA #4 — 器件已靠拢，铜皮未干净

- C1 `(120.0, 102.2)` rot90（VIN 北侧 ≤2 mm）；C2 `(124.0, 101.9)` rot0（VOUT 北侧）。
- C8 `(116.2, 121.9)`；C9 `(118.2, 123.4)` rot180（避开 R6，距 pin13 约 4 mm）。
- VDDA：FB1 → C8/C9（F 南侧）+ via `(118.98, 124.35)` → B.Cu → via `(125.10, 120.90)` → pin13。
- 仍有 VDDA 与 TGPIO2/GND/+3V3 等短路/间距报告，需再收。

## 5. H4 / J3 / J4 #7 — 完成

- J3 `(160.5, 108.6)`；J4 `(160.5, 117.6)`；H4 `(162.0, 132.3)`（南移 0.3 mm 避 J4 庭院，J4 最南 GND 在 y=127.76）。
- 12 条 `_J` 网络 `--ripup` **ALL ROUTED**。

## 6. CON_TX 盘中孔 #9 — 完成

- U1 pad16 内 CON_TX via 已删；最近 CON_TX via 距 pad16 **2.56 mm**。D1 pin2 VIPPO 未动。

## 7. J6 DNP #12 — 完成

- `attrs=77` = THT | EXCLUDE_FROM_BOM | EXCLUDE_FROM_POS_FILES | **FP_DNP**。

## 8. 丝印 #8 — 部分完成

- `ailink.kicad_pro`：`min_text_height` **0.7**。
- J3 奇数列 F 层 dx=−3.0；偶数列 B.SilkS 镜像，x 收到 164.25（避出板）。
- J4 同策略（含 G0–G7 与 GND 行）。
- J5：`TX` `RX` `G` 于 y=131.4，x=144.5/147.04/149.58。
- `3V3 ONLY` `(155.0, 133.2)`，`NO PWR OUT` `(155.0, 134.2)`；旧 `3V3 ONLY` / `NO POWER OUT` / 成组字已删。
- 余量：silk_over_copper **13**（未清零）；silk_overlap **4**；silk_edge **6**。

## 9. 终检缺口

未连接（5）：**SPI2_MOSI、TGPIO5、TGPIO3**，以及 T_nRESET / LED2 的层间断开。

`--ripup` 级联曾撕后又补回的网络（不完全表）：BOOT0、NRST、MCU_SWDIO、MCU_SWCLK、SPI2_*、FLASH_*、TGPIO0–7、T_SWDIO、T_SWCLK、T_nRESET、CON_TX、CON_RX、A_TX/A_RX/B_TX/B_RX、LED2、VCAP、BOOT1，以及 12 条 `_J`。

`scripts/astar_router.py` 改动：HSE/NRST/MCU_SWDIO 列入 `HARD_NETS`；禁止把路径终点拉到远处第一焊盘（避免斜穿 U1）；`build_grid` 识别 rule-area。

建议下一刀：先补 3 条硬断网 + 拆 VDDA/TGPIO2 短路，再清 silk_over_copper；不要再对西走廊做大范围 AABB 删线。
