"""
知识检索 MCP Server
提供 SOP 文档语义搜索、故障代码查询等工具
使用 fastembed 做嵌入，ChromaDB 做向量存储
"""
import json
import hashlib
import os
from pathlib import Path
from typing import Optional
try:
    from .mcp_compat import FastMCP
except ImportError:
    from mcp_compat import FastMCP

DATA_DIR = Path(__file__).parent.parent / "data"
CHROMA_DIR = DATA_DIR / "chroma"

mcp = FastMCP("knowledge-base")
_collection = None


def _load_json(filename: str) -> dict | list:
    """加载 JSON 数据文件，文件不存在时返回结构化错误"""
    try:
        with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": f"数据文件 {filename} 不存在，请先运行数据生成器"}


def _get_collection():
    """懒加载 ChromaDB 集合，首次调用时构建索引"""
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    from chromadb.api.types import EmbeddingFunction, Embeddings
    from fastembed import TextEmbedding

    class FastEmbedEmbeddingFn(EmbeddingFunction):
        """使用 fastembed 的自定义嵌入函数"""
        def __init__(self, model_name="BAAI/bge-small-zh-v1.5"):
            self._model = TextEmbedding(model_name=model_name)
            self._model_name = model_name

        def __call__(self, input) -> Embeddings:
            embeddings = list(self._model.embed(input))
            return [e.tolist() for e in embeddings]

        def name(self) -> str:
            return f"fastembed-{self._model_name}"

        def get_config(self) -> dict:
            return {"model_name": self._model_name}

    CHROMA_DIR.mkdir(exist_ok=True)
    embed_fn = FastEmbedEmbeddingFn()

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name="sop_documents",
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    if collection.count() == 0:
        sops = _load_json("sop_documents.json")
        if isinstance(sops, list):
            ids, documents, metadatas = [], [], []
            for sop in sops:
                content = sop["content"]
                # 按 ## 标题切块，保留标题上下文
                sections = content.split("## ")
                for idx, section in enumerate(sections):
                    section = section.strip()
                    if len(section) < 20:
                        continue
                    # 第一个 section 是文档标题，加上标题前缀
                    if idx == 0:
                        text = f"{sop['title']}\n{section}"
                    else:
                        text = f"{sop['title']} - {section.split(chr(10))[0]}\n{section}"
                    doc_id = hashlib.md5(f"{sop['id']}_{idx}".encode()).hexdigest()[:16]
                    ids.append(doc_id)
                    documents.append(text)
                    metadatas.append({
                        "sop_id": sop["id"],
                        "title": sop["title"],
                        "category": sop["category"],
                        "equipment": sop["equipment"],
                        "paragraph_idx": idx,
                    })
            if ids:
                collection.add(ids=ids, documents=documents, metadatas=metadatas)

    _collection = collection
    return collection


def _keyword_search_sop(query: str, top_k: int) -> dict:
    """Offline fallback for the demo when vector dependencies are unavailable."""
    sops = _load_json("sop_documents.json")
    if isinstance(sops, dict) and "error" in sops:
        return sops

    query_text = query.strip().lower()
    keywords = [query_text]
    for keyword in ["换模", "换刀", "主轴", "温度", "安全", "保养", "校准", "报警", "故障"]:
        if keyword in query_text and keyword not in keywords:
            keywords.append(keyword)

    ranked = []
    for sop in sops:
        haystack = f"{sop['title']}\n{sop['content']}".lower()
        score = sum(haystack.count(keyword) for keyword in keywords if keyword)
        ranked.append((score, sop))

    ranked.sort(key=lambda item: item[0], reverse=True)
    results = []
    for rank, (score, sop) in enumerate(ranked[:top_k], start=1):
        results.append({
            "sop_id": sop["id"],
            "title": sop["title"],
            "category": sop["category"],
            "equipment": sop["equipment"],
            "similarity": round(min(99.0, 50.0 + score * 10.0), 1),
            "content": sop["content"][:500] + ("..." if len(sop["content"]) > 500 else ""),
            "rank": rank,
        })

    return {
        "query": query,
        "result_count": len(results),
        "distinct_documents": len(results),
        "mode": "keyword-fallback",
        "results": results,
    }


