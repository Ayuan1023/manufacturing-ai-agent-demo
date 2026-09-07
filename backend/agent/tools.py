"""
Agent 工具注册层
将 3 个 MCP Server 的 18 个工具包装为 LangChain 可用的 StructuredTool
"""
import sys
from pathlib import Path
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# 将 MCP 模块加入路径
MCP_DIR = Path(__file__).parent.parent / "mcp_servers"
sys.path.insert(0, str(MCP_DIR))

import equipment_mcp
import mes_mcp
import knowledge_mcp


def _tool_function(tool):
    """Return the underlying callable across FastMCP versions and fallback mode."""
    return getattr(tool, "fn", tool)


# ============ 工具输入 Schema ============

class EquipmentListInput(BaseModel):
    pass


class EquipmentStatusInput(BaseModel):
    equipment_id: str = Field(description="设备ID，如 CNC-001、INJ-001")


class AlarmEquipmentInput(BaseModel):
    pass


class EquipmentHistoryInput(BaseModel):
    equipment_id: str = Field(description="设备ID")
    sensor_id: str = Field(description="测点ID，如 spindle_temp、power")
    hours: int = Field(default=24, description="查询最近多少小时，1-168")


class AnalyzeAnomalyInput(BaseModel):
    equipment_id: str = Field(description="设备ID")


class MaintenanceHistoryInput(BaseModel):
    equipment_id: str = Field(default=None, description="设备ID，可选")
    limit: int = Field(default=10, description="返回条数")


class WorkOrdersInput(BaseModel):
    status: str = Field(default=None, description="状态筛选：待排产/已排产/进行中/已完成/异常暂停")
    line: str = Field(default=None, description="产线筛选：1号线/2号线/3号线/4号线")
    limit: int = Field(default=20, description="返回条数")


class WorkOrderDetailInput(BaseModel):
    wo_id: str = Field(description="工单号，如 WO-2026-0001")


class ProductionStatsInput(BaseModel):
    days: int = Field(default=7, description="统计最近多少天")


class QualityAnalysisInput(BaseModel):
    pass


class MaterialAvailabilityInput(BaseModel):
    wo_id: str = Field(default=None, description="工单号")
    product_code: str = Field(default=None, description="产品编码")
    quantity: int = Field(default=None, description="生产数量")


class InventorySummaryInput(BaseModel):
    pass


class CreateWorkOrderDraftInput(BaseModel):
    product_code: str = Field(description="产品编码，如 P-A100")
    quantity: int = Field(description="生产数量")
    line: str = Field(description="产线：1号线/2号线/3号线/4号线")
    priority: str = Field(default="中", description="优先级：高/中/低")


class SearchSopInput(BaseModel):
    query: str = Field(description="搜索问题")
    top_k: int = Field(default=5, description="返回数量")


class SopDetailInput(BaseModel):
    sop_id: str = Field(description="SOP文档ID，如 SOP-001")


class ListSopInput(BaseModel):
    category: str = Field(default=None, description="分类筛选")


class SearchFaultCodeInput(BaseModel):
    code: str = Field(default=None, description="故障代码，如 E001")
    equipment: str = Field(default=None, description="设备类型：CNC/INJECTION/PRESS/ASSEMBLY/ALL")
    keyword: str = Field(default=None, description="关键词搜索")


class FaultCodeDetailInput(BaseModel):
    code: str = Field(description="故障代码")


# ============ 工具列表 ============

