# CLS 到 Grafana 标准操作指导包（通用版）

## 1. 目标
将 CLS Dashboard 标准化迁移到 Grafana，并确保“可导入、可查询、可验证、可复用”。

---

## 2. 适用范围
- 任意腾讯云 CLS 日志服务
- 已安装 CLS Grafana 插件的 Grafana 环境
- 适用于 PoC、交付实施、批量客户复用

---

## 3. 前置条件
1. Grafana 可访问（建议 10.4.x）
2. 已安装插件：`tencent-cls-grafana-datasource`
3. 已准备 CLS API 密钥（SecretId / SecretKey）
4. 已明确 CLS 地域和 API endpoint（示例：`cls.ap-singapore.tencentcloudapi.com`）

---

## 4. 指导包内容
1. `cls_grafana_migrator.py`：迁移主程序
2. `cls_migrator_config.example.json`：配置模板
3. 本文档：`CLS_Grafana_客户复用手册.md`

---

## 5. 快速开始

### 5.1 配置
复制模板：

```bash
cp cls_migrator_config.example.json cls_migrator_config.json
```

按实际环境填写：
- `cls.secretId`
- `cls.secretKey`
- `cls.region`
- `cls.endpoint`
- `grafana.url`
- `grafana.user`
- `grafana.password`
- `grafana.datasource.name`
- `migration.keepDashboards`
- `migration.exportDir`

### 5.2 执行

```bash
python3 cls_grafana_migrator.py --config cls_migrator_config.json
```

---

## 6. 工具自动完成内容
1. 创建或更新 CLS 数据源（含 SecretKey 安全写入）
2. 调用 CLS API 拉取 Dashboard 列表
3. 转换为 Grafana 可导入格式
4. 导入指定 Dashboard
5. 导出转换后的 Grafana JSON（用于二次复用）
6. 执行 `/api/ds/query` 冒烟检查
7. 输出 Dashboard 访问链接

---

## 7. 关键技术规范（必须遵守）

### 7.1 查询结构规范
每个 target 必须是以下结构：

```json
{
  "serviceType": "logService",
  "logServiceParams": {
    "region": "<region>",
    "TopicId": "<topicId>",
    "Query": "<query>",
    "SyntaxRule": 1,
    "format": "Graph"
  }
}
```

禁止使用旧平铺字段（仅 `TopicId/Query`）作为最终结构。

### 7.2 endpoint 规范
`cls.endpoint` 必须使用 CLS 正确域名格式（示例：`cls.ap-singapore.tencentcloudapi.com`）。

---

## 8. 验收标准
- 数据源 Health：`OK`
- `/api/ds/query` 返回 `frames > 0`（至少一个目标 panel）
- 仪表盘可打开，面板可正常渲染
- 导出目录存在 `.grafana.json` 文件

---

## 9. 常见问题排查

### Q1：Health OK 但面板无数据
优先检查：
1. target 是否为 `serviceType + logServiceParams`
2. `secureJsonFields.secretKey` 是否存在
3. TopicId / Query 是否为空
4. 时间范围内是否存在日志

### Q2：只部分面板有数据
多数为业务日志分布问题，先核对对应事件在当前时间窗是否存在。

### Q3：如何给下一个客户快速复用
仅需更换配置文件，不改脚本：
1. 复制模板
2. 修改环境参数
3. 执行脚本

---

## 10. 标准交付建议
交付客户时打包这三件：
- `cls_grafana_migrator.py`
- `cls_migrator_config.example.json`
- `CLS_Grafana_客户复用手册.md`

客户侧执行成本：**一份配置 + 一条命令**。
