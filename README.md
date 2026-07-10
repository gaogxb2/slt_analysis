# SLT 测试统计

基于 SUM 文件的 SLT 测试结果统计 Web 应用（FastAPI + SQLite + Vue3）。

## 功能

- SUM 文件解析与同轮（+1/+2）合并
- 多轮复测链（M2 → M2R1 → M2R2）展示
- Dashboard 总览、LOT 列表/详情、Bin/Site 分析、芯片追溯
- 目录扫描 + Web 上传导入
- 数据一致性校验告警

## 快速开始

```bash
./install.sh          # 安装 Python + npm 依赖
./start.sh seed         # 首次：扫描 testdata 入库
./start.sh dev          # 开发：后端 8000 + 前端 5173
./start.sh prod         # 生产：构建前端，单端口 8000
./start.sh backend      # 仅后端
```

## 启动（手动）

### 后端

```bash
cd backend
pip install -r requirements.txt
python seed.py          # 首次：扫描 testdata 入库
uvicorn app.main:app --reload --port 8000
# 或: python -m uvicorn app.main:app --reload --port 8000
```

API 文档：http://127.0.0.1:8000/docs

### 前端开发

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173
```

### 生产（单端口）

```bash
cd frontend && npm run build
cd ../backend && uvicorn app.main:app --port 8000
# 访问 http://127.0.0.1:8000
```

## 目录

```
backend/          FastAPI 服务、解析器、SQLite
frontend/         Vue3 前端
testdata/         样例 SUM 文件
testdata/testlogs/  由 SUM 生成的芯片 Log
docs/SUM_FORMAT.md  SUM 格式规范
docs/TESTLOG_FORMAT.md  Log 格式与 Web 对账
```

## 物料批次（LOT NO.）归组规则

满足以下**任一**条件，视为**同一批物料**在不同测试阶段/子批次的 LOT NO.：

1. **LOT NO. 完全相同**（例如 `JZADIWHMZ` 在 MT1、MT2、MT3 各测一次）
2. **除末尾 3 个字符外完全相同**，且末尾 3 字符符合 `AA\d`、`AB\d`、`AC\d`、`AD\d`、`AE\d`（`\d` 为任意数字）  
   - 示例：`AB0000AA1`（MT1）、`AB0000AB1`（MT2）、`AB0000AC1`（MT3）→ 同一物料 `AB0000A**`

在 Web 中每个 `(LOT NO., STAGE)` 仍作为独立 LOT 记录入库；归组规则用于跨批次追溯与物料级分析。

## SUM ↔ Log 对应关系

SUM 与芯片 Log 先归入同一 LOT：`(LOT NO., STAGE)` 对应 Log 的 `(CUSTOMER LOT ID, TEST STAGE)`。

单颗芯片的对账、关联、追溯使用以下 **4 项匹配键**（**不含 2DBarCode**；真实产线 Log 往往没有条码，文件名也不强制带条码）：

```
(round_key, test_mode, site, primary_die_id)
```

| 匹配键 | SUM 来源 | Log 来源 |
|--------|----------|----------|
| 批次（LOT 级） | `LOT NO.` + `STAGE` | `CUSTOMER LOT ID` + `TEST STAGE` |
| `round_key` | `Test Mode` 解析，如 `M2R1+2` → `M2R1` | `Test FLOW` 同样解析 |
| `test_mode` | 完整 `Test Mode`，如 `M2R1+2` | 完整 `Test FLOW` |
| `site` | Rawdata `Site` | `[BEGIN]` 的 `TEST SITE` |
| `primary_die_id` | `DieID` **分号前第一段** | **第一组** `DIEID_STR` |

### DieID 多 ID 规则

- **SUM**：`DieID` 可用分号 `;` 分隔多个 ID，如 `0CCE 8CD0 7D62 7248;0000 0000 0000 0000`
- **Log**：`[CHIPINFO]` 可有多组 `DIEID_STR`；匹配时仅用**第一组**
- 比较前去掉空格并转大写（`0CCE 8CD0` → `0CCE8CD0`）

### 兜底规则

若 `test_mode` 对不上，会忽略 `test_mode`，仅按 `(round_key, site, primary_die_id)` 再尝试关联。

### 不参与匹配的字段

- **`2DBarCode`**：SUM Rawdata 可有，Log 正文通常无；**不用于** SUM↔Log 匹配（仅作展示/追溯参考）
- Log 文件名中的条码后缀为可选；有则入库展示，无则不影响关联

## 样例数据

### AB0000A* 系列（同一物料，不同 STAGE）

| LOT NO.   | STAGE | Test Mode | SUM 文件 | Log 数 |
|-----------|-------|-----------|----------|--------|
| AB0000AB1 | MT2   | M2+1 … M2R2+2 | `testsum_M2+*.SUM` 等 | 64 |
| AB0000AA1 | MT1   | M1+1      | `testsum_AB0000AA1_M1+1.SUM` | 25 |
| AB0000AC1 | MT3   | M3+1      | `testsum_AB0000AC1_M3+1.SUM` | 25 |

### JZADIWHMZ（同一 LOT NO.，跨 STAGE）

| STAGE | Test Mode | SUM 文件 | 投入 | Log 数 |
|-------|-----------|----------|------|--------|
| MT1   | M1+1      | `testsum_JZADIWHMZ_MT1_M1+1.SUM` | 18 | 18 |
| MT2   | M2+1      | `testsum_JZADIWHMZ_MT2_M2+1.SUM` | 20 | 20 |
| MT3   | M3+1      | `testsum_JZADIWHMZ_MT3_M3+1.SUM` | 15 | 15 |

### AB0000AB1 多轮复测链（MT2）

| 轮次 | 合并后投入 | Pass | Fail |
|------|-----------|------|------|
| M2   | 50        | 40   | 10   |
| M2R1 | 10        | 6    | 4    |
| M2R2 | 4         | 2    | 2    |

### 重新生成扩展测试数据

```bash
cd backend
python scripts/generate_extended_testdata.py   # 生成 AB0000AA1/AC1、JZADIWHMZ 等 SUM
python scripts/generate_testlogs_from_sum.py   # 由全部 SUM 生成 testlogs
python seed.py                                 # 重新扫描入库
```
