# Testlog 文件格式规则

本文档描述单次芯片测试日志（`testlog.log` / `*.log`）的结构与字段含义，以及与 SUM 汇总文件的对应关系。

---

## 1. 文件定位

| 概念 | 说明 |
|------|------|
| **粒度** | **1 个 log 文件 = 1 颗芯片 × 1 次测试会话** |
| **与 SUM 关系** | SUM 为批次汇总；每颗芯片每次测试各生成 **1 个** log，多个 log 汇总为 1 个 SUM |
| **样例目录** | [`testdata/testlogs/`](../testdata/testlogs/)（由 SUM 批量生成） |

---

## 2. 整体结构

```
[BEGIN]              会话头（批次、Site、Stage、Flow、开始时间）
  [ONETEST]          单项测试 × N
  [ONETEST END]
  ...
[CHIPINFO]           芯片级汇总（Bin、P/F、DieID 等）
[CHIP END]
```

---

## 3. 通用格式约定

- 键值对格式为 `键 : 值`，**冒号前空格不统一**（与 SUM 相同，解析需容错）
- `*` 装饰行仅为分隔，**星号数量不固定**
- 区块标记：`[BEGIN]`、`[ONETEST]`、`[ONETEST END]`、`[CHIPINFO]`、`[CHIP END]`

---

## 4. [BEGIN] 会话头

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| CUSTOMER LOT ID | 字符串 | `AB0000AB1` | 客户批次号，对应 SUM `LOT NO.` |
| TEST SITE | 整数 | `1` | 测试 Site，对应 Rawdata `Site` |
| TEST STAGE | 字符串 | `MT2` | 测试阶段，对应 SUM `STAGE` |
| Test FLOW | 字符串 | `M2R1+1` | 测试流，对应 SUM `Test Mode` |
| TEST START | 日期时间 | `2020/02/02_10:00:01` | 开始时间；日期与时间以 **`_`** 连接（SUM 为空格） |

---

## 5. [ONETEST] 单项测试

每个测试项一个区块，顺序执行。

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| TEST_TXT | 字符串 | `AAA_TEST` | 测试项 / 程序名 |
| PATTERN | 字符串 | 空或 Pattern 名 | 可为空 |
| RESULT | 十六进制 | `0x1` / `0x4000` | 测试结果码；Pass 项常为 `0x1`，Fail 项可为 ErrorCode |
| P_F | `P` / `F` | `P` | 该项 Pass / Fail |
| TEST_TIME | 整数 | `15200` | 该项耗时，单位 **毫秒（ms）** |

### 5.1 与 CHIPINFO 的 Pass/Fail 规则

```
任一 ONETEST 的 P_F = F  →  CHIPINFO 的 P_F = F
全部 ONETEST 的 P_F = P  →  CHIPINFO 的 P_F = P
```

CHIPINFO 表示**所有 ONETEST 的汇总结果**，不是独立判定。

---

## 6. [CHIPINFO] 芯片汇总

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| SOFT_BIN | 整数 | `1000` | 软件 Bin，对应 Rawdata `SoftwareBin` |
| P_F | `P` / `F` | `P` | 芯片最终 Pass/Fail，对应 Rawdata `BootOn` |
| TEST_TIME | 浮点 + `s` | `300s` | 芯片总测试时间（秒） |
| TEST_START | 日期时间 | `2020/02/02_10:00:01` | 同 [BEGIN] 的 TEST START |

### 6.1 DieID 字段组（可重复多组）

一颗芯片可有 **多个 DieID**，每组包含：

| 字段 | 说明 |
|------|------|
| DIEID_STR | Die 字符串 ID（如 `7C6A F229 D06A 617D`） |
| DIEID_NAME | Die 命名 ID（如 `DIE_7C6A617D`） |
| DIEID_LOT | Lot 片段 |
| DIEID_WAFER | Wafer 号 |
| DIEID_X | Die X 坐标 |
| DIEID_Y | Die Y 坐标 |

