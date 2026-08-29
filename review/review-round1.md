# ailink v0.3 设计评审报告（第一轮）

## 总体结论

**不通过。当前版本不得直接投板。**

本轮发现 **2 项 Blocker、8 项 Major、3 项 Minor、3 项 Note**。两个阻断项分别为：

1. **D7（SMAJ5.0A）极性反接**：KiCad 官方单向 TVS/`D_SMA` 的 1 脚为带标记端（阴极），当前网表及 PCB 却为 `D7.1=GND、D7.2=VBUS_P`。按正常极性装配后，USB VBUS 将经 D7 正向导通到地，单板无法正常上电。
2. **16 MHz HSE 布局不满足关键时钟要求**：晶振回路长、OSC_OUT 换层并有两个过孔，负载电容远离晶振，且 BOOT0、MCU_SWDIO 等信号从晶振下方穿过；这直接违反 `product.md §4.14`，会给起振裕量、频率精度、EMI 及 DFU/应用启动带来不可接受风险。

投板前应关闭全部 Blocker；Major 应在第二轮评审前关闭，或由硬件负责人基于计算/仿真/制造商数据作书面偏差签核。修订后须重新导出网表、BOM、ERC、DRC、各层图和 SI 报告，并再次评审。

本报告是**投板前设计文件评审**，不是样机实测验收；`product.md §8` 的 HV-01～HV-15 尚无样机数据，不能据此判定最终硬件验收通过。

## 问题清单

