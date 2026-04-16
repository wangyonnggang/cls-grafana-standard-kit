#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reusable CLS -> Grafana migration tool.

Capabilities:
1) Pull dashboards from CLS API
2) Convert target/query schema for tencent-cls-grafana-datasource
3) Create or update Grafana CLS datasource automatically
4) Import selected (or all matched) dashboards
5) Export converted Grafana dashboard JSON for reuse
6) Run ds/query smoke checks

Usage:
python cls_grafana_migrator.py --config cls_migrator_config.json
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, obj: dict) -> None:
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


class Tc3Signer:
    def __init__(self, secret_id: str, secret_key: str, region: str, endpoint: str):
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.region = region
        self.endpoint = endpoint

    def build_headers(self, action: str, payload_str: str) -> Dict[str, str]:
        ts = int(time.time())
        date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        ct = "application/json; charset=utf-8"

        canonical = (
            "POST\n/\n\n"
            f"content-type:{ct}\n"
            f"host:{self.endpoint}\n\n"
            "content-type;host\n"
            f"{hashlib.sha256(payload_str.encode()).hexdigest()}"
        )

        scope = f"{date}/cls/tc3_request"
        string_to_sign = (
            "TC3-HMAC-SHA256\n"
            f"{ts}\n"
            f"{scope}\n"
            f"{hashlib.sha256(canonical.encode()).hexdigest()}"
        )

        def hmac256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        k = hmac256(("TC3" + self.secret_key).encode(), date)
        k = hmac256(k, "cls")
        k = hmac256(k, "tc3_request")
        sig = hmac.new(k, string_to_sign.encode(), hashlib.sha256).hexdigest()

        auth = (
            "TC3-HMAC-SHA256 "
            f"Credential={self.secret_id}/{scope}, "
            "SignedHeaders=content-type;host, "
            f"Signature={sig}"
        )

        return {
            "Content-Type": ct,
            "Host": self.endpoint,
            "X-TC-Action": action,
            "X-TC-Version": "2020-10-16",
            "X-TC-Timestamp": str(ts),
            "X-TC-Region": self.region,
            "Authorization": auth,
        }