@mcp.tool()
def search_sop(query: str, top_k: int = 5) -> dict:
    """
    语义搜索 SOP 文档，根据用户问题检索最相关的操作规程、安全规范、维护指南等。
    当用户问"怎么操作"、"故障怎么处理"、"安全规范是什么"、"找一下SOP"时使用。

    参数:
        query: 搜索问题，如"主轴过热怎么办"、"CNC安全操作规程"、"换模步骤"
        top_k: 返回最相关的文档数量（按SOP去重后），默认5
    """
    if os.environ.get("ENABLE_VECTOR_RAG", "0") != "1":
        return _keyword_search_sop(query, top_k)

    try:
        collection = _get_collection()
    except Exception:
        return _keyword_search_sop(query, top_k)

    # 多取一些结果用于去重
    raw_results = collection.query(query_texts=[query], n_results=top_k * 3)

    # 按 sop_id 去重，每个文档只保留最高分段落
    seen_sops = {}
    if raw_results["documents"] and raw_results["documents"][0]:
        for doc, meta, dist in zip(
            raw_results["documents"][0],
            raw_results["metadatas"][0],
            raw_results["distances"][0] if raw_results["distances"] else [0] * len(raw_results["documents"][0])
        ):
            sop_id = meta["sop_id"]
            similarity = round((1 - dist) * 100, 1) if dist else 0
            if sop_id not in seen_sops or similarity > seen_sops[sop_id]["similarity"]:
                seen_sops[sop_id] = {
                    "sop_id": sop_id,
                    "title": meta["title"],
                    "category": meta["category"],
                    "equipment": meta["equipment"],
                    "similarity": similarity,
                    "content": doc[:500] + ("..." if len(doc) > 500 else ""),
                }

    # 按相似度排序，取 top_k
    items = sorted(seen_sops.values(), key=lambda x: x["similarity"], reverse=True)[:top_k]
    for i, item in enumerate(items):
        item["rank"] = i + 1

    return {
        "query": query,
        "result_count": len(items),
        "distinct_documents": len(seen_sops),
        "results": items,
    }


@mcp.tool()
def get_sop_detail(sop_id: str) -> dict:
    """
    获取指定 SOP 文档的完整内容。
    当用户需要查看完整操作规程、详细步骤时使用。

    参数:
        sop_id: SOP文档ID，如 SOP-001、SOP-002
    """
    sops = _load_json("sop_documents.json")
    if isinstance(sops, dict) and "error" in sops:
        return sops
    sop = next((s for s in sops if s["id"] == sop_id), None)
    if not sop:
        available = [s["id"] for s in sops]
        return {"error": f"SOP {sop_id} 不存在", "available": available}
    return sop


@mcp.tool()
def list_sop_documents(category: Optional[str] = None) -> dict:
    """
    列出所有 SOP 文档，可按分类筛选。
    当用户问"有哪些SOP"、"文档列表"、"安全规范有哪些"时使用。

    参数:
        category: 分类筛选，可选：安全规范、设备维护、作业指导、质量管理、故障处理、生产管理、报告规范
    """
    sops = _load_json("sop_documents.json")
    if isinstance(sops, dict) and "error" in sops:
        return sops
    if category:
        sops = [s for s in sops if s["category"] == category]
    result = [
        {"id": s["id"], "title": s["title"], "category": s["category"], "equipment": s["equipment"]}
        for s in sops
    ]
    return {"total": len(result), "documents": result}


@mcp.tool()
def search_fault_code(code: Optional[str] = None, equipment: Optional[str] = None, keyword: Optional[str] = None) -> dict:
    """
    查询设备故障代码，获取故障原因和处理步骤。
    当用户问"E001是什么故障"、"报警代码"、"故障怎么处理"时使用。

    参数:
        code: 故障代码，如 E001、E004。不填则按其他条件筛选
        equipment: 设备类型筛选，可选：CNC、INJECTION、PRESS、ASSEMBLY、ALL
        keyword: 关键词搜索，在故障名称和原因中搜索
    """
    faults = _load_json("fault_codes.json")
    if isinstance(faults, dict) and "error" in faults:
        return faults

    if code:
        faults = [f for f in faults if f["code"].lower() == code.lower()]
    if equipment and equipment != "ALL":
        faults = [f for f in faults if f["equipment"] in [equipment, "ALL"]]
    if keyword:
        kw = keyword.lower()
        faults = [f for f in faults if kw in f["name"].lower() or kw in f["cause"].lower()]

    if not faults:
        return {"error": "未找到匹配的故障代码", "total": 0}
    return {"total": len(faults), "faults": faults}


@mcp.tool()
def get_fault_code_detail(code: str) -> dict:
    """
    获取指定故障代码的详细信息，包括严重度、原因、处理步骤。
    当用户需要详细了解某个故障代码时使用。

    参数:
        code: 故障代码，如 E001
    """
    faults = _load_json("fault_codes.json")
    if isinstance(faults, dict) and "error" in faults:
        return faults
    fault = next((f for f in faults if f["code"].lower() == code.lower()), None)
    if not fault:
        return {"error": f"故障代码 {code} 不存在"}
    return fault


if __name__ == "__main__":
    mcp.run()
