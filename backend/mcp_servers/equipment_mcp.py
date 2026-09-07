"""
设备数据 MCP Server
提供设备状态查询、历史数据、异常诊断等工具
"""
import json
from pathlib import Path
from typing import Optional
try:
    from .mcp_compat import FastMCP
except ImportError:
    from mcp_compat import FastMCP

DATA_DIR = Path(__file__).parent.parent / "data"

mcp = FastMCP("equipment-monitor")


def _load_json(filename: str) -> dict | list:
    """加载 JSON 数据文件，文件不存在时返回结构化错误"""
    try:
        with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": f"数据文件 {filename} 不存在，请先运行数据生成器"}


@mcp.tool()
def get_equipment_list() -> dict:
    """
    获取所有设备列表，包含设备ID、名称、类型、产线和当前状态。
    当用户问"有哪些设备"、"设备列表"、"产线设备"时使用此工具。
    """
    status = _load_json("equipment_status.json")
    if isinstance(status, dict) and "error" in status:
        return status
    result = []
    for eq_id, eq in status.items():
        result.append({
            "id": eq["id"],
            "name": eq["name"],
            "type": eq["type"],
            "line": eq["line"],
            "status": eq["status"],
        })
    return {"total": len(result), "equipment": result}


@mcp.tool()
def get_equipment_status(equipment_id: str) -> dict:
    """
    获取指定设备的当前实时状态，包括所有测点的当前值和告警状态。
    当用户询问某台设备"当前状态"、"实时数据"、"运行情况"时使用。

    参数:
        equipment_id: 设备ID，如 CNC-001、INJ-001、PRS-001、ASM-001
    """
    status = _load_json("equipment_status.json")
    if isinstance(status, dict) and "error" in status:
        return status
    if equipment_id not in status:
        return {"error": f"设备 {equipment_id} 不存在"}

    eq = status[equipment_id]
    alarms = []
    for sdef in eq["sensor_defs"]:
        val = eq["latest"].get(sdef["id"])
        if val and val > sdef["alarm_threshold"]:
            alarms.append({
                "sensor": sdef["name"],
                "value": val,
                "unit": sdef["unit"],
                "threshold": sdef["alarm_threshold"],
            })

    return {
        "id": eq["id"],
        "name": eq["name"],
        "type": eq["type"],
        "line": eq["line"],
        "status": eq["status"],
        "latest_readings": eq["latest"],
        "alarms": alarms,
        "alarm_count": len(alarms),
    }


@mcp.tool()
def get_alarm_equipment() -> dict:
    """
    获取当前处于告警状态的设备列表及告警详情。
    当用户问"哪些设备告警"、"有什么异常"、"设备故障"时使用。
    """
    status = _load_json("equipment_status.json")
    if isinstance(status, dict) and "error" in status:
        return status
    alarms = []
    for eq_id, eq in status.items():
        if eq["status"] == "告警":
            alarm_sensors = []
            for sdef in eq["sensor_defs"]:
                val = eq["latest"].get(sdef["id"])
                if val and val > sdef["alarm_threshold"]:
                    alarm_sensors.append({
                        "sensor": sdef["name"],
                        "value": val,
                        "unit": sdef["unit"],
                        "threshold": sdef["alarm_threshold"],
                        "exceed_pct": round((val - sdef["alarm_threshold"]) / sdef["alarm_threshold"] * 100, 1),
                    })
            alarms.append({
                "id": eq["id"],
                "name": eq["name"],
                "line": eq["line"],
                "alarm_sensors": alarm_sensors,
            })
    return {"alarm_count": len(alarms), "equipment": alarms}


@mcp.tool()
def get_equipment_history(equipment_id: str, sensor_id: str, hours: int = 24) -> dict:
    """
    获取指定设备某测点的历史时序数据，用于趋势分析和预测性维护。
    当用户问"温度趋势"、"历史数据"、"最近24小时变化"、"振动趋势"时使用。

    参数:
        equipment_id: 设备ID，如 CNC-001
        sensor_id: 测点ID，如 spindle_temp、spindle_speed、power、injection_pressure
        hours: 查询最近多少小时的数据，默认24小时，范围1-168小时（7天）
    """
    hours = max(1, min(hours, 168))
    ts_data = _load_json("equipment_timeseries.json")
    status = _load_json("equipment_status.json")

    if isinstance(ts_data, dict) and "error" in ts_data:
        return ts_data
    if equipment_id not in ts_data:
        return {"error": f"设备 {equipment_id} 不存在"}

    eq = ts_data[equipment_id]
    if sensor_id not in eq["sensors"]:
        return {"error": f"测点 {sensor_id} 不存在", "available_sensors": list(eq["sensors"].keys())}

    points = hours * 2  # 每30分钟一个点
    timestamps = eq["timestamps"][-points:]
    values = eq["sensors"][sensor_id][-points:]

    vals = [v for v in values if v is not None]
    stats = {
        "min": round(min(vals), 2),
        "max": round(max(vals), 2),
        "avg": round(sum(vals) / len(vals), 2),
        "latest": round(values[-1], 2),
        "trend": "上升" if values[-1] > values[0] else "下降" if values[-1] < values[0] else "平稳",
    }

    sdef = next((s for s in status[equipment_id]["sensor_defs"] if s["id"] == sensor_id), None)

    return {
        "equipment_id": equipment_id,
        "sensor_id": sensor_id,
        "sensor_name": sdef["name"] if sdef else sensor_id,
        "unit": sdef["unit"] if sdef else "",
        "alarm_threshold": sdef["alarm_threshold"] if sdef else None,
        "hours": hours,
        "data_points": len(timestamps),
        "statistics": stats,
        "timestamps": timestamps,
        "values": values,
    }


