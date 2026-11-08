# 导入核心依赖：数据类 + 环境变量读取（.env 由 app.config.env 统一加载）
from dataclasses import dataclass

from app.config.env import get_str


# 定义mcp的服务配置
@dataclass
class McpConfig:
    mcp_base_url: str
    api_key: str


mcp_config = McpConfig(
    mcp_base_url=get_str("MCP_DASHSCOPE_BASE_URL_STREAMABLE"),
    # 优先用 MCP 专用 key；没配则退回大模型那把（两者都是百炼 DashScope 的 key）。
    # 这样“联网搜索用的是哪个 key”在配置里是显式的，不再是隐式复用 OPENAI_API_KEY。
    api_key=get_str("MCP_DASHSCOPE_API_KEY") or get_str("OPENAI_API_KEY"),
)