class ClsClient:
    def __init__(self, signer: Tc3Signer):
        self.signer = signer

    def call(self, action: str, payload: dict) -> dict:
        payload_str = json.dumps(payload)
        headers = self.signer.build_headers(action, payload_str)
        req = urllib.request.Request(
            f"https://{self.signer.endpoint}",
            data=payload_str.encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def list_dashboards(self) -> List[dict]:
        out = []
        offset = 0
        while True:
            resp = self.call("DescribeDashboards", {"Offset": offset, "Limit": 100})
            infos = resp.get("Response", {}).get("DashboardInfos", [])
            total = resp.get("Response", {}).get("TotalCount", 0)
            out.extend(infos)
            if len(out) >= total:
                break
            offset += 100
        return out


class GrafanaClient:
    def __init__(self, url: str, user: str, password: str):
        self.url = url.rstrip("/")
        creds = base64.b64encode(f"{user}:{password}".encode()).decode()
        self.headers = {
            "Authorization": "Basic " + creds,
            "Content-Type": "application/json",
        }

    def api(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        req = urllib.request.Request(
            self.url + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=self.headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="ignore")
            try:
                return json.loads(txt)
            except Exception:
                return {"status": e.code, "error": txt}

    def get_datasources(self) -> List[dict]:
        ds = self.api("GET", "/api/datasources")
        return ds if isinstance(ds, list) else []

    def search_dashboards(self, limit: int = 500) -> List[dict]:
        data = self.api("GET", f"/api/search?type=dash-db&limit={limit}")
        return data if isinstance(data, list) else []


def ensure_cls_datasource(gf: GrafanaClient, cfg: dict) -> dict:
    ds_name = cfg["grafana"]["datasource"]["name"]
    ds_type = cfg["grafana"]["datasource"]["type"]

    region = cfg["cls"]["region"]
    endpoint = cfg["cls"]["endpoint"]
    secret_id = cfg["cls"]["secretId"]
    secret_key = cfg["cls"]["secretKey"]

    payload = {
        "name": ds_name,
        "type": ds_type,
        "access": "proxy",
        "url": f"https://{endpoint}",
        "basicAuth": False,
        "jsonData": {
            "region": region,
            "secretId": secret_id,
            "ClsUrl": endpoint,
            "url": endpoint,
        },
        "secureJsonData": {
            "secretKey": secret_key,
        },
    }

    current = None
    for d in gf.get_datasources():
        if d.get("name") == ds_name and d.get("type") == ds_type:
            current = d
            break

    if current:
        uid = current["uid"]
        payload["uid"] = uid
        ret = gf.api("PUT", f"/api/datasources/uid/{uid}", payload)
        if ret.get("status") not in ["success", "OK"]:
            raise RuntimeError(f"Failed to update datasource: {ret}")
        detail = gf.api("GET", f"/api/datasources/uid/{uid}")
        return {"uid": uid, "type": ds_type, "name": ds_name, "detail": detail}

    ret = gf.api("POST", "/api/datasources", payload)
    if ret.get("datasource") and ret["datasource"].get("uid"):
        uid = ret["datasource"]["uid"]
    elif ret.get("uid"):
        uid = ret["uid"]
    else:
        raise RuntimeError(f"Failed to create datasource: {ret}")

    detail = gf.api("GET", f"/api/datasources/uid/{uid}")
    return {"uid": uid, "type": ds_type, "name": ds_name, "detail": detail}


def panel_format(panel_type: str) -> str:
    p = (panel_type or "").lower()
    if p == "table":
        return "Table"
    if p == "logs":
        return "Log"
    return "Graph"


def map_panel_type(panel_type: str) -> str:
    mp = {
        "bar": "barchart",
        "pie": "piechart",
        "singlestat": "stat",
    }
    return mp.get(panel_type, panel_type)


def normalize_target(raw_t: dict, ds_ref: dict, cls_region: str, ptype: str, ref_id: str) -> dict:
    t = dict(raw_t or {})
    query = (t.get("Query") or t.get("query") or "").strip()
    topic = t.get("TopicId") or t.get("topicId") or t.get("topicID") or ""
    syntax = t.get("SyntaxRule", 1)
    max_num = t.get("MaxResultNum")

    lsp = {
        "region": t.get("region") or cls_region,
        "TopicId": topic,
        "Query": query,
        "SyntaxRule": syntax,
        "format": panel_format(ptype),
        "TimeZone": "UTC",
    }
    if max_num is not None:
        lsp["MaxResultNum"] = max_num

    out = {
        "refId": t.get("refId", ref_id),
        "datasource": ds_ref,
        "serviceType": "logService",
        "logServiceParams": lsp,
    }
    if "hide" in t:
        out["hide"] = t["hide"]
    return out


def convert_panel(panel: dict, ds_ref: dict, cls_region: str, id_counter: List[int]) -> dict:
    id_counter[0] += 1
    np = dict(panel)
    np["id"] = id_counter[0]

    ptype = map_panel_type(np.get("type", ""))
    np["type"] = ptype
    np["datasource"] = ds_ref

    raw_targets = []
    if isinstance(panel.get("targets"), list) and panel.get("targets"):
        raw_targets = panel.get("targets")
    elif isinstance(panel.get("target"), dict):
        raw_targets = [panel.get("target")]

    targets = []
    for idx, rt in enumerate(raw_targets):
        ref = chr(ord("A") + idx) if idx < 26 else f"A{idx}"
        targets.append(normalize_target(rt, ds_ref, cls_region, ptype, ref))
    np["targets"] = targets

    np.pop("target", None)

    if isinstance(panel.get("panels"), list):
        np["panels"] = [convert_panel(p, ds_ref, cls_region, id_counter) for p in panel["panels"]]

    return np


def convert_dashboard(src: dict, ds_ref: dict, cls_region: str) -> dict:
    raw_data = src.get("Data")
    if isinstance(raw_data, str):
        try:
            data = json.loads(raw_data)
        except Exception:
            data = {}
    else:
        data = raw_data or {}

    counter = [0]
    panels = [convert_panel(p, ds_ref, cls_region, counter) for p in data.get("panels", [])]

    dashboard = {
        "id": None,
        "uid": str(uuid.uuid4()),
        "title": src.get("DashboardName", "Imported from CLS"),
        "tags": ["cls-import", "portable-migrator"],
        "timezone": data.get("timezone", "browser"),
        "schemaVersion": data.get("schemaVersion", 36),
        "version": 0,
        "refresh": data.get("refresh", "10s"),
        "time": data.get("time", {"from": "now-6h", "to": "now"}),
        "templating": data.get("templating", {"list": []}),
        "panels": panels,
    }

    if isinstance(dashboard["time"], list):
        if len(dashboard["time"]) >= 2:
            dashboard["time"] = {"from": str(dashboard["time"][0]), "to": str(dashboard["time"][1])}
        else:
            dashboard["time"] = {"from": "now-6h", "to": "now"}

    return {"dashboard": dashboard, "folderId": 0, "overwrite": True}


def import_dashboards(
    gf: GrafanaClient,
    cls_dashboards: List[dict],
    keep_names: List[str],
    ds_ref: dict,
    cls_region: str,
    export_dir: str,
    cleanup_same_name: bool,
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    keep_set = set(keep_names)
    selected = [d for d in cls_dashboards if d.get("DashboardName") in keep_set]
    if not selected:
        raise RuntimeError("No target dashboards matched. Check migration.keepDashboards names.")

    if cleanup_same_name:
        current = gf.search_dashboards(limit=2000)
        title_to_uid = {x.get("title"): x.get("uid") for x in current if x.get("title") and x.get("uid")}
        for name in keep_set:
            if name in title_to_uid:
                gf.api("DELETE", f"/api/dashboards/uid/{title_to_uid[name]}")

    ok = []
    fail = []

    os.makedirs(export_dir, exist_ok=True)

    for src in selected:
        payload = convert_dashboard(src, ds_ref, cls_region)
        title = payload["dashboard"]["title"]

        safe = "".join(c if c.isalnum() or c in ["-", "_", " "] else "_" for c in title).strip()
        save_json(os.path.join(export_dir, f"{safe}.grafana.json"), payload)

        ret = gf.api("POST", "/api/dashboards/db", payload)
        uid = ret.get("uid")
        if uid:
            ok.append((title, uid))
        else:
            fail.append((title, str(ret)[:300]))

    return ok, fail


def smoke_query(gf: GrafanaClient, ds_ref: dict, dashboards: List[Tuple[str, str]]) -> List[Tuple[str, int]]:
    out = []
    for title, uid in dashboards:
        detail = gf.api("GET", f"/api/dashboards/uid/{uid}")
        db = detail.get("dashboard", {})
        query_target = None

        for p in db.get("panels", []):
            for t in p.get("targets", []):
                lsp = t.get("logServiceParams") or {}
                if lsp.get("TopicId") and lsp.get("Query"):
                    query_target = t
                    break
            if query_target:
                break

        if not query_target:
            out.append((title, -1))
            continue

        payload = {
            "queries": [
                {
                    "refId": "A",
                    "datasource": ds_ref,
                    "serviceType": "logService",
                    "logServiceParams": query_target.get("logServiceParams"),
                    "intervalMs": 60000,
                    "maxDataPoints": 1000,
                }
            ],
            "from": "now-6h",
            "to": "now",
        }

        res = gf.api("POST", "/api/ds/query", payload)
        frames = (res.get("results", {}).get("A", {}) or {}).get("frames", [])
        out.append((title, len(frames)))

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="CLS -> Grafana migration tool")
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    args = parser.parse_args()

    cfg = load_json(args.config)

    required = [
        ("cls", ["secretId", "secretKey", "region", "endpoint"]),
        ("grafana", ["url", "user", "password", "datasource"]),
        ("migration", ["keepDashboards", "exportDir"]),
    ]
    for section, keys in required:
        if section not in cfg:
            raise RuntimeError(f"Missing config section: {section}")
        for k in keys:
            if k not in cfg[section]:
                raise RuntimeError(f"Missing config key: {section}.{k}")

    signer = Tc3Signer(
        cfg["cls"]["secretId"],
        cfg["cls"]["secretKey"],
        cfg["cls"]["region"],
        cfg["cls"]["endpoint"],
    )
    cls_client = ClsClient(signer)

    gf = GrafanaClient(cfg["grafana"]["url"], cfg["grafana"]["user"], cfg["grafana"]["password"])

    print("[1/5] Ensuring Grafana CLS datasource exists and is correctly configured...")
    ds = ensure_cls_datasource(gf, cfg)
    ds_ref = {"type": ds["type"], "uid": ds["uid"]}
    print(f"  Datasource uid: {ds['uid']}")

    print("[2/5] Pulling dashboards from CLS...")
    dashboards = cls_client.list_dashboards()
    print(f"  Total dashboards: {len(dashboards)}")

    print("[3/5] Converting and importing target dashboards...")
    ok, fail = import_dashboards(
        gf=gf,
        cls_dashboards=dashboards,
        keep_names=cfg["migration"]["keepDashboards"],
        ds_ref=ds_ref,
        cls_region=cfg["cls"]["region"],
        export_dir=cfg["migration"]["exportDir"],
        cleanup_same_name=bool(cfg["migration"].get("cleanupSameName", True)),
    )
    print(f"  Imported successfully: {len(ok)}")
    print(f"  Import failed: {len(fail)}")

    print("[4/5] Running ds/query smoke checks...")
    smoke = smoke_query(gf, ds_ref, ok)
    for title, frames in smoke:
        mark = "OK" if frames > 0 else ("NO_TARGET" if frames == -1 else "EMPTY")
        print(f"  {title}: frames={frames} [{mark}]")

    print("[5/5] Dashboard URLs:")
    for title, uid in ok:
        print(f"  {title}: {cfg['grafana']['url'].rstrip('/')}/d/{uid}")

    if fail:
        print("\nFailure details:")
        for title, msg in fail:
            print(f"  - {title}: {msg}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[FATAL] {e}")
        raise