| # | 级别 | 位置 | 问题 | 建议 |
| --- | --- | --- | --- | --- |
| 1 | Blocker（阻断投板） | `outputs/ailink.net`、`hardware/ailink.kicad_pcb`；D7、`VBUS_P`、GND | D7 为单向 SMAJ5.0A。当前 `D7.1=GND、D7.2=VBUS_P`；KiCad 官方 SMAJ 单向 TVS 符号和 `D_SMA` 封装的 1 脚为阴极/色环端。按封装标记贴装后，器件会从 VBUS_P 向 GND 正向导通。现有 `verify_netlist.py` 只比较两端网络集合，未检查极性，所以错误地放过了该问题。 | 改为 `D7.1(K)=VBUS_P、D7.2(A)=GND`，在原理图和 PCB 上同步更新；在网表校验中加入有方向的 D7 引脚断言，并复核贴片图中的色环方向。 |
| 2 | Blocker（阻断投板） | PCB：U1 pin 5/6、X1、R6、C10/C11、`OSC_IN/OSC_OUT/OSC_XO`；X1 下方 B.Cu | HSE 回路未按关键时钟布局。统计值为 `OSC_IN≈12.49 mm`、`OSC_OUT≈7.00 mm`（含 2 个过孔和 2.25 mm B.Cu 段）、`OSC_XO≈10.97 mm`；R6、C10、C11 分散在 X1 周围较远位置。PCB 未定义晶振 keepout，BOOT0、MCU_SWDIO（以及邻近 NRST）B.Cu 走线进入 X1 本体/庭院投影区。晶振地焊盘附近也没有紧邻的回流过孔。 | 重做晶振小岛：X1 紧靠 PH0/PH1；R6 靠近 OSC_OUT；C10/C11 紧贴各晶振端并各自短接地过孔；HSE 全程 F.Cu、无过孔、无支路；在所有信号层建立 keepout，禁止非 HSE 信号穿过晶振及回路下方，并以 GND 包围。 |
| 3 | Major（强烈建议整改） | PCB：U2、C14、SPI2 网络 | SPI NOR 去耦和走线明显不合理。C14 到 U2 pin 8 的直线距离约 **17.5 mm**，与 `design-notes.md §4` 所称“迁至 U2 左侧”不符；`SPI2_SCK≈44.44 mm/2 vias`、`SPI2_MOSI≈30.90 mm/2 vias`、`FLASH_CS≈30.53 mm/4 vias`，而 U1、U2 中心仅相距约 10.2 mm。高速边沿下存在供电反跳、振铃和 Flash 不稳定风险。 | 将 C14 放到 U2 pin 8 旁（目标焊盘间路径 ≤1～2 mm）并紧邻地过孔；重新直连 SPI2，优先同层、短走线、连续参考地，尤其缩短 SCK；样机若仍有振铃，再在 MCU 端预留小阻值串阻并实测定值。 |
| 4 | Major（强烈建议整改） | PCB：U3/C1/C2、FB1/C8/C9/U1 pin 13 | 关键去耦未“紧邻”负载。U3 VIN 到 C1 约 5.77 mm、VOUT 到 C2 约 5.53 mm；VDDA 的 C8/C9 到 U1 pin 13 分别约 6.44/7.09 mm。AP2112 的稳定性与瞬态性能依赖靠近引脚的输入/输出陶瓷电容，VDDA 的 100 nF 也应直接服务 MCU 引脚。 | C1/C2 移到 U3 对应引脚旁，形成最小 VIN/GND 与 VOUT/GND 回路；按 `+3V3→FB1→VDDA 局部岛→C8/C9→U1.13` 排列，将 C9 置于 pin 13 最近处并紧邻地过孔。保留当前位置良好的 C3～C7。 |
| 5 | Major（强烈建议整改） | `hardware/ailink.kicad_pcb`、`outputs/si-report.txt`、`design-notes.md §3`；USB_DP/USB_DM | ER-07 尚未得到可制造、可复核的 90 Ω 证据。PCB 文件只有 1.6 mm 总厚度，没有介质厚度、Dk、铜厚及阻抗控制定义；SI 报告只是对“JLC7628-class”作近似声明。其脚本把整网所有支路长度相加，包含 Type-C 双触点扇出和不对称测试点支路，所得 0.73 mm 不是 U1 到 J1 的真实端到端 skew；设计说明又写成 1.53 mm。差分线也只有部分区段保持 0.35/0.15 mm 紧耦合。 | 锁定实际板厂叠层并取得阻抗计算/场求解结果；在制板要求中明确 90 Ω differential ±10%；按实际叠层反算线宽/间距。重写 SI 检查，按 U1↔J1 主路径计算长度，排除支路并计入过孔；测试点改为在线小焊盘或把支路缩到最短。 |
| 6 | Major（强烈建议整改） | 原理图/BOM：D1 USBLC6-2SC6；`product.md §4.3` | D1 不满足基线所写的“≤1 pF 量级”。ST 数据手册给出的 I/O-to-GND 电容为典型约 2.5 pF、最大 3.5 pF（线间典型约 1.2 pF）。该器件本身适用于 USB 2.0，USB FS 大概率可工作，但它是未在偏差表中批准的参数偏差。 | 二选一：改用明确满足 ≤1 pF 的 USB 专用 ESD 阵列；或由负责人正式修订/签核该指标，并以板厂叠层仿真和 USB 眼图/枚举压力测试证明 USBLC6-2SC6 可接受。 |
| 7 | Major（强烈建议整改） | PCB：H1～H4、板框 | 板框中心线尺寸为 65×35 mm，前三个孔位为 (103,103)、(162,103)、(103,132)，但 H4 位于 **(154.5,132)**，距右边约 10.5 mm，不是右下角安装孔，不符合 MR-01“四角 M2”。 | 调整 J4/J5/周边布局，把 H4 移到与其他孔对称的右下角（建议中心约 (162,132)）；若结构确实要求偏移，必须先修订 MR-01 并给出外壳/支撑柱图。 |
| 8 | Major（强烈建议整改） | PCB F.SilkS；J2～J5；`outputs/drc-report.txt` | DRC 有 11 个 warning，主要为丝印重叠/压焊盘。J5 的 `TX RX GND` 被三个焊盘裁切；J3 的 B 通道只写成 `B:TX,RX,GND`，J4 只写成 `G4-G7,GND`，没有逐针对应；`NO POWER OUT` 位于电源区且与 D7/U3 位号重叠，并未在 J2～J5 旁形成清晰接口边界。这不符合 MR-03/§4.13。 | 逐针、对齐标注 J2～J5，必要时在背面增加针脚表；TX/RX 明确为 ailink 视角。将 `3V3 ONLY / NO POWER OUT` 成组放到目标接口区。清除所有用户丝印 warning；J1 边缘连接器的 2 条边界 warning 可验证后作有理由的局部豁免。 |
| 9 | Major（强烈建议整改） | PCB：D1 pin 2、U1 pin 16（CON_TX） | 存在未充分处理的盘中孔：D1 pin 2 中心有 0.30 mm 钻孔/0.60 mm 过孔；U1 pin 16 的 LQFP 焊盘内也有同规格过孔，后者未在设计说明中披露。普通阻焊盖油不等于树脂填孔，回流时可能吸锡、形成空洞或开焊；D1 的地开焊还会使 USB ESD 保护失效。 | 优先用短 dog-bone 将过孔移出焊盘；若必须保留，制造文件明确要求树脂填孔+电镀盖孔（VIPPO），并让板厂确认 0.5 mm pitch LQFP 能力及钢网开口。补充 U1 pin 16 的工艺说明和 AOI/X-ray/电测要求。 |
| 10 | Major（强烈建议整改） | `outputs/ailink-bom.csv` | 数量骨架基本齐全，但尚不是可下单 BOM：R1/R2 未保留 ±1%，X1 未写 ±10/±20 ppm 及具体料号，C7 未注明低 ESR，C1/C2 未注明 X5R/X7R、耐压和直流偏压后的有效容量；D8、F1、FB1、J1、按键等仍主要靠通用 Value/Footprint 识别。D8 未锁定具体料号时，1210 RGB 的共阳脚序和颜色脚序无法保证。 | 为关键器件补齐 Manufacturer/MPN、封装、额定值、容差、耐压、温度特性和可替代料约束；尤其锁定 X1、D8、D1～D7、F1、FB1、U3、J1。BOM 导出时保留关键规格列，不应只输出 Value。 |
| 11 | Minor（可接受但建议改进） | PCB：D2～D6 pin 2；`design-notes.md §4` | 每个 SRV05-4 的 GND 脚约经 1.4 mm 走线后才到单个地过孔，不是最短 ESD 泄放路径。设计说明称“约 1.5 pF/线”，而 Semtech 原厂规格是 I/O-to-GND 典型约 3 pF（1.5 pF 是不同测量口径/部分替代品数值）。在当前 12 MHz/11.25 Mbaud 下带宽仍可接受，但物料和评审数据应准确。 | 锁定厂家完整 MPN；让 pin 2 紧贴 1～2 个地过孔直达 L2，缩短连接器→ESD→地回路；按所选厂商数据更新电容、钳位电压和 IEC 等级。 |
| 12 | Minor（可接受但建议改进） | PCB/BOM/3D：J6 | BOM 已省略 J6，符合默认不焊；但 PCB 中 J6 仍是普通 `through_hole` 属性，未排除 BOM/位置文件，3D 渲染也显示已装排针，交付信息互相矛盾。 | 在原理图和 PCB 中统一标记 DNP，并从 BOM/位置文件排除；装配图明确“J6 不装”，3D 渲染使用不带排针的焊盘状态。 |
| 13 | Minor（可接受但建议改进） | `design-notes.md`、`si-report.txt`、PCB 数据 | 交付材料存在版本/事实不一致：USB mismatch 为 1.53 mm 与 0.73 mm 两种值；设计说明称 B.Cu 有 GND 铺铜，但 PCB 实际只有 In1 GND 和 In2 +3V3 两个 zone；称 C14 已移到 U2 左侧，实际相距 17.5 mm。PCB 还检测到 12 组完全重复的同网走线段，增加脚本统计和后续维护歧义。 | 以最终 PCB 为单一源重新生成说明和报告；删除重复线段；所有自动检查记录板文件哈希/时间戳，并修正 D7 极性及 USB 主路径的断言方式。 |
| 14 | Note（备忘） | `design-notes.md §5`、`product.md §8` | LDO 温升/纹波、11.25 Mbaud UART、12 MHz SWD、ESD、24 h 老化等尚无样机结果。 | 第二轮设计通过后按 HV-01～HV-15 建立样机记录；未完成前不得宣称硬件最终验收通过。 |
| 15 | Note（备忘） | 固件/生产配置：GPIO bit2、RDP | 硬件已将 GPIO bit2 改到 PA0，但功能仍依赖固件表项同步；RDP Level 0 无法由网表证明。 | 样机验收纳入固件版本、PA0 GPIO 回归、BOOT0 任意 GPIO 状态下进入 DFU，以及量产烧录后 RDP0 读回检查。 |
| 16 | Note（备忘） | USB 描述符/发布边界 | VID/PID `1209:0010` 仍为测试用途，符合 v0.3 开发验证定位，但不适合销售。 | 对外分发前取得正式 VID/PID，并更新固件、标签和合规资料。 |

