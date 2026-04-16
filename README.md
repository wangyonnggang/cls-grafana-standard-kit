# CLS to Grafana Standard Kit

A generic toolkit for quickly migrating CLS dashboards to Grafana using the Tencent CLS datasource plugin.

## Contents
- `cls_grafana_migrator.py`: Main migration script
- `cls_migrator_config.example.json`: Configuration template
- `CLS_Grafana_Customer_Reuse_Guide.md`: Detailed implementation guide

## 1-Minute Quick Start

1. Copy the template and fill in your environment values:
```bash
cp cls_migrator_config.example.json cls_migrator_config.json
```

2. Update configuration values:
- CLS: `secretId` / `secretKey` / `region` / `endpoint`
- Grafana: `url` / `user` / `password`
- Dashboards to migrate: `migration.keepDashboards`

3. Run migration:
```bash
python3 cls_grafana_migrator.py --config cls_migrator_config.json
```

4. Validate:
- Open dashboard URLs printed by the script
- Check built-in `/api/ds/query` smoke results (`frames > 0`)

## Recommended Reuse Pattern (Multi-Customer)
- Keep one dedicated `config.json` per customer/environment
- Archive migration logs and exported JSON artifacts for delivery
- Validate on one test dashboard first, then scale to bulk migration

## Important
Use the plugin-required target schema:
- `serviceType = logService`
- `logServiceParams = { region, TopicId, Query, SyntaxRule, format }`

Do **not** use legacy flat fields (`TopicId` / `Query`) as the final structure.
