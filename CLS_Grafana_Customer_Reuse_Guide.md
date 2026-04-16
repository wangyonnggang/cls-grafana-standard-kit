# CLS to Grafana Standard Migration Guide (Generic Edition)

## 1. Objective
Standardize migration from CLS dashboards to Grafana and ensure the result is importable, queryable, verifiable, and reusable.

---

## 2. Scope
- Any Tencent Cloud CLS environment
- Any Grafana instance with the Tencent CLS datasource plugin installed
- Suitable for PoC, delivery implementation, and multi-customer reuse

---

## 3. Prerequisites
1. Grafana is reachable (10.4.x recommended)
2. Plugin installed: `tencent-cls-grafana-datasource`
3. CLS API credentials prepared (`SecretId` / `SecretKey`)
4. CLS region and API endpoint confirmed (example: `cls.ap-singapore.tencentcloudapi.com`)

---

## 4. Package Contents
1. `cls_grafana_migrator.py`: Main migration script
2. `cls_migrator_config.example.json`: Configuration template
3. `CLS_Grafana_Customer_Reuse_Guide.md`: This guide

---

## 5. Quick Start

### 5.1 Configure
Copy template:

```bash
cp cls_migrator_config.example.json cls_migrator_config.json
```

Fill values:
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

### 5.2 Execute

```bash
python3 cls_grafana_migrator.py --config cls_migrator_config.json
```

---

## 6. What the Tool Does Automatically
1. Creates or updates CLS datasource in Grafana (including secure secret key write)
2. Pulls dashboard list from CLS API
3. Converts dashboards into Grafana-importable schema
4. Imports selected dashboards
5. Exports converted Grafana JSON for reuse
6. Runs `/api/ds/query` smoke checks
7. Prints dashboard URLs

---

## 7. Required Technical Standards

### 7.1 Query Target Structure
Each target must use:

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

Legacy flat fields (`TopicId` / `Query` only) must not be used as final storage structure.

### 7.2 Endpoint Standard
`cls.endpoint` must use valid CLS domain format, e.g. `cls.ap-singapore.tencentcloudapi.com`.

---

## 8. Acceptance Criteria
- Datasource health: `OK`
- `/api/ds/query` returns `frames > 0` for at least one target panel
- Dashboards open and panels render correctly
- Export directory contains `.grafana.json` artifacts

---

## 9. Troubleshooting

### Q1: Datasource health is OK but panels show no data
Check in order:
1. Target schema is `serviceType + logServiceParams`
2. `secureJsonFields.secretKey` exists
3. `TopicId` / `Query` are not empty
4. Logs exist within selected time range

### Q2: Only part of the panels show data
Usually data distribution issue. Verify relevant events exist in the selected time window.

### Q3: How to reuse quickly for next customer
No script change needed:
1. Copy template config
2. Update environment values
3. Run the script

---

## 10. Delivery Recommendations
Package these files for customer delivery:
- `cls_grafana_migrator.py`
- `cls_migrator_config.example.json`
- `CLS_Grafana_Customer_Reuse_Guide.md`

Customer execution cost: **one config file + one command**.