## 逐项核查结果

### 1. 引脚映射（§5.1）：PASS

对 `outputs/ailink.net` 作了独立解析，33 个要求引脚为 **33/33 匹配**：

| 分组 | 逐项结果 |
| --- | --- |
| GPIOA | PA0=TGPIO2；PA1=TGPIO6；PA2=CON_TX；PA3=CON_RX；PA4=T_SWCLK；PA5=T_SWDIO；PA6=T_nRESET；PA8=TGPIO7；PA9=B_TX；PA10=B_RX；PA11=USB_DM；PA12=USB_DP；PA13=MCU_SWDIO；PA14=MCU_SWCLK |
| GPIOB | PB0=TGPIO0；PB1=TGPIO1；PB2=BOOT1；PB8=TGPIO3；PB9=TGPIO4；PB10=TGPIO5；PB12=FLASH_CS；PB13=SPI2_SCK；PB14=SPI2_MISO；PB15=SPI2_MOSI |
| GPIOC | PC0=LED1；PC1=LED2；PC2=LED3；PC6=A_TX；PC7=A_RX |
| 时钟/专用 | PH0=OSC_IN；PH1=OSC_OUT；BOOT0=BOOT0；NRST=NRST |

补充证据：

- GPIO bit2 已落到 PA0（U1 pin 14）；PB2（U1 pin 28）所在 BOOT1 网络仅连接 R5=10 kΩ 下拉，没有外部功能连接。
- 19 个未使用 MCU 引脚均以 `unconnected-*` 网络/NC 标记，结果为 19/19。
- MCU 电源脚、VSSA/VDDA、VCAP、VBAT 的网络分配与基线一致。

