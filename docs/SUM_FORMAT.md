# SUM 文件格式规则

本文档描述 SLT 测试结果汇总文件（`.SUM`）的各区块结构与字段格式，基于 `testdata/testsum.SUM` 样例归纳。

---

## 1. 文件整体结构

文件自上而下分为以下区块，各区块之间以空行分隔：

```
[TITLE 标题行]
[Lot 基本信息]
[各 Site 汇总] × N
[Total Site 汇总]
[Site Counter / Yield]
[Rawdata list]
```

---

## 2. 通用格式约定

### 2.1 键值对行

Lot 基本信息区采用 `键 : 值` 格式，注意以下特点：

| 特点 | 说明 |
|------|------|
| 冒号前空格 | **不统一**，有的字段冒号前有空格（如 `Total Fail : 10`），有的没有（如 `Total Pass: 40`） |
| 键名大小写 | 混用，如 `LOT NO.`、`Total Pass`、`STAGE` |
| 数值 | 整数直接写，百分比保留两位小数并带 `%` |

### 2.2 区块标题行

各区块标题由 `*` 号包裹文字标识，**星号数量不固定**，解析时不应依赖固定长度：

| 区块 | 标题示例 |
|------|----------|
| 文件标题 | `****TITLE xxx******` |
| Site 汇总 | `*****Site1 Summary  ******` |
| 全 Site 汇总 | `*****Total Site Summary   ***********` |
| 汇总结束 | `************** End ******` |
| Site 计数 | `******** Site Counter / Yield *******` |
| 原始数据 | `******Rawdata list*******` |

Site 编号嵌入标题中，格式为 `Site{N}`，N 为正整数。

---

## 3. Lot 基本信息

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| LOT NO. | 字符串 | `AB0000AB1` | 批次号 |
| Mater Traveler QTY | 整数 | `100` | 物料流转数量 |
| Input Testing QTY | 整数 | `50` | 实际投入测试数量 |
| START TIME | 日期时间 | `2020/02/02 01:01:01` | 格式 `YYYY/MM/DD HH:MM:SS` |
| Bin | 整数 | `1` | Bin 别，表示本批次采用的 Bin 分类方案编号 |
| Total Pass | 整数 | `40` | 通过总数 |
| Total Fail | 整数 | `10` | 失败总数 |
| Pass Yield | 百分比 | `80.00%` | 良率，保留两位小数 |
| Lot Start Date | 日期时间 | `2020/02/02 01:01:01` | 同 START TIME 格式 |
| Report Date | 日期时间 | `2020/02/02 05:01:01` | 报告生成时间 |
| STAGE | 字符串 | `MT2` | 测试阶段 |
| Test Mode | 字符串 | `M2+1` | 测试模式，见下方 **Test Mode 规则** |
| Temperature | 整数 | `99` | 测试温度（°C） |

### 3.1 Test Mode 规则

`Test Mode` 与 `STAGE` 配合，标识当前是第几轮测试及轮次内序号：

| 轮次 | Test Mode 格式 | 示例 | 说明 |
|------|----------------|------|------|
| 第 1 次（初测） | `{STAGE}+{n}` | `M2+1` | STAGE 为 `MT2` 时写作 `M2+1`，表示 MT2 阶段第一次测试 |
| 第 2 次（一复） | `{STAGE}R1+{n}` | `M2R1+1`、`M2R1+2` | `R1` 表示第一轮复测，`+n` 为轮次内子序号 |
| 第 3 次（二复） | `{STAGE}R2+{n}` | `M2R2+1`、`M2R2+2` | `R2` 表示第二轮复测 |
| 第 k 次复测 | `{STAGE}R{k-1}+{n}` | `M2R3+1` | 以此类推 |

`+n` 为**同一轮测试内的子批次序号**。同一 LOT、同一轮测试可能拆成多个 SUM 文件（如 `M2R2+1` 与 `M2R2+2`），需合并后才是该轮完整结果。

### 3.2 同轮子批次拆分与合并

**拆分场景：** 同一轮测试因产线并行、分批产出等原因，生成多个 SUM 文件，Test Mode 仅 `+n` 不同，其余 Lot 信息（`LOT NO.`、`STAGE`、`Bin`、`Lot Start Date` 等）一致。

**识别同一轮：** 去掉 `Test Mode` 末尾的 `+n` 后前缀相同，即为同一轮。例如 `M2R2+1` 与 `M2R2+2` 同属 M2R2 轮。

**合并计算规则：**

