# M3 F6 性能与资源证据状态

所有计时文件均保留，不覆盖失败结果。接受门槛来自 [F6 合同](../post-m2-f3-f6-action-plan.md)：producer 和独立 verifier 各自测试 200/400/800/1600 碎片；2 次预热、7 次样本、3 个干净进程；400→800 和 800→1600 的每轮中位数比均不超过 2.8。基线与候选在每个尺寸使用相同预先声明的批次，原始批次至少 20 ms。每组还逐尺寸断言候选和冻结的二次参考实现产生相同 parent 范围。

## 结果

- [v5](m3-f6-fragment-2026-10-15-v5-failed.md)：同尺寸固定批次下 800-part 候选批次最低为 17.556 ms，低于门槛，未形成正式结果。
- [v2](m3-f6-fragment-2026-10-15-v2.json) 是失败试跑；[v3](m3-f6-fragment-2026-10-15-v3.json) 和 [v4](m3-f6-fragment-2026-10-15-v4.json) 的比值通过，但新旧实现批次数不同，因此均不能计为合同验收。
- [v6](m3-f6-fragment-2026-10-15-v6.json)：计时门槛和相同批次通过，但第二轮 verifier 800→1600 为 2.850，超出 2.8。
- [v8](m3-f6-fragment-2026-10-15-v8.json)：相同批次和 20 ms 门槛均通过。第三轮 producer 400→800 为 3.215，verifier 为 3.348；整体 `pass=false`。
- [v4](m3-f6-fragment-2026-10-15-v4.json)：三轮比值曾通过，但基线和候选使用不同的批次，不符合最终冻结协议，不能作为验收结果。
- [1600-part 全链路 v2](m3-f6-task-1600-2026-10-15-v2.json)：旧源码指纹下的真实 GPX 任务/重放三轮通过（派生 71.2–80.4 秒，reload 70.7–85.5 秒，RSS 约 234–247 MiB），但**不代表最终 verifier 源码**。最终源码的 [v3 task trial](m3-f6-task-1600-2026-10-15-v3-failed.md) 第二轮触发 `PROCESSING_TIME_LIMIT_EXCEEDED`，单轮复现相同；因此当前 1600-part task 默认 wall-time gate 也未通过。

计时环境为 Python 3.12.14、Linux 6.18.44、Shapely 2.1.2、GEOS 3.13.1、Xeon Platinum 8573C。进程绑定到可见 CPU 0，但执行器未提供独占 CPU/固定频率保证；v8 的各尺寸测量波动与共享主机抢占一致。不能把失败轮次平均掉，也不能把 v4 改称通过。基础 admission、worker deadline/RSS enforcement 和旧源码指纹的全链路结果有证据；**最终源码的 F6 scaling 与 task wall-time gates 均未接受**，需要专用/可重复 runner 重测。可选 i7-8700 的 1 秒/512 MiB 声明未测试。

Python/依赖/源码和 artifact manifest 指纹见各 JSON 文件。基准脚本位于 [`scripts/benchmark_m3_fragmentation.py`](../../scripts/benchmark_m3_fragmentation.py)，端到端脚本位于 [`scripts/benchmark_m3_task_1600.py`](../../scripts/benchmark_m3_task_1600.py)。

## 当前实现验证记录

当前源代码全量 Python 测试 **402/402 通过**；已安装非 editable wheel 在仓库外全量测试 **402/402 通过**。Schema 为 260/260、语义 56/56、edge coverage 29/29；M2E/M2F Node runtime tests 均通过。wheel SHA-256：`88111d50eac52a13a79954855c96f4dbe3cd9997bf2e929610305bdabcddd238`。外部测试使用复制的 `tests/`、`schemas/` 和只作为测试 harness 的 `scripts/`，Python 包从虚拟环境 `site-packages` 导入；忽略 `__pycache__` 后，与 `src/target_area_route_reconstruction` 逐文件一致。

这些正确性/安装测试通过不覆盖上面的 F6 性能失败。PR exact-head GitHub CI 和独立 M3 退出审计仍待执行。
