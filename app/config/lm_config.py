# 导入核心依赖：数据类 + 环境变量读取（.env 由 app.config.env 统一加载）
from dataclasses import dataclass

from app.config.env import get_float, get_str


# 定义LLM服务配置
@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    lv_model: str
    llm_model: str
    llm_temperature: float


lm_config = LLMConfig(
    base_url=get_str("OPENAI_BASE_URL"),
    api_key=get_str("OPENAI_API_KEY"),
    lv_model=get_str("VL_MODEL"),
    llm_model=get_str("LLM_DEFAULT_MODEL"),
    # 缺值时用 0.1 兜底：原来 float(os.getenv(...)) 在 .env 没配时直接 TypeError
    llm_temperature=get_float("LLM_DEFAULT_TEMPERATURE", 0.1),
)
