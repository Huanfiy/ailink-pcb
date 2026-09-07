# ailink v0.4 产品板工程

当前基线为 **42 × 22 mm、四层、双面布局的无按键产品板**。原理图、布局、封装和配套固件已更新；布线及最终检查正在收尾。此页不沿用 v0.3 的“可投板”结论。

| 内容 | 入口 |
| --- | --- |
| 设计与接口基线 | [product.md](product.md) |
| KiCad 工程 | [原理图](hardware/ailink.kicad_sch) · [PCB](hardware/ailink.kicad_pcb) |
| 外形设计文档 | [docs/design/ailink-compact-pcb-design.md](docs/design/ailink-compact-pcb-design.md) |
| 正反面布局 | [docs/design/layout-options.svg](docs/design/layout-options.svg) |
| DRC 问题与约束评估 | [docs/error/2026-09-05-kicad-drc-routing-constraint-assessment.md](docs/error/2026-09-05-kicad-drc-routing-constraint-assessment.md) |
| 制造与装配条件 | [outputs/FAB-NOTES.md](outputs/FAB-NOTES.md) |
| 实施与验证说明 | [outputs/design-notes.md](outputs/design-notes.md) |
| 配套固件 | [../ai-link](../ai-link) · [USB 设计](../ai-link/docs/design/usb-bridge.md) |

正面保留 USB、MCU、时钟岛和指示灯，四颗 UART 灯正对 ATX、ARX、BTX、BRX；PWR/STATUS 位于 USB 座两侧。D1、电源、Flash 和大部分无源件位于背面。尾端为 2×6 夹板直针，正面双 UART，背面 SWD 与 3.3 V/5 V 输出；长边各四个 GPIO 孔，出厂不装针。

当前主 PCB 候选已完成布局、USB 保护路径、地/电源层和大部分信号布线。本轮补通 TGPIO3_J、TGPIO2_J、T_nRESET，修复新走线造成的 3.3 V 覆铜断开，并清理 11 个冗余过孔及死端支线。ERC、原理图一致性、56 项产品约束和 USB 几何检查通过；KiCad 原生 DRC 已从 11 个未连接项目 / 18 个过孔悬空警告降至 **8 个未连接项目 / 7 个过孔悬空警告**，无其他 DRC 违规。评审图纸、检查报告和源文件散列已刷新；制造导出被检查门禁阻止，未生成制造包。

86 个封装记录及 USB/HSE 的 45 条布线记录保持不变，没有放宽设计规则或引入盘中孔。剩余连接及后续处理重点见 [工程说明](outputs/design-notes.md)。

目标电源暂按 3.3 V / 100 mA 和 5 V / 150 mA 设计。固件已实现 USB 状态控制输出、信号高阻、通信灯和 GPIO2→PA0；Release 与 boot 构建通过，100 Hz / 1000 Hz tick 下的主机逻辑测试通过。新板尚未上机验证，USB 挂起时 MCU 低功耗路径仍待完成。

`outputs/` 被 Git 忽略，检查报告与图纸须按当前工程重新导出。旧版制造 ZIP 和 Gerber 已撤下；v0.3 评审材料已移出工作区，git 历史 `60fd433` 可查，不覆盖本版。

```bash
# 对当前源文件生成检查报告与评审图纸；失败不会生成制造包
bash scripts/export_all.sh review

# 在 /tmp 创建候选工程，保留 hardware/ 中的已编辑布线
bash scripts/run_pipeline.sh

# 布线与清理脚本的回归测试（使用带 pcbnew 的系统 Python）
python3 -m unittest discover -s tests -v
```

数字检查通过后，仍须核对实际叠层阻抗、D8 正式脚序、J2 夹板装配及样机电源/通信表现。USB 和排针的 3D 模型为示意，不作为供应商机械公差依据。
