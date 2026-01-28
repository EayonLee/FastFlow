import httpx
from typing import List, Optional
from core.schemas import NodeDefinition
from config.config import get_config
from config.logger import get_logger

settings = get_config()
logger = get_logger(__name__)

def fetch_node_definitions(auth_token: Optional[str] = None) -> List[NodeDefinition]:
    """
    获取节点定义列表。
    """
    url = f"{settings.FASTFLOW_API_URL}/fastflow/api/v1/workflow/nodes/definitions"
    headers = {}
    if auth_token:
        headers["Authorization"] = auth_token

    try:
        # 使用 httpx 获取节点定义
        response = httpx.get(url, headers=headers, timeout=5.0)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("code") == 200 or data.get("code") == 0:
            nodes_data = data.get("data", [])
            node_definitions = []
            
            for item in nodes_data:
                # 映射 Java VO 到 Python Pydantic Model
                # 假设 Java 返回结构: { "type": "...", "label": "...", "category": "...", "inputType": "...", "outputType": "...", "schema": {...} }
                try:
                    node_def = NodeDefinition(
                        type=item.get("type"),
                        label=item.get("label"),
                        category=item.get("category"),
                        input_type=item.get("inputType"),
                        output_type=item.get("outputType"),
                        schema=item.get("configSchema") or item.get("schema") or {} 
                    )
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