### 2. 功能需求（FR-01～FR-10）：PARTIAL

| 需求 | 判定 | 证据/说明 |
| --- | --- | --- |
| FR-01 USB 复合设备 | PARTIAL | PA11/PA12、J1、D1 和 USB 供电链完整；复合枚举及并发功能必须样机验证。 |
| FR-02 串口 A | PASS（设计） | PC6/PC7→R13/R14→D3→J3，映射正确。11.25 Mbaud 待实测。 |
| FR-03 串口 B | PASS（设计） | PA9/PA10→R15/R16→D3→J3，映射正确。11.25 Mbaud 待实测。 |
| FR-04 目标 SWD | PASS（设计） | PA4/PA5/PA6→R10～R12→D2→J2；J2 顺序 GND/CLK/DIO/RST。12 MHz 待实测。 |
| FR-05 8 路 GPIO | PASS（硬件） | PB0/PB1/PA0/PB8/PB9/PB10/PA1/PA8 全部存在并受保护；固件 PA0 表项待回归。 |
| FR-06 空板 DFU | PASS（电路） | BOOT0 下拉+按键至 3V3，RST 独立按键；端到端 DFU 待样机。 |
| FR-07 自身 SWD | PASS（电路） | J6 为 3V3/SWDIO/SWCLK/GND。DNP 元数据需统一。 |
| FR-08 控制台 | PASS（设计） | PA2/PA3→R25/R26→D6→J5。 |
| FR-09 状态灯 | PASS（设计） | PC0/PC1/PC2 低有效共阳 RGB，另有电源灯。 |
| FR-10 SPI NOR | PARTIAL | 型号和引脚映射正确，但 C14 与 SPI 布局存在问题 #3，不能按当前版接受稳定性。 |

### 3. 电气需求（ER-01～ER-10）：FAIL

