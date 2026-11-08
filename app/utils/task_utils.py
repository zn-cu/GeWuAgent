from typing import Any, Dict, List
from .sse_utils import push_to_session

# ---------------------------
# 内存态任务追踪（单进程）
# ---------------------------
# key: task_id
# value: 节点名列表（原始英文/节点ID）
_tasks_running_list: Dict[str, List[str]] = {}
_tasks_done_list: Dict[str, List[str]] = {}

# key: task_id
# value: status 字符串（如 pending/processing/completed/failed）
_tasks_status: Dict[str, str] = {}

# key: task_id
# value: 任务结果（例如 query 的 answer）
_tasks_result: Dict[str, Dict[str, str]] = {}

# key: task_id
# value: 任务元信息（query / started_at / finished_at / error），供监控页展示
_tasks_meta: Dict[str, Dict[str, Any]] = {}

TASK_STATUS_PENDING = "pending"
TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

# 节点名 -> 中文名映射（用于前端展示）
# 说明：这里的 key 必须与 LangGraph add_node("xxx", ...) 中的节点名一致。
#       只保留两个图（import_process / query_process）里真实存在的节点，
#       之前预留的 node_import_kg / node_query_kg / node_multi_search / node_join
#       在图里并不存在，已经删掉，需要时再按实际节点补。
_NODE_NAME_TO_CN: Dict[str, str] = {
    "upload_file": "开始上传文件",
    "node_entry": "检查文件",
    "node_pdf_to_md": "PDF转Markdown",
    "node_md_img": "Markdown图片处理",
    "node_item_name_recognition": "主体名称识别",
    "node_document_split": "文档切分",
    "node_bge_embedding": "向量生成",
    "node_import_milvus": "导入向量库",
    "__end__": "处理完成",
    "END": "处理完成",
    # --- Query 流程节点（app/query_process/agent/main_graph.py）---
    "node_item_name_confirm": "确认问题产品",
    "node_answer_output": "生成答案",
    "node_rerank": "重排序",
    "node_rrf": "倒排融合",
    "node_web_search_mcp": "网络搜索",
    "node_search_embedding": "切片搜索",
    "node_search_embedding_hyde": "切片搜索(假设性文档)",
}


def _ensure_task(task_id: str) -> None:
    """确保 task_id 对应的数据结构已初始化。"""
    if task_id not in _tasks_running_list:
        _tasks_running_list[task_id] = []
    if task_id not in _tasks_done_list:
        _tasks_done_list[task_id] = []
    if task_id not in _tasks_result:
        _tasks_result[task_id] = {}


def _to_cn(node_name: str) -> str:
    """将节点名转换为中文展示名；若无映射则返回原名。"""
    return _NODE_NAME_TO_CN.get(node_name, node_name)


def add_running_task(task_id: str, node_name: str, is_stream: bool = False) -> None:
    """
    添加“正在运行”的节点任务。

    参数：
    - task_id: 任务ID
    - node_name: 节点名称(节点ID)
    """
    _ensure_task(task_id)
    running = _tasks_running_list[task_id]
    # 避免重复追加
    if node_name not in running:
        running.append(node_name)

    if is_stream:
        task_push_queue(task_id)


def add_done_task(task_id: str, node_name: str, is_stream: bool = False) -> None:
    """
    添加“已完成”的节点任务。

    注意：添加已完成任务时，会把同名的“正在运行”任务删除。

    参数：
    - task_id: 任务ID
    - node_name: 节点名称(节点ID)
    """
    _ensure_task(task_id)

    # 1) 从 running 中移除同名节点（可能出现重复，移除所有）
    running = _tasks_running_list[task_id]
    _tasks_running_list[task_id] = [n for n in running if n != node_name]

    # 2) 追加到 done（保持完成顺序），避免重复
    done = _tasks_done_list[task_id]
    if node_name not in done:
        done.append(node_name)

    if is_stream:
        task_push_queue(task_id)


def set_task_result(task_id: str, key: str, value: str) -> None:
    """
    存储任务结果字段（如 answer / error）。
    """
    _ensure_task(task_id)
    _tasks_result[task_id][key] = value


def get_task_result(task_id: str, key: str, default: str = "") -> str:
    """
    获取任务结果字段（如 answer / error）。
    """
    _ensure_task(task_id)
    return _tasks_result.get(task_id, {}).get(key, default)


def get_task_status(task_id: str) -> str:
    """
    获取当前任务状态。

    参数：
    - task_id: 任务ID

    返回：
    - str: 状态名称；如果未设置过则返回空字符串
    """
    return _tasks_status.get(task_id, "")


def get_done_task_list(task_id: str) -> List[str]:
    """
    获取已完成节点列表（中文展示）。


    """
    _ensure_task(task_id)
    done = _tasks_done_list.get(task_id, [])
    return [_to_cn(n) for n in done]


def get_running_task_list(task_id: str) -> List[str]:
    """
    获取正在运行节点列表（中文展示）。

    """
    _ensure_task(task_id)
    running = _tasks_running_list.get(task_id, [])
    return [_to_cn(n) for n in running]


def update_task_status(task_id: str, status_name: str, push_queue: bool = False) -> None:
    """
    更新任务状态。

    参数：
    - task_id: 任务ID
    - status_name: 状态名称（字符串）
    """
    _tasks_status[task_id] = status_name
    if push_queue:
        task_push_queue(task_id)


def task_push_queue(task_id: str):
    push_to_session(task_id, "progress", {
        "status": get_task_status(task_id),
        "done_list": get_done_task_list(task_id),
        "running_list": get_running_task_list(task_id),
    })


#
def clear_task(task_id: str):
    _tasks_running_list.pop(task_id, None)
    _tasks_done_list.pop(task_id, None)
    _tasks_status.pop(task_id, None)
    _tasks_result.pop(task_id, None)
    _tasks_meta.pop(task_id, None)


# ---------------------------
# 任务元信息（给 /query/monitor 监控页用）
# ---------------------------
def set_task_meta(task_id: str, **fields: Any) -> None:
    """写入任务元信息（如 query / started_at / finished_at / error），不覆盖其它字段"""
    _tasks_meta.setdefault(task_id, {}).update(fields)


def get_task_meta(task_id: str) -> Dict[str, Any]:
    """读取任务元信息（返回副本，避免调用方误改内部状态）"""
    return dict(_tasks_meta.get(task_id, {}))


def list_task_ids() -> List[str]:
    """列出当前进程内跟踪的所有 task_id（按状态字典的 key）"""
    return list(_tasks_status.keys())


def task_exists(task_id: str) -> bool:
    """判断该 task_id 是否被跟踪过（避免查不存在的 id 时凭空创建空记录）"""
    return task_id in _tasks_status