def get_all_tools() -> list:
    """获取所有注册的工具列表"""
    return [
        # 设备 MCP (6)
        StructuredTool(
            name="get_equipment_list",
            description="获取所有设备列表，包含设备ID、名称、类型、产线和当前状态。当用户问'有哪些设备'、'设备列表'时使用。",
            func=_tool_function(equipment_mcp.get_equipment_list),
            args_schema=EquipmentListInput,
        ),
        StructuredTool(
            name="get_equipment_status",
            description="获取指定设备的当前实时状态和告警信息。当用户问某台设备'当前状态'、'实时数据'时使用。",
            func=_tool_function(equipment_mcp.get_equipment_status),
            args_schema=EquipmentStatusInput,
        ),
        StructuredTool(
            name="get_alarm_equipment",
            description="获取当前处于告警状态的设备列表及告警详情。当用户问'哪些设备告警'、'有什么异常'时使用。",
            func=_tool_function(equipment_mcp.get_alarm_equipment),
            args_schema=AlarmEquipmentInput,
        ),
        StructuredTool(
            name="get_equipment_history",
            description="获取指定设备某测点的历史时序数据，用于趋势分析。当用户问'温度趋势'、'历史数据'时使用。",
            func=_tool_function(equipment_mcp.get_equipment_history),
            args_schema=EquipmentHistoryInput,
        ),
        StructuredTool(
            name="analyze_equipment_anomaly",
            description="对指定设备进行异常分析，检查超阈值和劣化趋势。当用户问'分析设备异常'、'诊断故障'时使用。",
            func=_tool_function(equipment_mcp.analyze_equipment_anomaly),
            args_schema=AnalyzeAnomalyInput,
        ),
        StructuredTool(
            name="get_maintenance_history",
            description="获取设备维护工单历史，可按设备筛选。当用户问'维护记录'、'维修历史'时使用。",
            func=_tool_function(equipment_mcp.get_maintenance_history),
            args_schema=MaintenanceHistoryInput,
        ),
        # MES MCP (7)
        StructuredTool(
            name="get_work_orders",
            description="查询MES工单列表，可按状态和产线筛选。当用户问'工单列表'、'进行中的工单'时使用。",
            func=_tool_function(mes_mcp.get_work_orders),
            args_schema=WorkOrdersInput,
        ),
        StructuredTool(
            name="get_work_order_detail",
            description="获取指定工单的详细信息，包括进度、良率、工艺路线。当用户问'工单详情'、'工单进度'时使用。",
            func=_tool_function(mes_mcp.get_work_order_detail),
            args_schema=WorkOrderDetailInput,
        ),
        StructuredTool(
            name="get_production_stats",
            description="获取生产统计数据，包括完成率、产量、良率、各线体对比。当用户问'生产情况'、'本周产量'时使用。",
            func=_tool_function(mes_mcp.get_production_stats),
            args_schema=ProductionStatsInput,
        ),
        StructuredTool(
            name="get_quality_analysis",
            description="获取质量分析数据，包括良率分布、低良率工单。当用户问'质量情况'、'良率分析'时使用。",
            func=_tool_function(mes_mcp.get_quality_analysis),
            args_schema=QualityAnalysisInput,
        ),
        StructuredTool(
            name="check_material_availability",
            description="检查物料齐套情况，可按工单或产品+数量检查。当用户问'物料齐套吗'、'缺什么料'时使用。",
            func=_tool_function(mes_mcp.check_material_availability),
            args_schema=MaterialAvailabilityInput,
        ),
        StructuredTool(
            name="get_inventory_summary",
            description="获取库存概览，包括缺料预警、呆滞料。当用户问'库存情况'、'缺料预警'时使用。",
            func=_tool_function(mes_mcp.get_inventory_summary),
            args_schema=InventorySummaryInput,
        ),
        StructuredTool(
            name="create_work_order_draft",
            description="创建生产工单草稿（仅生成草稿，不写入系统，需人工确认）。当用户要求'创建工单'、'安排生产'时使用。这是写操作。",
            func=_tool_function(mes_mcp.create_work_order_draft),
            args_schema=CreateWorkOrderDraftInput,
        ),
        # 知识 MCP (5)
        StructuredTool(
            name="search_sop",
            description="语义搜索SOP文档，检索操作规程、安全规范、维护指南。当用户问'怎么操作'、'故障怎么处理'时使用。",
            func=_tool_function(knowledge_mcp.search_sop),
            args_schema=SearchSopInput,
        ),
        StructuredTool(
            name="get_sop_detail",
            description="获取指定SOP文档的完整内容。当用户需要查看完整操作规程时使用。",
            func=_tool_function(knowledge_mcp.get_sop_detail),
            args_schema=SopDetailInput,
        ),
        StructuredTool(
            name="list_sop_documents",
            description="列出所有SOP文档，可按分类筛选。当用户问'有哪些SOP'时使用。",
            func=_tool_function(knowledge_mcp.list_sop_documents),
            args_schema=ListSopInput,
        ),
        StructuredTool(
            name="search_fault_code",
            description="查询设备故障代码，获取故障原因和处理步骤。当用户问'E001是什么故障'、'报警代码'时使用。",
            func=_tool_function(knowledge_mcp.search_fault_code),
            args_schema=SearchFaultCodeInput,
        ),
        StructuredTool(
            name="get_fault_code_detail",
            description="获取指定故障代码的详细信息。当用户需要详细了解某个故障代码时使用。",
            func=_tool_function(knowledge_mcp.get_fault_code_detail),
            args_schema=FaultCodeDetailInput,
        ),
    ]


# 写操作工具列表（需要 HITL 确认）
WRITE_TOOLS = {"create_work_order_draft"}

# 工具描述映射（用于前端展示）
TOOL_DESCRIPTIONS = {
    "get_equipment_list": "查询设备列表",
    "get_equipment_status": "查询设备实时状态",
    "get_alarm_equipment": "查询告警设备",
    "get_equipment_history": "查询设备历史趋势",
    "analyze_equipment_anomaly": "设备异常分析",
    "get_maintenance_history": "查询维护历史",
    "get_work_orders": "查询工单列表",
    "get_work_order_detail": "查询工单详情",
    "get_production_stats": "生产统计",
    "get_quality_analysis": "质量分析",
    "check_material_availability": "物料齐套检查",
    "get_inventory_summary": "库存概览",
    "create_work_order_draft": "创建工单草稿",
    "search_sop": "SOP语义搜索",
    "get_sop_detail": "SOP详情",
    "list_sop_documents": "SOP列表",
    "search_fault_code": "故障代码查询",
    "get_fault_code_detail": "故障代码详情",
}
