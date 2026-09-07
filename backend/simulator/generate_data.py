"""
制造业 AI Agent Demo - 模拟数据生成器
生成：设备时序数据、MES工单、SOP文档、物料BOM/库存、维护工单历史
"""
import json
import random
import math
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)  # 固定种子，保证可复现

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ============================================================
# 1. 设备时序数据
# ============================================================

EQUIPMENT = [
    {"id": "CNC-001", "name": "CNC加工中心-01", "type": "CNC", "line": "1号线"},
    {"id": "CNC-002", "name": "CNC加工中心-02", "type": "CNC", "line": "1号线"},
    {"id": "INJ-001", "name": "注塑机-01", "type": "INJECTION", "line": "2号线"},
    {"id": "INJ-002", "name": "注塑机-02", "type": "INJECTION", "line": "2号线"},
    {"id": "PRS-001", "name": "冲压机-01", "type": "PRESS", "line": "3号线"},
    {"id": "PRS-002", "name": "冲压机-02", "type": "PRESS", "line": "3号线"},
    {"id": "ASM-001", "name": "装配线-01", "type": "ASSEMBLY", "line": "4号线"},
    {"id": "ASM-002", "name": "装配线-02", "type": "ASSEMBLY", "line": "4号线"},
]

# 每类设备的测点定义（测点ID, 名称, 单位, 正常值范围, 告警阈值）
SENSOR_DEFS = {
    "CNC": [
        ("spindle_temp", "主轴温度", "°C", 25, 45, 65),
        ("spindle_speed", "主轴转速", "rpm", 800, 3000, 5000),
        ("spindle_vibration", "主轴振动", "mm/s", 0.5, 2.0, 4.5),
        ("coolant_temp", "冷却液温度", "°C", 18, 28, 35),
        ("cutting_force", "切削力", "N", 100, 500, 800),
        ("power", "功率", "kW", 2.0, 8.0, 15.0),
        ("feed_rate", "进给速度", "mm/min", 100, 800, 1500),
        ("tool_wear", "刀具磨损", "mm", 0.01, 0.15, 0.30),
    ],
    "INJECTION": [
        ("melt_temp", "熔胶温度", "°C", 180, 230, 280),
        ("mold_temp", "模具温度", "°C", 40, 70, 100),
        ("injection_pressure", "注射压力", "MPa", 50, 120, 180),
        ("holding_pressure", "保压压力", "MPa", 30, 80, 120),
        ("cycle_time", "周期时间", "s", 20, 45, 70),
        ("screw_speed", "螺杆转速", "rpm", 50, 150, 250),
        ("clamp_force", "锁模力", "kN", 500, 1200, 2000),
        ("power", "功率", "kW", 5.0, 15.0, 25.0),
    ],
    "PRESS": [
        ("stroke", "行程", "mm", 50, 150, 250),
        ("press_force", "冲压力", "kN", 200, 800, 1500),
        ("cycle_rate", "冲压频率", "次/min", 20, 60, 120),
        ("motor_temp", "电机温度", "°C", 30, 55, 85),
        ("vibration", "振动", "mm/s", 1.0, 3.0, 6.0),
        ("air_pressure", "气压", "MPa", 0.4, 0.6, 0.8),
        ("oil_temp", "油温", "°C", 25, 45, 70),
        ("power", "功率", "kW", 3.0, 10.0, 18.0),
    ],
    "ASSEMBLY": [
        ("conveyor_speed", "传送带速度", "m/min", 1.0, 3.0, 5.0),
        ("torque", "扭矩", "N·m", 5, 20, 35),
        ("air_pressure", "气压", "MPa", 0.4, 0.6, 0.8),
        ("cycle_time", "节拍时间", "s", 15, 35, 60),
        ("temperature", "环境温度", "°C", 20, 26, 32),
        ("humidity", "环境湿度", "%", 40, 55, 70),
        ("power", "功率", "kW", 1.0, 4.0, 8.0),
        ("error_rate", "错误率", "%", 0.1, 1.0, 3.0),
    ],
}


