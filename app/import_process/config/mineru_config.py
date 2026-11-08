# 导入核心依赖：数据类 + 环境变量读取（.env 由 app.config.env 统一加载）
from dataclasses import dataclass

from app.config.env import get_str


# 定义minerU服务配置
@dataclass
class MineruConfig:
    base_url: str
    api_token: str


mineru_config = MineruConfig(
    base_url=get_str("MINERU_BASE_URL", "https://mineru.net/api/v4"),
    api_token=get_str("MINERU_API_TOKEN"),
)