| 字段 / 区块 | 合并方式 |
|-------------|----------|
| `Input Testing QTY` | 各子文件相加 |
| `Total Pass` / `Total Fail` | 各子文件相加 |
| `Pass Yield` | 合并后重算：`Total Pass` / `Input Testing QTY` × 100%（**不能**对子文件良率取平均） |
| `START TIME` | 取所有子文件中最早时间 |
| `Report Date` | 取所有子文件中最晚时间 |
| Site Summary / Total Site Summary | 按 `(Software Category, Hardware Bin, Code)` 合并 `COUNT`，`Per(%)` 按合并后总数重算 |
| Site Counter / Yield | 按 Site 合并 `Pass`/`Fail`，良率重算 |
| Rawdata list | 拼接所有子文件记录；`DieID` 不应重复 |

**复测投入规则：**

- 每一轮复测仅投入**上一轮 Fail 的芯片**（非 Pass 的不复测）。
- 因此复测文件的 `Input Testing QTY` = 上一轮 `Total Fail`。
- `Mater Traveler QTY` 通常保持原始批次数量不变。
- `Lot Start Date` 一般与初测相同；`START TIME` / `Report Date` 为当轮测试时间。
- Rawdata 中 `DieID`、`2DBarCode` 与上一轮 Fail 记录一致，用于追溯同一颗芯片。

**测试数据文件示例**（见 `testdata/`）：

| 轮次 | 子文件 | Test Mode | Input QTY | Pass | Fail |
|------|--------|-----------|-----------|------|------|
| 初测 M2 | `testsum_M2+1.SUM` | M2+1 | 25 | 22 | 3 |
| 初测 M2 | `testsum_M2+2.SUM` | M2+2 | 25 | 18 | 7 |
| 初测 M2（合并） | — | M2 | **50** | **40** | **10** |
| 一复 M2R1 | `testsum_M2R1+1.SUM` | M2R1+1 | 5 | 3 | 2 |
| 一复 M2R1 | `testsum_M2R1+2.SUM` | M2R1+2 | 5 | 3 | 2 |
| 一复 M2R1（合并） | — | M2R1 | **10** | **6** | **4** |
| 二复 M2R2 | `testsum_M2R2+1.SUM` | M2R2+1 | 2 | 1 | 1 |
| 二复 M2R2 | `testsum_M2R2+2.SUM` | M2R2+2 | 2 | 1 | 1 |
| 二复 M2R2（合并） | — | M2R2 | **4** | **2** | **2** |

`testsum.SUM` 内容与 `testsum_M2+1.SUM` 相同（初测第一个子批次）。

**跨轮数量链：** M2 合并 Fail(10) → M2R1 合并投入(10) → M2R1 合并 Fail(4) → M2R2 合并投入(4)。

**一致性约束：**

- `Input Testing QTY` = `Total Pass` + `Total Fail`
- `Pass Yield` = `Total Pass` / `Input Testing QTY` × 100%

---

## 4. Site Summary（各 Site 汇总）

每个 Site 一个独立区块，结构相同。

### 4.1 表头（两行）

```
Software   Hardware    COUNT    Per(%)   Code    BinDESCRIPT
Category     Bin
```

第一行为列名，第二行为子列名（Software Category / Hardware Bin）。

### 4.2 数据行

| 列 | 格式 | 示例 | 说明 |
|----|------|------|------|
| Software Category | 整数 | `1000` | 软件 Bin 分类 |
| Hardware Bin | 整数 | `1` | 硬件 Bin 编号 |
| COUNT | 整数 | `8` | 该 Bin 的芯片数量 |
| Per(%) | 百分比 | `80.00%` | 占该 Site 测试总数的比例 |
| Code | 整数 | `1000` | 错误/结果代码 |
| BinDESCRIPT | 字符串 | `PASS` / `E2` | Bin 描述 |

**Pass 记录典型值：**

| Software Category | Hardware Bin | Code | BinDESCRIPT |
|-------------------|--------------|------|-------------|
| 1000 | 1 | 1000 | PASS |

**Fail 记录典型值：**

| Software Category | Hardware Bin | Code | BinDESCRIPT |
|-------------------|--------------|------|-------------|
| 1111 | 2 | 4000 | E2 |
| 1212 | 3 | 4001 | E3 |
| 1313 | 4 | 4002 | E1 |

**一致性约束：**

- 同一 Site 内所有行的 `COUNT` 之和 = 该 Site 测试总数
- 同一 Site 内所有行的 `Per(%)` 之和 = 100%

---

## 5. Total Site Summary（全 Site 汇总）

结构与 Site Summary 相同，数据为所有 Site 的合并统计。

**一致性约束：**

- 各 Bin 的 `COUNT` = 所有 Site 对应 Bin 的 `COUNT` 之和
- `Per(%)` 分母为 `Input Testing QTY`
- 区块末尾紧跟 `************** End ******` 结束标记

---

## 6. Site Counter / Yield

### 6.1 表头

```
Site No     Site Counter    Pass   Fail   Site Yield(%)
```

### 6.2 数据行

