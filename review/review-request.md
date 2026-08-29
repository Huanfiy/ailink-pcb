# ailink v0.3 硬件设计评审请求

## 评审对象

基于 `product.md` v0.3 需求基线完成的初版单板设计（KiCad 10）：原理图、4 层 PCB、BOM。

## 评审输入材料（均为绝对路径）

| 材料 | 路径 |
| --- | --- |
| 需求基线（权威依据） | /home/huan/workspace/kicad/ailink/product.md |
| 设计说明（决策与偏差） | /home/huan/workspace/kicad/ailink/outputs/design-notes.md |
| 原理图 PDF 转图片 | /home/huan/workspace/kicad/ailink/outputs/ailink-schematic-1.png |
| 网表（s 表达式） | /home/huan/workspace/kicad/ailink/outputs/ailink.net |
| BOM | /home/huan/workspace/kicad/ailink/outputs/ailink-bom.csv |
| ERC 报告 | /home/huan/workspace/kicad/ailink/outputs/erc-report.txt |
| DRC 报告 | /home/huan/workspace/kicad/ailink/outputs/drc-report.txt |
| PCB 顶层铜 | /home/huan/workspace/kicad/ailink/outputs/pcb-pdf/01-F_Cu.pdf |
| PCB 内层1 GND | /home/huan/workspace/kicad/ailink/outputs/pcb-pdf/02-In1_GND.pdf |
| PCB 内层2 电源 | /home/huan/workspace/kicad/ailink/outputs/pcb-pdf/03-In2_PWR.pdf |
| PCB 底层铜 | /home/huan/workspace/kicad/ailink/outputs/pcb-pdf/04-B_Cu.pdf |
| 3D 渲染 | /home/huan/workspace/kicad/ailink/outputs/renders/render-top.png 等 4 张 |
| USB 差分几何报告 | /home/huan/workspace/kicad/ailink/outputs/si-report.txt |

## 评审范围与判定标准

请按 product.md 逐条核查，输出分级问题清单（Blocker / Major / Minor / Note）：

1. **引脚映射（§5.1）**：网表中 U1 每个引脚的网络是否与 §5.1 完全一致（含 GPIO bit2=PA0、PB2 仅 10k 下拉）。
2. **功能需求（§2.3 FR-01~10）**：USB-C、双串口、SWD、8 路 GPIO、控制台、状态灯、SPI NOR、DFU 按键链路完整性。
3. **电气需求（§2.4 ER-01~10）**：LDO 规格与余量、220 Ω 串阻覆盖 17 路、ESD 器件选型与位置、16 MHz 晶振、90 Ω 差分、无 D+ 外挂上拉、BOOT0/BOOT1/NRST 上电确定性、NC 引脚处理。
4. **自举与救砖（§4.11 / CR-05/06）**：BOOT0 按键+下拉、PB2 下拉、NRST 按键+100nF 的正确性。
5. **保护链（§4.12）**：VBUS 保险丝+TVS、每路串阻+ESD 的拓扑与器件参数是否合理。
6. **电源（§4.2 / D-09）**：AP2112K-3.3 选型、去耦方案（VCAP 2.2µF、VDD 100nF×4、VDDA 磁珠+1µF+100nF）。
7. **PCB（§4.14 / MR 系列）**：板框 65×35、四角 M2、USB 端与目标端对置、L2 完整地、晶振包地与禁布、ESD 靠近连接器、丝印标注（3V3 ONLY 等）。
8. **BOM 完整性（§7）**：与骨架清单对照，数量与规格。
9. **设计偏差合理性**：design-notes.md 第 4 节所列偏差是否可接受。
10. **可制造性**：0603 工艺、两面贴装、盘中孔备注、丝印可读性。

## 结论要求

- 每条问题给出：级别、位置（文件/位号/网络）、问题描述、建议修改。
- 明确总体结论：通过 / 有条件通过（列出必须整改项）/ 不通过。
