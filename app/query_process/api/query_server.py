
# 6个接口  健康状态 返回页面  发起提问   sse长连接  查看历史对话  清空历史对话
from pathlib import Path
import math
import time
import uuid
import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
from app.core.logger import logger
from app.query_process.agent.state import create_query_default_state
from app.utils.path_util import PROJECT_ROOT

from app.utils.task_utils import (
    clear_task,          # 每轮提问前重置该 session 的进度状态（否则进度会继承上一轮对话）
    get_done_task_list,
    get_running_task_list,
    get_task_meta,
    get_task_result,
    get_task_status,
    list_task_ids,
    set_task_meta,
    task_exists,
    update_task_status,
)
from app.utils.sse_utils import create_sse_queue, push_to_session, SSEEvent, sse_generator
from app.clients.mongo_history_utils import clear_history, get_recent_messages
from app.query_process.agent.main_graph import query_app


# 定义fastapi对象
app = FastAPI(title="query service", description="格物致知查询服务！")

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康状态
@app.get("/health")
async def health():
    logger.info(f"触发后台检测检查接口，数据一切正常！！")
    return {"status": "ok"}


# 返回页面（chat.html / query_monitor.html 共用）
def _page_response(filename: str) -> FileResponse:
    """返回 query_process/page 目录下的静态页面"""
    page_path = PROJECT_ROOT / 'app' / 'query_process' / 'page' / filename
    if not page_path.exists():
        raise HTTPException(status_code=404, detail=f"{filename}文件不存在")
    return FileResponse(page_path)


@app.get("/chat.html")
async def chat_html():
    """返回 chat.html 对话页面"""
    return _page_response("chat.html")


@app.get("/query_monitor.html")
async def query_monitor_html():
    """返回 query_monitor.html 查询监控页面"""
    return _page_response("query_monitor.html")


# 发起提问接口
# 接收参数的类型
class QueryRequest(BaseModel):
    query: str = Field(..., title="查询内容,必须传递")
    session_id:str = Field(None, title="会话id，可以不传递，后台uuid生成第一个！")
    is_stream:bool = Field(False, title="是否流式返回结果")


def run_query_graph(query: str, session_id: str, is_stream: bool):
    # 一会回调用 main_graph执行
    # 关键：进度事件是用 session_id 作为 key 存的，不清空的话本轮会继承上一轮的
    # done/running 列表，前端“阶段进度”就会一直停在上一次对话的节点上。
    # 统一在这里（流式/非流式都走这个入口）重置一次。
    clear_task(session_id)

    # 记录本轮元信息，供 /query/monitor 监控页展示（问题原文、开始时间）
    set_task_meta(session_id, query=query, started_at=time.time(), finished_at=None, error="")

    # 本次任务开启了！ is_stream = True 把结果加入到队列，sse可以取到
    update_task_status(session_id, "processing", is_stream)

    state = create_query_default_state(
        session_id=session_id,
        original_query=query,
        is_stream=is_stream
    )
    try:
        query_app.invoke(state)
        # 本次任务开启了！ is_stream = True 把结果加入到队列，sse可以取到
        update_task_status(session_id, "completed", is_stream)
        set_task_meta(session_id, finished_at=time.time())
    except Exception as e:
        logger.exception(f"---session_id = {session_id},查询流程出现异常！！{str(e)}")
        # 修改 event = process
        update_task_status(session_id, "failed", is_stream)
        set_task_meta(session_id, finished_at=time.time(), error=str(e))
        # 推送指定类型的事件
        push_to_session(session_id, SSEEvent.ERROR, {"error": str(e)})


@app.post("/query")  # 客户端 -》 问题 -》 graph开启了 -》 查到rag的结果 -》 返回即可！！
async def query(request: QueryRequest,background_tasks: BackgroundTasks):
    """
    :param request: 请求参数
    :param background_tasks: 异步执行函数  is_stream = True
    :return:
    """
    query = request.query
    session_id = request.session_id or str(uuid.uuid4())
    is_stream = request.is_stream
    # 判断是不是流式处理 （异步 -》 先返回一个结果 开始处理 | 后台运行图，结果向前端推送）
    if is_stream:
        # 只要开启流式处理，我们业务中就是将数据，插入到队列中！ {session_id , queue [update_task_state , add_running_task,add_done_list]}
        # 创建当前session_id对应的队列 =》 _session_stream
        create_sse_queue(session_id)
        # 异步执行  立即返回结果前端 || 中间的过程 sse 一点一点推送给前端
        background_tasks.add_task(run_query_graph, query, session_id, is_stream)
        logger.info(f"query:{query}已经开启了异步和流式处理！！")
        return {
            "session_id": session_id,
            "message": "本次查询处理中...."
        }
    else:
        # 同步执行：必须丢到线程池里跑，不能直接在事件循环里调用。
        # 原因1：查询要跑几十秒甚至几分钟，会阻塞整个服务的所有请求；
        # 原因2：图里的 node_web_search_mcp 用 asyncio.run 起协程，
        #        在已有事件循环里调用会抛
        #        "asyncio.run() cannot be called from a running event loop"。
        await run_in_threadpool(run_query_graph, query, session_id, is_stream)
        # 获取最后一个节点插入的结果！ node_answer_output (answer)
        answer = get_task_result(session_id,"answer")  # task_utils 封装的一个存储会话结果函数
        # 返回对应的json数据即可
        logger.info(f"query:{query}开启同步处理！处理结果为：{answer}!")
        return {
            "answer": answer,
            "session_id": session_id,
            "message": "本次查询处理完毕！",
            # 每轮开头已 clear_task，这里拿到的是本轮的节点，不会混入上一轮
            "done_list": get_done_task_list(session_id)
        }