| 需求 | 判定 | 证据/说明 |
| --- | --- | --- |
| ER-01 仅 USB 供电、不向目标供电 | PASS | J2～J5 无 5 V/3V3 电源针；J6 的 3V3 仅用于 ailink 自身调试。 |
| ER-02 LDO ≥300 mA、余量 | PARTIAL | AP2112K-3.3 额定 600 mA，容量满足；布局、温升和纹波待问题 #4/HV-01 关闭。 |
| ER-03 固定 3.3 V CMOS | PASS | 未发现电平转换或 VTref/目标供电网络。 |
| ER-04 对外接口 ESD | FAIL | 17 路目标信号均有 ESD，USB 也有 D1；但 D7 反接且 D1 电容不满足书面基线。 |
| ER-05 17 路 220 Ω | PASS | R10～R26 共 17 个，逐路形成 MCU 网络→电阻→`*_J` 网络→ESD/连接器。 |
| ER-06 16 MHz ±20 ppm | FAIL | 原理图值为 16 MHz，设计说明称 ±10 ppm；BOM未固化精度，且 PCB 晶振回路为 Blocker。 |
| ER-07 USB 90 Ω ±10% | PARTIAL | L1/L2 参考结构和 0.35/0.15 几何存在，但没有锁定叠层/场求解/受控阻抗制造要求。 |
| ER-08 无 D+ 1.5 kΩ 外拉 | PASS | 网表/BOM 未发现 D+ 外挂上拉。 |
| ER-09 BOOT0/BOOT1/NRST 确定性 | PASS | BOOT0 R4=10 kΩ 下拉；BOOT1 R5=10 kΩ 下拉；NRST 按键至地+C12=100 nF。 |
| ER-10 未用引脚 NC | PASS | U1 未用引脚 19/19 为 NC，未引出功能焊盘。 |

### 4. 自举与救砖（§4.11 / CR-05/06）：PARTIAL

- **电路拓扑 PASS**：BOOT0 按下接 3V3、常态 R4 下拉；PB2/BOOT1 仅 R5 下拉；NRST 由 SW2 拉低并有 C12=100 nF。
- **整体 PARTIAL**：D7 反接会阻断供电，HSE 布局风险会影响应用时钟与既定 DFU 路径；RDP Level 0 属生产配置，不能由设计文件证明。
- J6 可提供外部探针救砖，但默认 DNP 信息需统一。

### 5. 保护链（§4.12）：FAIL

- 17 路外部信号的逻辑拓扑全部正确：`MCU→220 Ω（R10～R26）→ESD（D2～D6）→J2～J5`。
- USB 为 J1→D1→U1，D1 靠近 USB 数据出线；CC1/CC2 各有 5.1 kΩ 下拉。
- VBUS 为 J1→F1→`VBUS_P`→U3，D7 跨接 `VBUS_P/GND`；但 D7 极性错误是阻断项。
- D1 及 U1 pin 16 的盘中孔、D2～D6 的地回路和 D1 电容规格需按问题 #6/#9/#11 整改。

### 6. 电源（§4.2 / D-09）：FAIL

- **选型/网表正确部分**：U3=AP2112K-3.3；VIN 与 EN 接保险丝后 `VBUS_P`；C1=1 µF、C2=2.2 µF；VCAP C7=2.2 µF；VDD 去耦 C3～C6 共 4×100 nF；VDDA 为 FB1+C8 1 µF+C9 100 nF。
- **失败原因**：D7 反接使电源入口不可用；C1/C2 和 VDDA 去耦距离不符合“紧邻”要求；BOM 未锁定电容介质、耐压和有效容量。
- 额定 600 mA 相对估算 130 mA 有余量，但约 0.22 W 的 SOT-23-5 温升仍须 HV-01 实测。

### 7. PCB（§4.14 / MR 系列）：FAIL

- **PASS**：板框中心线 65×35 mm；4 层；In1.Cu 为单一 GND zone，In2.Cu 为 +3V3 zone；没有信号在内层走线；USB 在左端，目标 J2/J3/J4 集中在右端；ESD 阵列位于连接器侧；BOOT/RST 相邻且独立。
- **FAIL**：H4 不是右下角孔；晶振回路及 keepout 不合格；USB 90 Ω 未形成可制造闭环；目标接口丝印不逐针且 DRC 不清零；设计说明所称 B.Cu GND 铺铜与实际 PCB 不符。
- USB 主路径主要在 F.Cu、以 L2 为参考；USB_DM 的两个过孔位于 Type-C 复用触点扇出支路，不等同于主差分对整体换层，但现有 SI 脚本没有区分主路径和支路。

### 8. BOM 完整性（§7）：PARTIAL