| 列 | 格式 | 示例 | 说明 |
|----|------|------|------|
| Site No | 整数（前导空格对齐） | `1` | Site 编号 |
| Site Counter | 整数 | `10` | 该 Site 测试总数 |
| Pass | 整数 | `8` | 通过数 |
| Fail | 整数 | `2` | 失败数 |
| Site Yield(%) | 百分比 | `80.00%` | 该 Site 良率 |

**一致性约束：**

- `Site Counter` = `Pass` + `Fail`
- `Site Yield(%)` = `Pass` / `Site Counter` × 100%
- 所有 Site 的 `Site Counter` 之和 = `Input Testing QTY`
- 所有 Site 的 `Pass` 之和 = `Total Pass`
- 所有 Site 的 `Fail` 之和 = `Total Fail`

---

## 7. Rawdata list（原始数据列表）

### 7.1 区块标题

```
******Rawdata list*******
```

### 7.2 单行格式

每颗芯片一条记录，字段以逗号分隔，采用 `Key=Value` 形式：

```
ErrorCode={code},SoftwareBin={bin},DieID={id},Tj={tj},Temperature={temp},Site={site},BiosTime={bios},TestTime={test},2DBarCode={barcode},booton={booton},Tested={tested}
```

### 7.3 各字段规则

| 字段 | 格式 | 示例 | 说明 |
|------|------|------|------|
| ErrorCode | 整数 | `1000` / `4000` | 错误代码；Pass 为 `1000`，Fail 为 `4xxx` |
| SoftwareBin | 整数 | `1000` / `1111` | 软件 Bin，与 Summary 中 Software Category 对应 |
| DieID | 4 段 16 进制，空格分隔 | `0CCE 8CD0 7D62 7248` | 芯片唯一标识，每段 4 位大写十六进制 |
| Tj | 4 个浮点数，点号连接 | `42.1.41.5.51.1.48.2` | 结温读数，格式 `{v1}.{v2}.{v3}.{v4}`，每位保留 1 位小数 |
| Temperature | 整数 | `99` | 测试温度，与 Lot 基本信息中一致 |
| Site | 整数 | `1` | 测试 Site 编号 |
| BiosTime | 浮点数 + `s` 后缀 | `121.3s` | BIOS 启动耗时（秒） |
| TestTime | 浮点数（无后缀） | `31.9` | 测试耗时（秒） |
| 2DBarCode | 数字字符串 | `026577442871` | 二维条码，12 位数字 |
| booton | 时间-日期 | `13:13:13-2026/01/01` | 启动时间（HH:MM:SS-YYYY/MM/DD） |
| Tested | 时间-日期 | `13:13:14-2026/01/01` | 测试完成时间 |

Pass/Fail 由 **ErrorCode** 判定：`10` 开头为 Pass（如 `1000`），否则 Fail（如 `4000`）。

### 7.4 ErrorCode 与 Bin 对应关系

| 结果 | ErrorCode | SoftwareBin | Summary Code | BinDESCRIPT |
|------|-----------|-------------|--------------|-------------|
| Pass | 1000 | 1000 | 1000 | PASS |
| Fail (E2) | 4000 | 1111 | 4000 | E2 |
| Fail (E3) | 4001 | 1212 | 4001 | E3 |
| Fail (E1) | 4002 | 1313 | 4002 | E1 |

### 7.5 一致性约束

- Rawdata 总行数 = `Input Testing QTY`
- ErrorCode 以 `10` 开头的记录数 = `Total Pass`
- 其余 ErrorCode 的记录数 = `Total Fail`
- 按 Site 分组统计应与 Site Summary、Site Counter 区块数据一致
- 按 SoftwareBin / ErrorCode 分组统计应与 Total Site Summary 一致

---

## 8. 解析建议

1. **区块识别**：用包含关键字（如 `Summary`、`Rawdata list`、`Site Counter`）的行定位区块，不要依赖 `*` 的精确数量。
2. **键值对解析**：Lot 信息区用正则 `^(.+?)\s*:\s*(.+)$` 提取，兼容冒号前有无空格。
3. **Summary 表格**：跳过两行表头后，按空格分列解析数据行；百分比列含 `%` 后缀。
4. **Rawdata 行**：按逗号 split 后再按首个 `=` split 为键值；`DieID` 值中不含逗号。
5. **容错**：字段名拼写（如 `Mater Traveler`、`BinDESCRIPT`）以文件原文为准，兼容大小写，不做修正。
6. **同轮合并**：按 `LOT NO.` + Test Mode 前缀（去掉 `+n`）分组，合并 Rawdata 后重算汇总；子文件良率不可直接平均。

---

## 9. 参考样例

完整样例见 `testdata/`：

- 初测：`testsum_M2+1.SUM`、`testsum_M2+2.SUM`（`testsum.SUM` = M2+1）
- 一复：`testsum_M2R1+1.SUM`、`testsum_M2R1+2.SUM`
- 二复：`testsum_M2R2+1.SUM`、`testsum_M2R2+2.SUM`
