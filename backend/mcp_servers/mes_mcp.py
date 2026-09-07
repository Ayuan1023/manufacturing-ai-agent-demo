"""
MES 工单 MCP Server
提供工单查询、生产统计、质量分析、物料齐套、工单草稿创建等工具
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from fastmcp import FastMCP

DATA_DIR = Path(__file__).parent.parent / "data"

mcp = FastMCP("mes-workorder")


def _load_json(filename: str) -> dict | list:
    """加载 JSON 数据文件，文件不存在时返回结构化错误"""
    try:
        with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": f"数据文件 {filename} 不存在，请先运行数据生成器"}


@mcp.tool()
def get_work_orders(status: Optional[str] = None, line: Optional[str] = None, limit: int = 20) -> dict:
    """
    查询 MES 工单列表，可按状态和产线筛选。
    当用户问"工单列表"、"有哪些工单"、"进行中的工单"、"某条线的工单"时使用。

    参数:
        status: 工单状态筛选，可选值：待排产、已排产、进行中、已完成、异常暂停。不填则返回全部
        line: 产线筛选，可选值：1号线、2号线、3号线、4号线。不填则返回全部
        limit: 返回条数，默认20
    """
    orders = _load_json("mes_work_orders.json")
    if isinstance(orders, dict) and "error" in orders:
        return orders

    if status:
        orders = [o for o in orders if o["status"] == status]
    if line:
        orders = [o for o in orders if o["line"] == line]

    orders = sorted(orders, key=lambda x: x["planned_start"], reverse=True)[:limit]

    simplified = []
    for o in orders:
        simplified.append({
            "wo_id": o["wo_id"],
            "product_name": o["product_name"],
            "quantity": o["quantity"],
            "completed": o["completed_quantity"],
            "status": o["status"],
            "yield_rate": o["yield_rate"],
            "line": o["line"],
            "priority": o["priority"],
            "operator": o["operator"],
        })

    return {"total": len(simplified), "orders": simplified}


@mcp.tool()
def get_work_order_detail(wo_id: str) -> dict:
    """
    获取指定工单的详细信息，包括产品、数量、进度、良率、时间、工艺路线等。
    当用户问"工单详情"、"WO-XXXX 怎么样了"、"工单进度"时使用。

    参数:
        wo_id: 工单号，如 WO-2026-0001
    """
    orders = _load_json("mes_work_orders.json")
    if isinstance(orders, dict) and "error" in orders:
        return orders
    order = next((o for o in orders if o["wo_id"] == wo_id), None)
    if not order:
        return {"error": f"工单 {wo_id} 不存在"}

    progress = round(order["completed_quantity"] / order["quantity"] * 100, 1) if order["quantity"] > 0 else 0
    return {**order, "progress_pct": progress}


@mcp.tool()
def get_production_stats(days: int = 7) -> dict:
    """
    获取生产统计数据，包括工单完成率、产量、良率、各线体对比。
    当用户问"生产情况"、"本周产量"、"完成率"、"生产统计"时使用。

    参数:
        days: 统计最近多少天的工单（按planned_start过滤），默认7天
    """
    orders = _load_json("mes_work_orders.json")
    if isinstance(orders, dict) and "error" in orders:
        return orders

    # 按时间过滤最近 N 天的工单
    cutoff = (datetime(2026, 9, 7) - timedelta(days=days)).isoformat()
    recent_orders = [o for o in orders if o["planned_start"] >= cutoff]
    # 如果过滤后太少，回退到全部工单并说明
    if len(recent_orders) < 5:
        recent_orders = orders
        filter_note = f"最近{days}天工单不足，已统计全部工单"
    else:
        filter_note = f"已统计最近{days}天工单"

    status_count = {}
    for o in recent_orders:
        status_count[o["status"]] = status_count.get(o["status"], 0) + 1

    completed = [o for o in recent_orders if o["status"] == "已完成"]
    total_planned = sum(o["quantity"] for o in recent_orders)
    total_completed = sum(o["completed_quantity"] for o in recent_orders)
    avg_yield = round(sum(o["yield_rate"] for o in completed if o["yield_rate"]) / len(completed), 1) if completed else 0

    line_stats = {}
    for o in recent_orders:
        line = o["line"]
        if line not in line_stats:
            line_stats[line] = {"total": 0, "completed": 0, "yield_rates": []}
        line_stats[line]["total"] += o["quantity"]
        line_stats[line]["completed"] += o["completed_quantity"]
        if o["yield_rate"]:
            line_stats[line]["yield_rates"].append(o["yield_rate"])

    for line in line_stats:
        ls = line_stats[line]
        ls["completion_rate"] = round(ls["completed"] / ls["total"] * 100, 1) if ls["total"] > 0 else 0
        ls["avg_yield"] = round(sum(ls["yield_rates"]) / len(ls["yield_rates"]), 1) if ls["yield_rates"] else 0
        del ls["yield_rates"]

    abnormal = [o for o in recent_orders if o["status"] == "异常暂停"]

    return {
        "period_days": days,
        "filter_note": filter_note,
        "total_orders": len(recent_orders),
        "status_distribution": status_count,
        "completion_rate": round(total_completed / total_planned * 100, 1) if total_planned > 0 else 0,
        "total_planned_qty": total_planned,
        "total_completed_qty": total_completed,
        "avg_yield_rate": avg_yield,
        "line_stats": line_stats,
        "abnormal_orders": [{"wo_id": o["wo_id"], "product": o["product_name"], "remark": o["remark"]} for o in abnormal],
    }


@mcp.tool()
def get_quality_analysis() -> dict:
    """
    获取质量分析数据，包括良率分布、低良率工单、不良趋势。
    当用户问"质量情况"、"良率分析"、"不良品"、"质量问题"时使用。
    """
    orders = _load_json("mes_work_orders.json")
    if isinstance(orders, dict) and "error" in orders:
        return orders

    with_yield = [o for o in orders if o["yield_rate"] is not None]
    excellent = [o for o in with_yield if o["yield_rate"] >= 98]
    good = [o for o in with_yield if 95 <= o["yield_rate"] < 98]
    poor = [o for o in with_yield if o["yield_rate"] < 95]
    low_yield = sorted(poor, key=lambda x: x["yield_rate"])[:5]

    line_yield = {}
    for o in with_yield:
        line = o["line"]
        if line not in line_yield:
            line_yield[line] = []
        line_yield[line].append(o["yield_rate"])
    line_avg = {line: round(sum(y) / len(y), 1) for line, y in line_yield.items()}

    overall_avg = round(sum(o["yield_rate"] for o in with_yield) / len(with_yield), 1) if with_yield else 0

    return {
        "total_with_yield": len(with_yield),
        "yield_distribution": {
            "excellent(>=98%)": len(excellent),
            "good(95-98%)": len(good),
            "poor(<95%)": len(poor),
        },
        "overall_avg_yield": overall_avg,
        "line_avg_yield": line_avg,
        "low_yield_orders": [
            {"wo_id": o["wo_id"], "product": o["product_name"], "yield_rate": o["yield_rate"], "line": o["line"]}
            for o in low_yield
        ],
        "quality_target": 98.0,
        "target_met": overall_avg >= 98,
    }


@mcp.tool()
def check_material_availability(wo_id: Optional[str] = None, product_code: Optional[str] = None, quantity: Optional[int] = None) -> dict:
    """
    检查物料齐套情况，可按工单或产品+数量检查。
    当用户问"物料齐套吗"、"缺什么料"、"能不能投产"、"库存够不够"时使用。

    参数:
        wo_id: 工单号，如 WO-2026-0001。提供后自动获取产品和数量
        product_code: 产品编码，如 P-A100。wo_id 不填时需提供
        quantity: 生产数量。wo_id 不填时需提供
    """
    boms = _load_json("product_bom.json")
    inventory = _load_json("inventory.json")
    if isinstance(boms, dict) and "error" in boms:
        return boms
    if isinstance(inventory, dict) and "error" in inventory:
        return inventory

    inv_map = {i["mat_code"]: i for i in inventory}

    if wo_id:
        orders = _load_json("mes_work_orders.json")
        if isinstance(orders, dict) and "error" in orders:
            return orders
        order = next((o for o in orders if o["wo_id"] == wo_id), None)
        if not order:
            return {"error": f"工单 {wo_id} 不存在"}
        product_code = order["product_code"]
        quantity = order["quantity"]
    elif not product_code or not quantity:
        return {"error": "请提供 wo_id 或 product_code + quantity"}

    if product_code not in boms:
        return {"error": f"产品 {product_code} 不存在"}

    bom = boms[product_code]
    results = []
    all_ready = True

    for item in bom["items"]:
        mat_code = item["mat_code"]
        required = item["quantity"] * quantity
        inv = inv_map.get(mat_code)
        if not inv:
            results.append({
                "mat_code": mat_code, "mat_name": item["mat_name"],
                "required": required, "available": 0, "shortage": required,
                "status": "缺料", "in_transit": 0,
            })
            all_ready = False
            continue

        available = inv["stock_qty"] - inv["reserved_qty"] + inv["in_transit_qty"]
        shortage = max(0, required - available)
        status = "齐套" if shortage == 0 else "缺料"
        if shortage > 0:
            all_ready = False

        results.append({
            "mat_code": mat_code, "mat_name": inv["mat_name"],
            "required": required, "stock": inv["stock_qty"],
            "reserved": inv["reserved_qty"], "in_transit": inv["in_transit_qty"],
            "available": available, "shortage": shortage, "status": status,
            "safety_stock": inv["safety_stock"],
        })

    shortage_items = [r for r in results if r["status"] == "缺料"]
    return {
        "wo_id": wo_id, "product_code": product_code,
        "product_name": bom["product_name"], "quantity": quantity,
        "overall_status": "齐套" if all_ready else "缺料",
        "total_items": len(results),
        "ready_items": len(results) - len(shortage_items),
        "shortage_items": shortage_items,
        "details": results,
    }


@mcp.tool()
def get_inventory_summary() -> dict:
    """
    获取库存概览，包括缺料预警、呆滞料、库存总值。
    当用户问"库存情况"、"缺料预警"、"呆滞料"、"库存盘点"时使用。
    """
    inventory = _load_json("inventory.json")
    if isinstance(inventory, dict) and "error" in inventory:
        return inventory

    short = [i for i in inventory if i["stock_qty"] < i["safety_stock"]]
    dormant = [i for i in inventory if i["stock_qty"] > i["safety_stock"] * 5]
    in_transit = [i for i in inventory if i["in_transit_qty"] > 0]

    type_stats = {}
    for i in inventory:
        t = i["type"]
        if t not in type_stats:
            type_stats[t] = {"count": 0, "total_stock": 0}
        type_stats[t]["count"] += 1
        type_stats[t]["total_stock"] += i["stock_qty"]

    return {
        "total_materials": len(inventory),
        "shortage_count": len(short),
        "dormant_count": len(dormant),
        "in_transit_count": len(in_transit),
        "type_stats": type_stats,
        "shortage_alerts": [
            {"mat_code": i["mat_code"], "mat_name": i["mat_name"],
             "stock": i["stock_qty"], "safety_stock": i["safety_stock"]}
            for i in short[:10]
        ],
        "dormant_alerts": [
            {"mat_code": i["mat_code"], "mat_name": i["mat_name"],
             "stock": i["stock_qty"], "safety_stock": i["safety_stock"],
             "ratio": round(i["stock_qty"] / i["safety_stock"], 1)}
            for i in dormant
        ],
    }


@mcp.tool()
def create_work_order_draft(product_code: str, quantity: int, line: str, priority: str = "中") -> dict:
    """
    创建生产工单草稿（仅生成草稿，不写入系统，需人工确认后提交）。
    当用户要求"创建工单"、"下生产单"、"安排生产"时使用。
    这是写操作，生成草稿后需要用户确认。

    参数:
        product_code: 产品编码，如 P-A100、P-B200、P-C300、P-D400、P-E500
        quantity: 生产数量
        line: 产线，可选值：1号线、2号线、3号线、4号线
        priority: 优先级，可选值：高、中、低，默认中
    """
    boms = _load_json("product_bom.json")
    orders = _load_json("mes_work_orders.json")
    if isinstance(boms, dict) and "error" in boms:
        return boms
    if isinstance(orders, dict) and "error" in orders:
        return orders

    if product_code not in boms:
        return {"error": f"产品 {product_code} 不存在，可选：{list(boms.keys())}"}
    if quantity <= 0:
        return {"error": "数量必须大于0"}
    if line not in ["1号线", "2号线", "3号线", "4号线"]:
        return {"error": f"产线 {line} 无效，可选：1号线、2号线、3号线、4号线"}

    bom = boms[product_code]

    # 从已有工单中查找同产品的工艺路线
    same_product = next((o for o in orders if o["product_code"] == product_code), None)
    process_route = same_product["process_route"] if same_product else "按工艺路线执行"

    new_id = f"WO-2026-{len(orders) + 1:04d}"
    draft = {
        "wo_id": new_id,
        "product_code": product_code,
        "product_name": bom["product_name"],
        "quantity": quantity,
        "line": line,
        "priority": priority,
        "status": "草稿（待确认）",
        "process_route": process_route,
        "created_at": datetime.now().isoformat(),
        "note": "此为AI生成的工单草稿，需人工确认后提交至MES系统",
    }

    return {
        "status": "草稿已生成",
        "action_required": "请确认工单信息，确认后可提交至MES系统",
        "draft": draft,
    }


if __name__ == "__main__":
    mcp.run()