- 数量与骨架基本一致：U1/U2/U3 各 1；D1 1 个、D2～D6 共 5 个、D7 1 个；F1 1 个；R10～R26 共 17 个 220 Ω；CC 下拉 2 个；VDD 去耦 4 个；VCAP、VDDA 滤波、LED 限流、连接器和按键数量齐全。
- J6 未列入 BOM，符合默认不焊，但 PCB/位置文件属性未同步。
- 关键规格和可采购料号不完整，详见问题 #10；当前只能视为设计 BOM，不能视为已冻结的生产 BOM。

### 9. 设计偏差合理性：PARTIAL

| `design-notes.md §4` 偏差 | 判定 | 评审意见 |
| --- | --- | --- |
| D7 改 SMAJ5.0A/SMA | 封装偏差可接受；实现不可接受 | 400 W 等级对本用途有余量，SMA 也可制造；但当前极性反接必须修正，并需确认 5 V VRWM、钳位和 AP2112 6.5 V 绝对最大值之间的系统保护目标。 |
| TPD4E05U06→SRV05-4 | 有条件接受 | 对 11.25 Mbaud UART/12 MHz SWD 的带宽足够，SOT-23-6 易装配；必须锁定厂家 MPN并用其真实 3 pF 级参数和钳位曲线评估。 |
| R22↔R24、R15↔R16 位置互换 | 接受 | 网表网络未改变，17 路拓扑逐项正确。 |
| R7/R8/C14 迁移 | R7/R8 接受；C14 不接受 | 上拉电阻位置影响较小；C14 实际距 U2 VCC 约 17.5 mm，不能作为有效本地去耦。 |
| 低速线使用 0.15 mm | 接受 | 满足常规 6 mil 工艺且电流很小；仍应以实际板厂能力表确认。 |
| 背面放置 CC/RC/去耦等 | 接受 | 均为小型器件，双面回流可行；须在装配报价和工艺文件中明确双面贴装。 |
| 无源件位号不上丝印 | 有条件接受 | Fab/装配层完整即可；但不能牺牲 J2～J5 每一针的功能丝印，当前实现不满足 MR-03。 |

另：D1 pin 2 盘中孔仅作为“备注”不足以形成制造约束；若不改 dog-bone，必须在板厂订单/制板说明中明确填孔盖孔工艺。

### 10. 可制造性：FAIL

- **PASS**：主体无源为 0603；0.15 mm 最小线宽、0.30 mm 钻孔/0.60 mm 普通过孔属于常规能力；顶/底面器件均为可回流的小封装；DRC 显示 0 个未连接焊盘、0 个封装错误。
- **FAIL**：D1/U1 盘中孔未转化为明确 VIPPO 工艺；丝印 DRC 未清零且接口文字会被裁切；J6 DNP 属性不一致；生产 BOM 未冻结。
- 板上 12 组重复同网线段不会直接改变 Gerber 铜形，但会污染长度统计、增加后续编辑风险，应在发布前删除。

## 亮点与风险提示

### 亮点

- 需求到网表的核心映射完成度高：33/33 引脚正确，PA0 替代 PB2，19 个闲置 MCU 引脚均 NC。
- BOOT0/BOOT1/NRST、USB CC、SPI NOR、RGB LED、自身 SWD 等原理图链路完整。
- 17 路 220 Ω 串阻和 D2～D6 ESD 的网络拓扑全部正确；目标连接器没有输出板上电源。
- VCAP、4 组 VDD 去耦及四层 L2 整面地的架构方向正确；ERC 为 0 error/0 warning，PCB 无未连接焊盘。
- 65×35 mm 板框、USB/目标接口分区和双面 0603 工艺总体可实现。

### 风险提示

- 当前自动网表检查对“网络存在”覆盖较好，但对有极性器件、物理距离、回流路径、支路长度和制造属性覆盖不足；D7 正是典型漏检。
- 修改 GPIO bit2 后必须使用与本板匹配的固件版本；量产烧录流程还需锁定 RDP Level 0。
- 固定 3.3 V、无 VTref、无目标供电是有意产品边界，接口丝印必须足够清楚，否则误接风险会抵消电路保护收益。
- 即使第二轮设计文件通过，仍必须完成 USB 枚举/并发、11.25 Mbaud UART、12 MHz SWD、SPI Flash、DFU 救砖、温升、ESD 和 24 h 老化后，才能给出最终硬件验收结论。
