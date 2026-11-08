# 导入核心依赖：数据类 + 环境变量读取（.env 由 app.config.env 统一加载）
from dataclasses import dataclass

from app.config.env import get_str


# 定义Milvus向量数据库配置类
@dataclass
class MilvusConfig:
    milvus_url: str          # Milvus服务端连接地址
    chunks_collection: str   # 存储切片的集合名称
    entity_name_collection: str  # 预留-实体名称集合
    item_name_collection: str    # 存储文档对应实体类的集合名称


# 实例化Milvus配置对象（和其他配置对象命名风格统一）
milvus_config = MilvusConfig(
    milvus_url=get_str("MILVUS_URL", "http://127.0.0.1:19530"),
    # 集合名给默认值，与 .env 保持一致；.env 里配了就以 .env 为准
    chunks_collection=get_str("CHUNKS_COLLECTION", "kb_chunks"),
    entity_name_collection=get_str("ENTITY_NAME_COLLECTION", "kb_graph_entity_names"),
    item_name_collection=get_str("ITEM_NAME_COLLECTION", "kb_item_names"),
)
