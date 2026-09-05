# AGENTS.md — ailink-pcb

适用于整个仓库。首轮读本文建立概貌，再按任务查索引；不要默认遍历大体积 KiCad 文件、生成物或历史评审。

## 1. 项目概貌

ailink 是基于 STM32F446RET6 的 KiCad 硬件工程，提供 USB-C 双 UART、CMSIS-DAP v2 与 8 路 GPIO；现行 v0.4 为 42 × 22 mm、四层、双面布局、无用户按键。配套固件在相邻仓库 [../ai-link/](../ai-link/)，不在本仓库构建。

先按 [product.md](product.md) 确认产品要求，再查 [DELIVERY.md](DELIVERY.md) 的实现与交付边界；当前数字检查未全部通过，不能宣称可投板或量产就绪。

## 2. 按任务查入口

| 任务 | 文件 / 目录与用途 |
| --- | --- |
| 查接口、电气、供电、验证边界 | [product.md](product.md)：现行产品基线，不从旧评审推导脚序 |
| 查进度、阻塞、交付结论 | [DELIVERY.md](DELIVERY.md)：状态与检查、导出入口 |
| 查外形、层叠、装配与正反面方向 | [设计说明](docs/design/ailink-compact-pcb-design.md)；[布局图](docs/design/layout-options.svg)、[排针剖面](docs/design/header-cross-section.svg) |
| 分析剩余布线与约束 | [DRC 评估](docs/error/2026-09-05-kicad-drc-routing-constraint-assessment.md)：问题证据、候选方案与验收条件；建议不等于已批准变更 |
| 修改 KiCad 工程 | [hardware/](hardware/)：[原理图](hardware/ailink.kicad_sch)、[PCB](hardware/ailink.kicad_pcb)、[规则及项目配置](hardware/ailink.kicad_pro) |
| 修改符号、封装与模型 | [hardware/lib/](hardware/lib/)；[符号表](hardware/sym-lib-table)、[封装表](hardware/fp-lib-table)；生成入口 [gen_product_lib.py](scripts/gen_product_lib.py) |
| 修改电路或布局生成逻辑 | [gen_sch.py](scripts/gen_sch.py) 电路；[gen_pcb.py](scripts/gen_pcb.py) 布局；[product_config.py](scripts/product_config.py) 参数；[pcb_common.py](scripts/pcb_common.py) 公共 API 与路径 |
| 重建候选 / 理解布线顺序 | [run_pipeline.sh](scripts/run_pipeline.sh)：生成、关键走线、扇出、Freerouting、补线与检查的执行索引 |
| 修改补线 / 铜对象清理 | [astar_router.py](scripts/astar_router.py) 搜索；[fanout_product.py](scripts/fanout_product.py) 扇出与几何；[finish_routes.py](scripts/finish_routes.py) 补线；[cleanup_routes.py](scripts/cleanup_routes.py) 清理；[回归测试](tests/test_route_cleanup.py) |
| 检查与导出 | [verify_netlist.py](scripts/verify_netlist.py) 网络断言；[check_product.py](scripts/check_product.py) 板级约束；[si_check.py](scripts/si_check.py) USB 几何；[export_all.sh](scripts/export_all.sh) 检查门禁与导出 |
| 查看本地检查证据 | [outputs/](outputs/)：检查报告、图纸、BOM；[verification.json](outputs/verification.json) 记录源文件 SHA-256 与检查状态 |
| 修改或新增文档 | 先读 [docs-rules.md](docs-rules.md)：记录归属、落档门槛与清理规则 |

`outputs/` 被 Git 忽略，新检出可能不存在，不能把旧报告当作当前验证。[review/](review/) 和 [docs/plans/](docs/plans/) 中的 v0.3 材料仅供历史追溯，不作为 v0.4 验收依据。

## 3. 环境与常用命令

在仓库根目录执行。使用 **KiCad 10 的 `kicad-cli`、标准库及能 `import pcbnew` 的系统 Python 3**（已有检查环境为 KiCad 10.0.5），不要默认虚拟环境可用。完整导出还需 `pdftoppm`，制造打包需 `zip`；自动布线的 Java 路径与 JAR 要求见 [tools/run-freerouting.sh](tools/run-freerouting.sh)。

```bash
# 快速检查：不重建主工程，但不能代替完整 ERC/DRC
python3 -m unittest discover -s tests -v
python3 scripts/verify_netlist.py
python3 scripts/check_product.py
python3 scripts/si_check.py hardware/ailink.kicad_pcb
```

其他操作按任务选择，不作为快速检查的一部分：

- **只检查 DRC**：按 [DRC 复查入口](docs/error/2026-09-05-kicad-drc-routing-constraint-assessment.md#8-复查入口与证据文件) 执行；不加 `--save-board`，避免保存到主 PCB。
- **重建候选**：`bash scripts/run_pipeline.sh` 默认在 `/tmp` 从生成逻辑重建，不是主 PCB 的增量续布。
- **评审导出（会改源文件）**：`bash scripts/export_all.sh review` 会重填并保存主 PCB、刷新布局 SVG、移除旧制造包；运行前保留基线，运行后审查差异。检查失败返回非零。
- **制造导出**：`bash scripts/export_all.sh fabrication` 仅在全部数字门禁通过后生成制造包。

## 4. 修改与验收底线

1. **先保留工作板，再做候选**。`hardware/` 含已编辑布线，生成脚本不能完整替代，禁止直接重建覆盖；候选经检查与评审后才替换。路径控制见 `pcb_common.py` 的 `AILINK_HW` / `AILINK_PCB`；逐脚本核对支持范围，`gen_product_lib.py` 仍直接写主工程库。
2. **不靠降低标准消除报错**。不得擅改产品脚序、保护拓扑、制造规则、实际焊盘尺寸或新增 DRC 忽略项；不得为清告警删掉仍有连接用途的过孔。布局与普通扇出可评估重排，旧坐标不等于产品硬约束。
3. **守住关键电气边界**。目标信号固定 3.3 V，5 V 针仅供电；保留 L2 连续地、背面 USB 的 L3 地参考与换层回流；HSE 只走正面且无信号过孔。详细参数查产品基线与工程规则。
4. **源文件与检查同步**。改电路、封装、位置或脚序时，同步相关生成逻辑、网络断言、坐标/禁布区域及固件映射，不得只改检查迎合错误实现。工程变更后重跑 ERC、重填铜 DRC/原理图一致性、产品与 USB 几何检查；路由算法变更还须跑回归测试。
5. **按证据交付**。交付结论须引用匹配当前源文件 SHA-256 的报告，并保留未验证项。`si_check.py` 仅做几何检查，不是阻抗仿真；数字通过、旧样机性能及示意 3D 模型均不替代当前工程的实物验证。

## 5. 协作文档

按 [docs-rules.md](docs-rules.md) 在事实所属文件就地更新；本文只保留索引、命令与关键约束，不复制参数、交付计数或过程日志。临时试验放仓库外或已隔离目录；尊重 [.gitignore](.gitignore)，不强制纳入生成物、第三方二进制或个人 AI 配置。开始修改前查看 `git status`，不要覆盖与当前任务无关的用户改动。