def generate_equipment_timeseries():
    """生成7天设备时序数据，每30分钟一个采样点"""
    end_time = datetime(2026, 9, 7, 0, 0, 0)
    start_time = end_time - timedelta(days=7)
    interval = timedelta(minutes=30)
    num_points = int((end_time - start_time) / interval)

    all_data = {}
    equipment_status = {}

    for eq in EQUIPMENT:
        eq_id = eq["id"]
        eq_type = eq["type"]
        sensors = SENSOR_DEFS[eq_type]
        timestamps = []
        sensor_data = {s[0]: [] for s in sensors}

        # 决定是否注入异常（CNC-001 温度异常持续到当前，INJ-001 历史异常已恢复）
        has_anomaly = eq_id in ["CNC-001", "INJ-001"]
        if eq_id == "CNC-001":
            anomaly_start = start_time + timedelta(days=5, hours=8)
            anomaly_end = end_time  # 持续到当前，确保有实时告警
        elif eq_id == "INJ-001":
            anomaly_start = start_time + timedelta(days=3, hours=8)
            anomaly_end = anomaly_start + timedelta(hours=6)  # 历史异常，已恢复
        else:
            anomaly_start = None
            anomaly_end = None

        current_time = start_time
        for i in range(num_points):
            timestamps.append(current_time.isoformat())

            for sid, sname, unit, vmin, vnormal, vmax in sensors:
                # 基础值 = 正常值 + 噪声
                base = vnormal + random.gauss(0, (vmax - vmin) * 0.05)

                # 日间波动（白天生产，夜间低负荷）
                hour = current_time.hour
                if 8 <= hour < 20:  # 生产时段
                    base *= 1.0 + random.uniform(-0.05, 0.08)
                else:  # 夜间待机
                    base *= 0.6 + random.uniform(-0.02, 0.05)

                # 注入异常
                if has_anomaly and anomaly_start <= current_time <= anomaly_end:
                    if eq_id == "CNC-001" and sid == "spindle_temp":
                        base = vmax * 1.08 + random.gauss(0, 2)  # 温度超过告警阈值
                    elif eq_id == "CNC-001" and sid == "spindle_vibration":
                        base = vmax * 1.05 + random.gauss(0, 0.3)
                    elif eq_id == "INJ-001" and sid == "injection_pressure":
                        base = vmax * 1.05 + random.gauss(0, 5)

                # 限制范围
                base = max(vmin * 0.5, min(vmax * 1.2, base))
                sensor_data[sid].append(round(base, 2))

            current_time += interval

        # 计算当前状态
        latest = {s[0]: sensor_data[s[0]][-1] for s in sensors}
        is_alarm = any(
            latest[s[0]] > s[5] for s in sensors
        )
        status = "告警" if is_alarm else ("运行" if latest.get("power", 0) > 1 else "待机")

        equipment_status[eq_id] = {
            "id": eq_id,
            "name": eq["name"],
            "type": eq_type,
            "line": eq["line"],
            "status": status,
            "latest": latest,
            "sensor_defs": [
                {"id": s[0], "name": s[1], "unit": s[2],
                 "normal_min": s[3], "normal_max": s[4], "alarm_threshold": s[5]}
                for s in sensors
            ],
        }

        all_data[eq_id] = {
            "timestamps": timestamps,
            "sensors": sensor_data,
        }

    # 保存时序数据（分开保存，避免单文件过大）
    with open(DATA_DIR / "equipment_timeseries.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False)

    with open(DATA_DIR / "equipment_status.json", "w", encoding="utf-8") as f:
        json.dump(equipment_status, f, ensure_ascii=False, indent=2)

    print(f"✅ 设备时序数据：{len(EQUIPMENT)} 台设备，{num_points} 个时间点/台")
    print(f"✅ 设备状态：{sum(1 for s in equipment_status.values() if s['status']=='运行')} 运行 / "
          f"{sum(1 for s in equipment_status.values() if s['status']=='告警')} 告警 / "
          f"{sum(1 for s in equipment_status.values() if s['status']=='待机')} 待机")


# ============================================================
# 2. MES 工单数据
# ============================================================

PRODUCTS = [
    {"code": "P-A100", "name": "铝合金外壳-A型", "process": "CNC加工→表面处理→检验"},
    {"code": "P-B200", "name": "塑料面板-B型", "process": "注塑→修剪→检验→包装"},
    {"code": "P-C300", "name": "金属支架-C型", "process": "冲压→焊接→检验"},
    {"code": "P-D400", "name": "电子组件-D型", "process": "SMT→装配→测试→包装"},
    {"code": "P-E500", "name": "精密齿轮-E型", "process": "车削→磨削→检验"},
]

WORK_ORDER_STATUS = ["待排产", "已排产", "进行中", "已完成", "异常暂停"]


def generate_work_orders():
    orders = []
    base_time = datetime(2026, 9, 1, 8, 0, 0)

    for i in range(1, 36):
        product = random.choice(PRODUCTS)
        status = random.choices(
            WORK_ORDER_STATUS,
            weights=[10, 15, 30, 35, 10]
        )[0]

        quantity = random.choice([100, 200, 500, 1000, 2000])
        start_time = base_time + timedelta(days=random.randint(0, 5), hours=random.randint(0, 8))

        if status == "已完成":
            end_time = start_time + timedelta(hours=random.randint(4, 24))
            completed_qty = quantity
            yield_rate = round(random.uniform(92.0, 99.5), 1)
        elif status == "进行中":
            end_time = None
            completed_qty = int(quantity * random.uniform(0.2, 0.8))
            yield_rate = round(random.uniform(90.0, 98.0), 1)
        elif status == "异常暂停":
            end_time = None
            completed_qty = int(quantity * random.uniform(0.1, 0.5))
            yield_rate = round(random.uniform(85.0, 95.0), 1)
        else:
            end_time = None
            completed_qty = 0
            yield_rate = None

        order = {
            "wo_id": f"WO-2026-{i:04d}",
            "product_code": product["code"],
            "product_name": product["name"],
            "process_route": product["process"],
            "quantity": quantity,
            "completed_quantity": completed_qty,
            "status": status,
            "yield_rate": yield_rate,
            "planned_start": start_time.isoformat(),
            "actual_start": start_time.isoformat() if status in ["进行中", "已完成", "异常暂停"] else None,
            "actual_end": end_time.isoformat() if end_time else None,
            "line": random.choice(["1号线", "2号线", "3号线", "4号线"]),
            "priority": random.choice(["高", "中", "低"]),
            "operator": random.choice(["张伟", "李娜", "王强", "刘洋", "陈静"]),
            "remark": "设备故障待维修" if status == "异常暂停" else "",
        }
        orders.append(order)

    with open(DATA_DIR / "mes_work_orders.json", "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    status_count = {}
    for o in orders:
        status_count[o["status"]] = status_count.get(o["status"], 0) + 1
    print(f"✅ MES工单：{len(orders)} 条，状态分布：{status_count}")


# ============================================================
# 3. SOP 文档 + 故障代码表
# ============================================================

FAULT_CODES = [
    {"code": "E001", "equipment": "CNC", "name": "主轴过热", "severity": "高",
     "cause": "主轴冷却系统故障或长时间高负荷运行",
     "action": "1.立即停机 2.检查冷却液液位和泵 3.清理主轴散热片 4.待温度降至40°C以下再启动"},
    {"code": "E002", "equipment": "CNC", "name": "刀具磨损超限", "severity": "中",
     "cause": "刀具使用时间超过设定寿命或切削参数不当",
     "action": "1.暂停加工 2.更换刀具 3.重新对刀 4.首件检验合格后继续"},
    {"code": "E003", "equipment": "CNC", "name": "切削力异常", "severity": "中",
     "cause": "工件装夹不牢或刀具崩刃",
     "action": "1.停机检查 2.确认工件装夹 3.检查刀具状态 4.降低进给速度试切"},
    {"code": "E004", "equipment": "INJECTION", "name": "注射压力过高", "severity": "高",
     "cause": "浇口堵塞或熔胶温度过低",
     "action": "1.降低注射压力 2.提高熔胶温度5-10°C 3.清理浇口 4.检查模具流道"},
    {"code": "E005", "equipment": "INJECTION", "name": "熔胶温度异常", "severity": "中",
     "cause": "加热圈损坏或温控表故障",
     "action": "1.检查各段加热圈 2.校准温控表 3.更换损坏加热圈"},
    {"code": "E006", "equipment": "INJECTION", "name": "产品飞边", "severity": "低",
     "cause": "锁模力不足或注射压力过高",
     "action": "1.增加锁模力 2.降低注射压力 3.检查模具分型面"},
    {"code": "E007", "equipment": "PRESS", "name": "冲压力不足", "severity": "中",
     "cause": "液压油不足或泵磨损",
     "action": "1.检查液压油位 2.检查油泵压力 3.更换液压油 4.检修油泵"},
    {"code": "E008", "equipment": "PRESS", "name": "电机过热", "severity": "高",
     "cause": "连续高负荷运行或散热风扇故障",
     "action": "1.停机降温 2.检查散热风扇 3.清理电机散热片 4.检查轴承润滑"},
    {"code": "E009", "equipment": "PRESS", "name": "气压不足", "severity": "低",
     "cause": "空压机故障或气管漏气",
     "action": "1.检查空压机运行状态 2.排查气管接头 3.更换密封件"},
    {"code": "E010", "equipment": "ASSEMBLY", "name": "扭矩异常", "severity": "中",
     "cause": "螺丝滑牙或电动扭矩工具校准偏差",
     "action": "1.停止该工位 2.校准扭矩工具 3.检查螺丝规格 4.追溯已生产产品"},
    {"code": "E011", "equipment": "ASSEMBLY", "name": "传送带卡滞", "severity": "低",
     "cause": "异物卡入或皮带偏移",
     "action": "1.停机清理 2.调整皮带张紧度 3.检查导轨润滑"},
    {"code": "E012", "equipment": "ALL", "name": "紧急停止", "severity": "高",
     "cause": "操作人员按下急停按钮或安全光幕触发",
     "action": "1.确认现场安全 2.排查急停原因 3.复位急停按钮 4.手动模式试运行"},
    {"code": "E013", "equipment": "CNC", "name": "振动超标", "severity": "中",
     "cause": "主轴轴承磨损或工件不平衡",
     "action": "1.降低转速 2.检查主轴轴承 3.重新平衡工件 4.必要时更换轴承"},
    {"code": "E014", "equipment": "INJECTION", "name": "周期时间过长", "severity": "低",
     "cause": "冷却时间设置过长或模具温度异常",
     "action": "1.优化冷却时间 2.检查模温机 3.调整工艺参数"},
    {"code": "E015", "equipment": "ALL", "name": "通信中断", "severity": "中",
     "cause": "网络故障或PLC通信模块异常",
     "action": "1.检查网络连接 2.重启通信模块 3.检查PLC状态"},
]

SOP_DOCS = [
    {
        "id": "SOP-001",
        "title": "CNC加工中心安全操作规程",
        "category": "安全规范",
        "equipment": "CNC",
        "content": """# CNC加工中心安全操作规程

## 1. 开机前检查
- 检查机床周围无障碍物
- 确认润滑油、冷却液液位正常
- 检查急停按钮是否复位
- 确认门联锁装置有效

## 2. 操作步骤
1. 打开总电源，等待系统启动
2. 回参考点（各轴归零）
3. 装夹工件，确认夹紧可靠
4. 安装刀具，确认刀具号与程序一致
5. 选择加工程序，空运行验证
6. 切换至自动模式，启动加工

## 3. 运行中注意事项
- 严禁打开防护门
- 密切关注切削声音和温度
- 出现异常立即按急停
- 清理切屑必须使用专用工具

## 4. 关机流程
1. 停止加工程序
2. 各轴移至安全位置
3. 关闭主轴和冷却液
4. 切断总电源
5. 清理机床周围环境

## 5. 应急处理
- 发生火灾：立即断电，使用干粉灭火器
- 人员受伤：立即停机，呼叫急救
- 刀具断裂：按急停，更换刀具后检查工件
"""
    },
    {
        "id": "SOP-002",
        "title": "注塑机日常点检标准",
        "category": "设备维护",
        "equipment": "INJECTION",
        "content": """# 注塑机日常点检标准

## 点检频率：每日开班前

## 点检项目

### 安全系统
- [ ] 安全门联锁有效
- [ ] 急停按钮功能正常
- [ ] 光电保护装置正常

### 润滑系统
- [ ] 润滑油位在刻度线之间
- [ ] 润滑泵工作正常
- [ ] 各润滑点无泄漏

### 温度系统
- [ ] 料筒各段温度达到设定值
- [ ] 模温机运行正常
- [ ] 冷却水温在20-25°C

### 液压系统
- [ ] 液压油位正常
- [ ] 系统压力稳定
- [ ] 无异常噪音和泄漏

### 电气系统
- [ ] 控制柜温度正常
- [ ] 各指示灯正常
- [ ] 接地线连接可靠

## 点检记录
点检人：________ 日期：________ 班次：________
异常处理：________________________________
"""
    },
    {
        "id": "SOP-003",
        "title": "冲压机换模作业指导书",
        "category": "作业指导",
        "equipment": "PRESS",
        "content": """# 冲压机换模作业指导书

## 适用范围：冲压机模具更换

## 换模前准备
1. 确认生产工单和模具编号
2. 检查模具外观无损伤
3. 准备换模工具（扳手、铜棒、吊环）
4. 确认行车/叉车可用

## 换模步骤
1. 停机，将滑块升至上死点
2. 切断电机电源，挂牌"正在换模"
3. 拆卸旧模具固定螺栓
4. 使用行车平稳吊出旧模具
5. 清理工作台面
6. 吊入新模具，对准定位销
7. 均匀紧固固定螺栓（对角拧紧）
8. 手动盘车，确认无干涉
9. 接通电源，低压试模
10. 首件检验合格后正式生产

## 安全注意事项
- 吊装时严禁人员站在模具下方
- 螺栓必须对角均匀拧紧
- 试模必须使用低压低速
- 换模完成后摘除警示牌

## 换模时间标准：≤45分钟
"""
    },
    {
        "id": "SOP-004",
        "title": "装配线质量检验规范",
        "category": "质量管理",
        "equipment": "ASSEMBLY",
        "content": """# 装配线质量检验规范

## 检验频次
- 首件：每批次第一件全检
- 巡检：每2小时抽检5件
- 末件：每批次最后一件全检

## 检验项目

### 外观检验
- 表面无划痕、变形、色差
- 标识清晰完整
- 无多余物料残留

### 尺寸检验
- 关键尺寸使用卡尺/千分尺测量
- 配合尺寸使用专用检具
- 记录实测值，与图纸公差对比

### 功能检验
- 按动开关/按钮，功能正常
- 连接部位无松动
- 通电测试（如适用）

### 扭矩检验
- 关键螺丝扭矩值符合工艺要求
- 使用扭矩扳手抽检
- 记录扭矩值和螺丝编号

## 不合格处理
1. 立即停止该工位生产
2. 标识不合格品，放入红色不合格区
3. 通知班组长和质量员
4. 分析原因，采取纠正措施
5. 追溯已生产产品，确定影响范围

## 质量目标
- 一次交验合格率 ≥ 98%
- 巡检合格率 ≥ 99%
- 客户投诉率 ≤ 0.1%
"""
    },
    {
        "id": "SOP-005",
        "title": "设备故障代码速查表",
        "category": "故障处理",
        "equipment": "ALL",
        "content": """# 设备故障代码速查表

## CNC 设备
| 代码 | 名称 | 严重度 | 处理要点 |
|------|------|--------|----------|
| E001 | 主轴过热 | 高 | 停机降温，检查冷却系统 |
| E002 | 刀具磨损超限 | 中 | 更换刀具，重新对刀 |
| E003 | 切削力异常 | 中 | 检查装夹和刀具状态 |
| E013 | 振动超标 | 中 | 降速，检查轴承和平衡 |

## 注塑设备
| 代码 | 名称 | 严重度 | 处理要点 |
|------|------|--------|----------|
| E004 | 注射压力过高 | 高 | 降压升温，清理浇口 |
| E005 | 熔胶温度异常 | 中 | 检查加热圈和温控表 |
| E006 | 产品飞边 | 低 | 增锁模力，降注射压 |
| E014 | 周期时间过长 | 低 | 优化冷却，检查模温 |

## 冲压设备
| 代码 | 名称 | 严重度 | 处理要点 |
|------|------|--------|----------|
| E007 | 冲压力不足 | 中 | 检查油位和油泵 |
| E008 | 电机过热 | 高 | 停机降温，检查风扇 |
| E009 | 气压不足 | 低 | 检查空压机和气管 |

## 装配设备
| 代码 | 名称 | 严重度 | 处理要点 |
|------|------|--------|----------|
| E010 | 扭矩异常 | 中 | 校准工具，检查螺丝 |
| E011 | 传送带卡滞 | 低 | 清理异物，调整皮带 |

## 通用
| 代码 | 名称 | 严重度 | 处理要点 |
|------|------|--------|----------|
| E012 | 紧急停止 | 高 | 确认安全，排查原因 |
| E015 | 通信中断 | 中 | 检查网络和通信模块 |

> 详细处理步骤请参考各设备故障维修手册。
> 高严重度故障必须立即停机并通知设备主管。
"""
    },
    {
        "id": "SOP-006",
        "title": "预测性维护操作指南",
        "category": "设备维护",
        "equipment": "ALL",
        "content": """# 预测性维护操作指南

## 目的
通过设备运行数据趋势分析，在故障发生前进行预防性维护，减少非计划停机。

## 监测指标与阈值

### 温度类
- 主轴/电机温度：正常 < 55°C，预警 55-65°C，告警 > 65°C
- 油温：正常 < 50°C，预警 50-60°C，告警 > 60°C
- 趋势判断：连续3天同一时段温度上升 > 5°C，安排检查

### 振动类
- 振动值：正常 < 2.8mm/s，预警 2.8-4.5mm/s，告警 > 4.5mm/s
- 趋势判断：振动值持续上升且伴随温度上升，优先检查轴承

### 压力类
- 液压/气压：偏离设定值 ±10% 持续30分钟以上，检查管路
- 注射压力波动 > 15%，检查止逆环和料筒

## 维护决策流程
1. 系统自动生成预警工单
2. 设备工程师确认预警有效性
3. 评估故障风险等级（高/中/低）
4. 高风险：24小时内安排维护
5. 中风险：纳入下周维护计划
6. 低风险：持续观察，记录趋势

## 维护记录要求
- 记录维护前设备状态数据
- 记录更换的备件型号和数量
- 记录维护后设备运行参数
- 维护完成后48小时内跟踪设备状态

## KPI目标
- 非计划停机时间减少 ≥ 30%
- 维护成本降低 ≥ 15%
- 预警准确率 ≥ 80%
"""
    },
    {
        "id": "SOP-007",
        "title": "物料齐套检查流程",
        "category": "生产管理",
        "equipment": "ALL",
        "content": """# 物料齐套检查流程

## 适用场景
工单排产前、生产过程中物料短缺时

## 检查步骤

### 1. 获取工单BOM
- 根据工单号查询产品BOM
- 确认物料编码、规格、需求量

### 2. 查询库存
- 原材料库存（仓库可用量）
- 在制品库存（线边仓）
- 在途量（已下单未到货）
- 预留量（其他工单已占用）

### 3. 齐套计算
可用量 = 库存 + 在途 - 预留
缺料量 = 需求量 - 可用量

### 4. 缺料处理
- 缺料量 ≤ 0：齐套，可排产
- 缺料量 > 0 且在途可在3天内到货：标记"部分齐套"，与采购确认到货时间
- 缺料量 > 0 且无在途：触发采购申请，工单暂缓排产

### 5. 呆滞料预警
- 物料库存 > 6个月消耗量 → 标记呆滞
- 呆滞料优先在替代工单中使用
- 无法使用的呆滞料提交处理申请

## 齐套率目标
- 工单排产齐套率 ≥ 95%
- 缺料导致的排产延误 ≤ 5%
"""
    },
    {
        "id": "SOP-008",
        "title": "生产周报生成规范",
        "category": "报告规范",
        "equipment": "ALL",
        "content": """# 生产周报生成规范

## 报告周期：每周一至周日

## 报告内容

### 1. 生产完成情况
- 计划工单数量 vs 实际完成数量
- 计划产量 vs 实际产量
- 完成率 = 实际完成 / 计划 × 100%

### 2. 质量指标
- 一次交验合格率（目标 ≥ 98%）
- 不良品数量及Top3不良类型
- 客户投诉/退货情况

### 3. 设备效率
- OEE（设备综合效率）= 时间稼动率 × 性能稼动率 × 良品率
- 各线体OEE对比
- 非计划停机时间及原因Top3

### 4. 物料情况
- 缺料工单数
- 呆滞料金额
- 库存周转率

### 5. 异常与改进
- 本周重大异常事件
- 已采取的纠正措施
- 下周重点改进事项

## 数据来源
- MES系统：工单、产量、良率
- 设备监控系统：OEE、停机时间
- ERP系统：库存、采购
- 质量系统：不良品、投诉

## 提交时间：每周一上午10:00前
"""
    },
]


def generate_sop_docs():
    # 保存 SOP 文档
    with open(DATA_DIR / "sop_documents.json", "w", encoding="utf-8") as f:
        json.dump(SOP_DOCS, f, ensure_ascii=False, indent=2)

    # 保存故障代码表
    with open(DATA_DIR / "fault_codes.json", "w", encoding="utf-8") as f:
        json.dump(FAULT_CODES, f, ensure_ascii=False, indent=2)

    print(f"✅ SOP文档：{len(SOP_DOCS)} 份")
    print(f"✅ 故障代码：{len(FAULT_CODES)} 条")


# ============================================================
# 4. 物料 BOM + 库存
# ============================================================

MATERIAL_NAMES = {
    "原材料": ["铝合金板6061-T6", "不锈钢棒304", "ABS塑料粒", "PC塑料粒", "铜排T2", "冷轧钢板SPCC", "铝型材6063", "硅胶原料", "环氧板FR-4", "尼龙棒PA66"],
    "半成品": ["铝合金外壳毛坯", "塑料面板半成品", "金属支架冲压件", "电路板PCBA", "齿轮毛坯", "转轴组件", "密封圈半成品", "散热片毛坯", "线束组件", "外壳喷涂件"],
    "包装材料": ["瓦楞纸箱", "气泡膜", "PE包装袋", "打包带", "标签贴纸", "泡沫护角", "说明书", "合格证", "干燥剂", "托盘"],
    "辅料": ["切削液", "润滑油", "液压油", "螺丝M4x10", "螺丝M6x20", "螺母M4", "螺母M6", "垫片Φ8", "扎带", "清洁剂"],
}

MATERIALS = []
for i in range(1, 51):
    mat_type = random.choice(["原材料", "半成品", "包装材料", "辅料"])
    name_pool = MATERIAL_NAMES[mat_type]
    MATERIALS.append({
        "mat_code": f"M-{i:04d}",
        "mat_name": random.choice(name_pool),
        "type": mat_type,
        "unit": random.choice(["个", "kg", "m", "套", "L"]),
        "spec": f"规格-{random.randint(10, 99)}",
    })


def generate_bom_and_inventory():
    # 为每个产品生成 BOM
    boms = {}
    for product in PRODUCTS:
        num_items = random.randint(5, 10)
        selected = random.sample(MATERIALS, num_items)
        bom_items = []
        for mat in selected:
            bom_items.append({
                "mat_code": mat["mat_code"],
                "mat_name": mat["mat_name"],
                "quantity": random.choice([1, 2, 3, 5, 10]),
                "unit": mat["unit"],
            })
        boms[product["code"]] = {
            "product_code": product["code"],
            "product_name": product["name"],
            "items": bom_items,
        }

    with open(DATA_DIR / "product_bom.json", "w", encoding="utf-8") as f:
        json.dump(boms, f, ensure_ascii=False, indent=2)

    # 生成库存数据
    inventory = []
    for mat in MATERIALS:
        safety_stock = random.choice([100, 200, 500, 1000])
        in_transit = random.choice([0, 0, 0, 500, 1000, 2000])  # 60%概率无在途

        # 正常物料：库存为安全库存的0.5-3倍
        base_stock = int(safety_stock * random.uniform(0.5, 3.0))

        # 故意设置缺料（库存 < 安全库存的50%）
        if mat["mat_code"] in ["M-0005", "M-0012", "M-0023", "M-0035", "M-0048"]:
            base_stock = random.randint(0, safety_stock // 2)

        # 故意设置呆滞料（库存远大于安全库存，8-15倍）
        if mat["mat_code"] in ["M-0008", "M-0019", "M-0042"]:
            base_stock = safety_stock * random.randint(8, 15)

        inventory.append({
            "mat_code": mat["mat_code"],
            "mat_name": mat["mat_name"],
            "type": mat["type"],
            "unit": mat["unit"],
            "stock_qty": base_stock,
            "safety_stock": safety_stock,
            "in_transit_qty": in_transit,
            "reserved_qty": random.randint(0, base_stock // 3),
            "warehouse": random.choice(["原材料仓", "线边仓A", "线边仓B", "成品仓"]),
            "last_inbound": (datetime(2026, 9, 7) - timedelta(days=random.randint(0, 30))).isoformat(),
        })

    with open(DATA_DIR / "inventory.json", "w", encoding="utf-8") as f:
        json.dump(inventory, f, ensure_ascii=False, indent=2)

    short_count = sum(1 for i in inventory if i["stock_qty"] < i["safety_stock"])
    print(f"✅ 产品BOM：{len(boms)} 个产品")
    print(f"✅ 物料库存：{len(inventory)} 种物料，其中 {short_count} 种低于安全库存")


# ============================================================
# 5. 维护工单历史
# ============================================================

def generate_maintenance_orders():
    orders = []
    for i in range(1, 16):
        eq = random.choice(EQUIPMENT)
        fault = random.choice(FAULT_CODES)
        start = datetime(2026, 8, 15) + timedelta(days=random.randint(0, 22), hours=random.randint(0, 12))
        duration = random.choice([0.5, 1, 2, 3, 4, 6, 8])
        end = start + timedelta(hours=duration)
        status = random.choice(["已完成", "已完成", "已完成", "已完成", "处理中"])
        # completed_at 与 status 绑定：仅已完成时有值
        completed_at = end.isoformat() if status == "已完成" else None

        orders.append({
            "mo_id": f"MO-2026-{i:04d}",
            "equipment_id": eq["id"],
            "equipment_name": eq["name"],
            "fault_code": fault["code"],
            "fault_name": fault["name"],
            "severity": fault["severity"],
            "fault_description": f"{fault['cause']}，导致设备{'告警' if fault['severity']=='高' else '运行异常'}",
            "action_taken": fault["action"],
            "status": status,
            "reported_at": start.isoformat(),
            "completed_at": completed_at,
            "downtime_hours": duration,
            "spare_parts": [
                {"name": random.choice(["轴承", "密封圈", "加热圈", "继电器", "传感器"]),
                 "qty": random.randint(1, 3)}
            ] if random.random() > 0.3 else [],
            "maintainer": random.choice(["赵工", "钱工", "孙工", "李工"]),
            "cost": random.randint(100, 5000),
        })

    with open(DATA_DIR / "maintenance_orders.json", "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    print(f"✅ 维护工单：{len(orders)} 条，平均停机 {sum(o['downtime_hours'] for o in orders)/len(orders):.1f} 小时")


# ============================================================
# 主函数
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("开始生成模拟数据...")
    print("=" * 50)
    generate_equipment_timeseries()
    generate_work_orders()
    generate_sop_docs()
    generate_bom_and_inventory()
    generate_maintenance_orders()
    print("=" * 50)
    print(f"✅ 全部数据已生成至：{DATA_DIR}")
    print("=" * 50)
