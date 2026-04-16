# CLS to Grafana Standard Kit

通用版：用于将 CLS Dashboard 快速迁移到 Grafana（Tencent CLS 插件）。

## 目录
- `cls_grafana_migrator.py`：迁移主程序
- `cls_migrator_config.example.json`：配置模板
- `CLS_Grafana_客户复用手册.md`：详细操作手册

## 1 分钟快速开始

1. 复制模板并填写参数：
```bash
cp cls_migrator_config.example.json cls_migrator_config.json
```

2. 按你的环境填写：
- CLS：`secret_id` / `secret_key` / `region`
- Grafana：`url` / `username` / `password`
- 需要迁移的 dashboard 列表

3. 运行迁移：
```bash
python3 cls_grafana_migrator.py --config cls_migrator_config.json
```

4. 验收：
- 打开脚本输出的 Grafana dashboard URL
- 查看脚本内置的 `/api/ds/query` 冒烟结果（frames > 0）

## 推荐做法（给客户批量复用）
- 每个客户保留一份独立的 `config.json`
- 统一保留迁移日志和导出 JSON 作为交付物
- 先做一个测试 dashboard 验证，再全量迁移

## 注意
- 必须使用 CLS 插件要求的标准查询结构：
  - `serviceType = logService`
  - `logServiceParams = { region, TopicId, Query, SyntaxRule, format }`
- 不要用旧平铺结构（仅 `TopicId/Query`）作为最终结构。
