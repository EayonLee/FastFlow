import httpx
from typing import List, Optional
from nexus.core.schemas import NodeDefinition
from nexus.config.config import get_config
from nexus.config.logger import get_logger

settings = get_config()
logger = get_logger(__name__)

def fetch_node_definitions(auth_token: Optional[str] = None) -> List[NodeDefinition]:
    """
    获取节点定义列表。
    """
    url = f"{settings.FASTFLOW_API_URL}/fastflow/api/v1/workflow/node/list"
    headers = {}
    if auth_token:
        headers["Authorization"] = auth_token

    try:
        # 获取节点定义，显式禁用代理（避免 VPN/系统代理干扰本地请求）
        with httpx.Client(trust_env=False) as client:
            response = client.get(url, headers=headers, timeout=5.0)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("code") == 200 or data.get("code") == 0:
            nodes_data = data.get("data", [])
            node_definitions = []
            
            for item in nodes_data:
                # 映射 Java VO 到 Python Pydantic Model
                # 当前 Java 返回 NodeDefVO: flowNodeType/name/icon/avatar/version/intro/position/inputs/outputs/nodeId
                try:
                    node_def = NodeDefinition(**item)
                    node_definitions.append(node_def)
                except Exception as e:
                    logger.warning(f"Failed to parse node definition: {item}, error: {e}")
                    
            return node_definitions
        else:
            logger.error(f"Failed to fetch node definitions: {data.get('message')}")
            return []
            
    except Exception as e:
        logger.error(f"Error fetching node definitions: {e}")
        return []
