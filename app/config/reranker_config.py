# 导入核心依赖：数据类 + 环境变量读取（.env 由 app.config.env 统一加载）
from dataclasses import dataclass

from app.config.env import get_bool, get_str


@dataclass
class RerankerConfig:
    bge_reranker_large: str   # 本地模型路径
    bge_reranker_device: str  # 运行设备(cuda:0/cpu)
    bge_reranker_fp16: bool   # 是否开启半精度（1=True/0=False）


# 实例化配置对象，和原代码lm_config风格保持一致
reranker_config = RerankerConfig(
    bge_reranker_large=get_str("BGE_RERANKER_LARGE"),
    bge_reranker_device=get_str("BGE_RERANKER_DEVICE", "cpu"),
    # .env 里的 1/0/true/false 统一由 get_bool 解析
    bge_reranker_fp16=get_bool("BGE_RERANKER_FP16", False),
)