@app.get("/stream/{session_id}")
async def stream(session_id: str,request:Request):
    """
    :param session_id:
    :param request: 前端的原生请求对象，可以判断是否断开连接！！
    :return:
    """
    logger.info(f"session_id = {session_id}客户端，已经和后台建立了长连接！")
    return StreamingResponse(
        sse_generator(session_id,request),
        media_type="text/event-stream"
    )


@app.get("/history/{session_id}")
async def history(session_id: str,limit: int = 10):
    """
    :param session_id:
    :param limit: 切割的数量
    :return:
    """
    # 获取历史对话
    chats =  get_recent_messages(session_id,limit)
    # chat mongodb _id -> ObjectId -> 不能直接序列化 json
    # items = []
    # for chat in chats:
    #     items.append(chat)
    logger.info(f"查询历史对话，session_id = {session_id}成功！查询数据为：{chats}")
    return {
        "session_id":session_id,
        "items": chats
    }

@app.delete("/history/{session_id}")
async def delete_history(session_id: str):
    """
    :param session_id:
    :return:
    """
    # 删除历史对话
    delete_count = clear_history(session_id)
    logger.info(f"删除历史对话，session_id = {session_id}成功,删除数量：{delete_count}！")
    return {
        "deleted_count":delete_count,
        "message": f"{session_id}聊天记录删除成功！"
    }


# --------------------------
# 查询监控（query_monitor.html 用）
# 数据来自 task_utils 的内存字典，只在单进程内有效
# --------------------------
def _latency_ms(meta: dict) -> int | None:
    """根据 started_at / finished_at 算耗时（毫秒），没结束则返回 None"""
    started_at = meta.get("started_at")
    finished_at = meta.get("finished_at")
    if started_at and finished_at:
        return int((finished_at - started_at) * 1000)
    return None


def _task_snapshot(session_id: str) -> dict:
    """把一个 session 的进度/元信息拼成监控页需要的结构
    注意：/query 的进度是按 session_id 存的，每个会话只保留最近一轮
    """
    meta = get_task_meta(session_id)
    return {
        "session_id": session_id,
        "query": meta.get("query", ""),
        "status": get_task_status(session_id) or "processing",
        "latency_ms": _latency_ms(meta),
        "done_count": len(get_done_task_list(session_id)),
        "running_count": len(get_running_task_list(session_id)),
        "answer_len": len(get_task_result(session_id, "answer") or ""),
        "updated_at": meta.get("finished_at") or meta.get("started_at"),
        "error": meta.get("error", ""),
    }


# 注意：/recent 必须声明在 /{session_id} 之前，否则会被动态路由吃掉
@app.get("/query/monitor/recent")
async def query_monitor_recent(limit: int = 200):
    """最近查询列表 + 汇总指标"""
    limit = max(1, min(limit, 1000))
    all_items = [_task_snapshot(sid) for sid in list_task_ids()]
    # 最近更新的排前面（没有时间戳的排最后）
    all_items.sort(key=lambda x: x["updated_at"] or 0, reverse=True)

    completed = sum(1 for x in all_items if x["status"] == "completed")
    failed = sum(1 for x in all_items if x["status"] == "failed")
    finished = completed + failed
    latencies = sorted(x["latency_ms"] for x in all_items if x["latency_ms"] is not None)

    if latencies:
        # P95 用「ceil(0.95*n)-1」取下标，避免小样本时越界
        p95_index = min(len(latencies) - 1, max(0, math.ceil(0.95 * len(latencies)) - 1))
        p95 = latencies[p95_index]
    else:
        p95 = 0

    return {
        "summary": {
            "total": len(all_items),
            "completed": completed,
            "failed": failed,
            "processing": len(all_items) - finished,
            "success_rate": round(completed / finished * 100, 1) if finished else 0,
            "p95_latency_ms": p95,
        },
        "items": all_items[:limit],
    }


@app.get("/query/monitor/{session_id}")
async def query_monitor_detail(session_id: str):
    """单个 session 的详情（不存在的 id 返回空结构，不会凭空创建记录）"""
    if not task_exists(session_id):
        return {
            "session_id": session_id,
            "query": "",
            "status": "",
            "latency_ms": None,
            "done_list": [],
            "running_list": [],
            "error": "",
        }

    snapshot = _task_snapshot(session_id)
    snapshot["done_list"] = get_done_task_list(session_id)
    snapshot["running_list"] = get_running_task_list(session_id)
    return snapshot


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8001)