@mcp.tool()
def analyze_equipment_anomaly(equipment_id: str) -> dict:
    """
    对指定设备进行异常分析，检查当前值是否超阈值、历史趋势是否劣化。
    当用户问"分析设备异常"、"诊断故障"、"设备有什么问题"时使用。

    参数:
        equipment_id: 设备ID，如 CNC-001
    """
    status = _load_json("equipment_status.json")
    ts_data = _load_json("equipment_timeseries.json")

    if isinstance(status, dict) and "error" in status:
        return status
    if equipment_id not in status:
        return {"error": f"设备 {equipment_id} 不存在"}

    eq = status[equipment_id]
    findings = []
    severity = "正常"

    for sdef in eq["sensor_defs"]:
        sid = sdef["id"]
        current = eq["latest"].get(sid)
        if current is None:
            continue

        if current > sdef["alarm_threshold"]:
            findings.append({
                "severity": "高",
                "sensor": sdef["name"],
                "issue": f"当前值 {current}{sdef['unit']} 超过告警阈值 {sdef['alarm_threshold']}{sdef['unit']}",
                "suggestion": f"立即检查{sdef['name']}相关系统，参考故障代码表处理",
            })
            severity = "高"
        elif current > sdef["normal_max"]:
            findings.append({
                "severity": "中",
                "sensor": sdef["name"],
                "issue": f"当前值 {current}{sdef['unit']} 超出正常范围({sdef['normal_min']}-{sdef['normal_max']}{sdef['unit']})",
                "suggestion": f"关注{sdef['name']}变化趋势，必要时安排检查",
            })
            if severity == "正常":
                severity = "中"

        # 检查历史趋势（最近24小时是否持续上升）
        if isinstance(ts_data, dict) and equipment_id in ts_data and sid in ts_data[equipment_id]["sensors"]:
            recent = ts_data[equipment_id]["sensors"][sid][-48:]
            if len(recent) >= 12:
                first_half_avg = sum(recent[:12]) / 12
                second_half_avg = sum(recent[-12:]) / 12
                if second_half_avg > first_half_avg * 1.1 and current > sdef["normal_max"] * 0.8:
                    findings.append({
                        "severity": "中",
                        "sensor": sdef["name"],
                        "issue": f"最近24小时{sdef['name']}呈上升趋势（{round(first_half_avg,2)}→{round(second_half_avg,2)}{sdef['unit']}）",
                        "suggestion": "可能存在劣化趋势，建议安排预防性维护",
                    })
                    if severity == "正常":
                        severity = "中"

    return {
        "equipment_id": equipment_id,
        "equipment_name": eq["name"],
        "overall_severity": severity,
        "status": eq["status"],
        "findings": findings,
        "finding_count": len(findings),
        "recommendation": "建议立即停机检查并联系设备主管" if severity == "高"
        else "建议关注并安排近期检查" if severity == "中"
        else "设备运行正常，继续监控",
    }


@mcp.tool()
def get_maintenance_history(equipment_id: Optional[str] = None, limit: int = 10) -> dict:
    """
    获取设备维护工单历史，可按设备筛选。
    当用户问"维护记录"、"维修历史"、"之前修过什么"时使用。

    参数:
        equipment_id: 设备ID，可选，不填则返回全部
        limit: 返回条数，默认10条
    """
    orders = _load_json("maintenance_orders.json")
    if isinstance(orders, dict) and "error" in orders:
        return orders
    if equipment_id:
        orders = [o for o in orders if o["equipment_id"] == equipment_id]
    orders = sorted(orders, key=lambda x: x["reported_at"], reverse=True)[:limit]

    total_downtime = sum(o["downtime_hours"] for o in orders)
    total_cost = sum(o["cost"] for o in orders)

    return {
        "total_orders": len(orders),
        "total_downtime_hours": round(total_downtime, 1),
        "total_cost": total_cost,
        "orders": orders,
    }


if __name__ == "__main__":
    mcp.run()
