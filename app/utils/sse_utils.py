import json
import queue
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import Request

from app.core.logger import logger


class SSEEvent:
    READY = "ready"         # 连接建立
    PROGRESS = "progress"   # 任务节点进度
    DELTA = "delta"         # LLM 流式输出增量
    FINAL = "final"         # 最终完整答案
    ERROR = "error"         # 错误信息
    CLOSE = "__close__"     # 关闭连接信号


# 全局 SSE 会话队列存储
# Key: session_id, Value: queue.Queue
_session_stream: Dict[str, queue.Queue] = {}

def get_sse_queue(session_id: str) -> Optional["queue.Queue"]:
    """获取指定 session 的队列"""
    return _session_stream.get(session_id)

def create_sse_queue(session_id: str) -> "queue.Queue":
    """创建并注册一个新的 SSE 队列

    同一 session 再次提问时，上一轮的 generator 可能还挂在旧队列上。
    它退出时的 finally 会调用 remove_sse_queue，如果不做保护就会把这里新建的
    队列一起删掉，于是本轮所有 progress 事件都被推到一个没人消费的队列里，
    前端表现就是“进度不刷新”。所以这里先给旧队列塞一个关闭信号，让它自己退干净。
    """
    logger.debug("[SSE] 创建队列: session_id={}", session_id)
    old_queue = _session_stream.get(session_id)
    if old_queue is not None:
        try:
            old_queue.put({"event": SSEEvent.CLOSE, "data": {}})
        except Exception as exc:  # noqa: BLE001
            logger.warning("[SSE] 关闭旧队列失败: session_id={} 错误={}", session_id, exc)

    q = queue.Queue()
    _session_stream[session_id] = q
    return q

def remove_sse_queue(session_id: str, target_queue: "queue.Queue" = None):
    """移除指定 session 的队列

    target_queue 不为空时，只有当前注册的队列确实是它才会移除，
    避免上一轮的 generator 误删新一轮刚注册的队列。
    """
    if target_queue is not None and _session_stream.get(session_id) is not target_queue:
        logger.debug("[SSE] 跳过清理：队列已被新一轮替换 session_id={}", session_id)
        return
    logger.debug("[SSE] 移除队列: session_id={}", session_id)
    _session_stream.pop(session_id, None)

def _sse_pack(event: str, data: Dict[str, Any]) -> str:
    """打包 SSE 消息格式"""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"

def push_to_session(session_id: str, event: str, data: Dict[str, Any]):
    """
    通过 session_id 推送事件
    """
    stream_queue = get_sse_queue(session_id)
    if stream_queue:
        stream_queue.put({"event": event, "data": data})
    else:
        # 没有队列通常是「前端还没连上」或「已经断开」，属于可预期情况，给 warning 便于排查
        logger.warning("[SSE] 推送时找不到队列: session_id={} event={}", session_id, event)

async def sse_generator(session_id: str, request: Request):
    """
    SSE 生成器，用于 FastAPI 的 StreamingResponse
    """
    logger.debug("[SSE] 生成器启动: session_id={}", session_id)
    stream_queue = get_sse_queue(session_id)
    if stream_queue is None:
        # 如果没有对应的队列，直接结束
        logger.error(
            "[SSE] 队列不存在，直接结束: session_id={} 当前活跃会话={}",
            session_id,
            list(_session_stream.keys()),
        )
        return

    loop = asyncio.get_running_loop()
    try:
        # 发送连接建立信号
        logger.debug("[SSE] 发送 ready 信号: session_id={}", session_id)
        yield _sse_pack("ready", {})

        while True:
            # 若客户端断开，尽快退出
            if await request.is_disconnected():
                logger.debug("[SSE] 客户端断开连接: session_id={}", session_id)
                break

            try:
                # 使用 run_in_executor 避免阻塞 async 事件循环
                msg = await loop.run_in_executor(None, stream_queue.get, True, 1.0)
            except queue.Empty:
                continue

            event = msg.get("event")
            data = msg.get("data")

            # 特殊关闭事件
            if event == SSEEvent.CLOSE:
                logger.debug("[SSE] 收到关闭信号: session_id={}", session_id)
                break

            yield _sse_pack(event, data)
    except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
        logger.debug("[SSE] 客户端连接中断(Cancelled/Reset/Pipe): session_id={}", session_id)
        # 生成器被取消/对端断开：静默退出
        return
    except Exception as exc:  # noqa: BLE001
        logger.error("[SSE] 生成器异常: session_id={} 错误={}", session_id, exc)
    finally:
        logger.debug("[SSE] 生成器结束: session_id={}", session_id)
        # 清理资源：只清理自己消费的那个队列，别误删新一轮的队列
        remove_sse_queue(session_id, stream_queue)