**与 SUM 的对应：**

- SUM Rawdata 中的 `DieID` **仅对应 CHIPINFO 里第一组 `DIEID_STR`**
- 第二组及以后为同一物理芯片的附加标识，不出现在 SUM 的 `DieID` 字段中

---

## 7. SUM ↔ Testlog 字段映射

| Testlog | SUM Rawdata / Meta |
|---------|-------------------|
| CUSTOMER LOT ID | `LOT NO.` |
| TEST STAGE | `STAGE` |
| Test FLOW | `Test Mode` |
| TEST SITE | `Site` |
| 第一组 DIEID_STR | `DieID` |
| SOFT_BIN | `SoftwareBin` |
| P_F（CHIPINFO） | `BootOn`（PASS/FAIL） |
| — | `ErrorCode`（Fail 时，与 SOFT_BIN / RESULT 对应） |
| — | `2DBarCode`（log 文件名或扩展字段可关联） |

---

## 8. 文件命名建议

批量生成时推荐：

```
testdata/testlogs/{TestMode}/{LOT}_S{Site}_{DieID紧凑}_{2DBarCode}.log
```

示例：

```
testdata/testlogs/M2R1+1/AB0000AB1_S1_7C6AF229D06A617D_660781151148.log
```

---

## 9. 解析建议

1. 用 `[ONETEST]` / `[CHIPINFO]` 等标记分块，不依赖 `*` 行长度。
2. 键值行正则：`^(.+?)\s*:\s*(.*)$`，兼容缺冒号或空格不一致（需容错）。
3. 解析后**校验**：CHIPINFO.P_F 应与所有 ONETEST.P_F 的汇总规则一致。
4. 关联 SUM：`(LOT NO., Test Mode, Site, 第一 DIEID_STR)` 或 `(LOT, Test Mode, 2DBarCode)`。

---

## 10. 批量生成

由 SUM 文件生成 testlog（每颗芯片一条）：

```bash
cd backend
python scripts/generate_testlogs_from_sum.py
```

默认读取 `testdata/*.SUM`（跳过与 `testsum_M2+1.SUM` 重复的 `testsum.SUM`），输出到 `testdata/testlogs/`。

---

## 11. 参考样例

- 模板：[`testlog.log`](../testlog.log)
- 生成样例：[`testdata/testlogs/`](../testdata/testlogs/)

---

## 12. Web 对账

启动 Web 应用后（`./start.sh dev`），可通过以下功能将 Log 与 SUM 联合比对：

| 功能 | 路径 / 入口 | 说明 |
|------|-------------|------|
| SUM/Log 对账页 | `/lots/{LOT}/reconcile` | LOT 详情顶部「SUM/Log 对账」按钮 |
| 对账 API | `GET /api/lots/{lot_no}/reconcile` | 返回 matched / sum_only / log_only / mismatch 明细 |
| Log 详情 | `GET /api/chip-logs/{id}` | 单条 Log（BEGIN + ONETEST + CHIPINFO） |
| Fail 下钻 | `GET /api/dies/{die_record_id}/log` | 从 SUM die 反查关联 Log |
| Log 扫描入库 | `POST /api/import/scan-logs` | 扫描 `testdata/testlogs/` |

**关联键**：`lot_no` + `test_mode`（Test FLOW）+ `site` + 第一组 `DIEID_STR` + `barcode`。

**对账状态**：

- `matched`：SUM 与 Log 均已找到且字段一致
- `sum_only`：有 SUM 无 Log（log 丢失）
- `log_only`：有 Log 无 SUM（未汇总进 SUM）
- `mismatch`：已匹配但 P/F、Bin、Site、Flow、时间等不一致

**典型用法**：

1. 打开对账页查看 `sum_only` / `mismatch` 列表，确认信息是否丢失或对不上
2. LOT 详情 Fail 芯片点击「查看 Log」，在抽屉 ONETEST 表中定位 Fail 项
