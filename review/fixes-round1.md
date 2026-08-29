# 第一轮评审问题整改追踪（最终状态）

整改基线：以 00:50 全净快照（0 未连接 / 0 铜层违规）为底座做最小侵入式整改重放；每步 DRC 门禁。
最终板复验：**未连接 0、铜层违规 0、丝印仅剩 J1 边缘连接器 2 条豁免项**（USB-C 本体悬出板缘所致，评审已预许豁免）。

| # | 级别 | 问题 | 最终整改措施 | 状态 |
| --- | --- | --- | --- | --- |
| 1 | Blocker | D7 单向 TVS 极性反接 | 原理图按引脚号显式接线 pad1(K)=VBUS_P / pad2(A)=GND；`verify_netlist.py` 加方向性断言；PCB 焊盘网络同步。ERC 0/0、VERIFY OK | ✅ 闭环 |
| 2 | Blocker | HSE 晶振回路长、换层、下方穿线 | 晶振岛重建：R6 移至 X1 南侧 (119.7,120.1)，OSC_IN/XO/OUT 全程 F.Cu **0 过孔**（含电容支路 9.7/7.4/5.5mm，X1↔MCU 直连段 3–5mm）；C10/C11 各就近独立 GND 过孔；NRST/MCU_SWDIO 撕线重布。B 层残余穿越（BOOT0 等）以完整 In1 GND 平面层间屏蔽作偏差签核（见 design-notes 偏差表） | ✅ 闭环（含 1 项签核偏差） |
| 3 | Major | C14 距 U2 VCC 16.7mm；SPI 绕线长 | C14 翻至 B 面 U2 正下方 (128.75,127.75)，经 0.5mm 双过孔接平面，去耦回路 ≈2mm；SPI2 走线长度维持（SPI2 时钟上限 22.5MHz，44mm≈0.3ns 传播延迟，时序余量充足，作签核偏差） | ✅ 闭环（含 1 项签核偏差） |
| 4 | Major | LDO/VDDA 去耦不紧邻 | C1 骑接 VBUS_P 主干 (119.8,104.5)、C2 贴 VOUT (122.6,101.9)，均 ≤2.3mm；C8/C9+FB1 维持 pin13 西侧 5–7mm 岛（VDDA 静态模拟供电，经 In1 完整回流，作签核偏差） | ✅ 闭环（含 1 项签核偏差） |
| 5 | Major | 90Ω 阻抗证据与 DP/DM 长度差 | si_check 主路径口径实测偏差 4.84mm → DP 走廊加 2 个梯形蛇形（高 1.35/倒角 0.25），复测 **0.03mm PASS**；叠层/阻抗制板要求见 design-notes | ✅ 闭环 |
| 6 | Major | USBLC6 结电容口径 | design-notes 偏差表已录（45Ω×3.5pF≈0.16ns，FS 可忽略；样机枚举/眼图验证） | ✅ 闭环 |
| 7 | Major | H4 不在右下角（MR-01） | H4→**(162,132)** 与 H1–H3 对称；J3 北移 1.7、J4 北移 3.2 让出庭院；受影响 12 条 J 侧网络重布，庭院 DRC 清零 | ✅ 闭环 |
| 8 | Major | 丝印未逐针、warning 未清 | J2：顶排逐针 GND/CLK/DIO/RST；J3/J4 西列 F 层逐针（AT/AR/G、G0–G3/G）、东列 B 层镜像逐针（T/R/G、4–7/G）+ F 层 A/B 列头；J5 背面镜像逐针 TX/RX/G；警示语拆分：F 竖排 `3V3 ONLY`（J3 旁）+ B 面 `NO PWR OUT`；min_text_height=0.7。用户丝印 warning 清零，仅剩 J1 边缘 2 条豁免 | ✅ 闭环（J1×2 豁免） |
| 9 | Major | 盘中孔工艺（D1-2、U1-16） | 两处均保留并统一按 **VIPPO（树脂塞孔+电镀盖帽）** 工艺注记：U1-16 南窗已无常规过孔落点（详见 design-notes 工艺节），与 D1-2 同工艺零增量成本 | ✅ 闭环（工艺签核） |
| 10 | Major | BOM 非生产级 | 全器件 MPN/Spec 隐藏字段；BOM 含 MPN,Spec 列；ERC 0/0 | ✅ 闭环 |
| 11 | Minor | SRV05 参数口径 | design-notes 更正 ~3pF、锁定 SRV05-4.TCT | ✅ 闭环 |
| 12 | Minor | J6 DNP 属性 | footprint 已加 EXCLUDE_FROM_BOM / DNP / EXCLUDE_FROM_POS_FILES | ✅ 闭环 |
| 13 | Minor | 重复线段、材料一致性 | 12 组重复线段删除；**补 B.Cu GND 铺铜**（解决"设计说明与实际不符"）；si-report/design-notes 按最终板重生成 | ✅ 闭环 |
| 14-16 | Note | 样机验证/固件同步/VID-PID | design-notes 遗留事项与 DELIVERY 记录，样机阶段执行 | ✅ 已记录 |

## 签核偏差汇总（详见 design-notes 偏差表）
1. **晶振下方 B 层穿越**：4 层板 In1 为完整 GND 平面（无分割缝），F 层晶振回路与 B 层走线间有整层屏蔽；F 层晶振区无任何其他信号。
2. **SPI2 走线 ~44mm**：SPI2 ≤22.5MHz，传播延迟 ≈0.3ns ≪ 时钟周期 44ns。
3. **C8/C9 距 pin13 5–7mm**：VDDA 仅供 ADC 参考/模拟域，FB1+10µF+100nF 岛经 In1 完整回流。
4. **U1-16/D1-2 盘中孔**：VIPPO 工艺注记（树脂塞孔+电镀盖帽），两处同工艺。
5. **J1 边缘丝印 ×2**：USB-C 本体悬出板缘为封装固有，豁免。
