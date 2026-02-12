import httpx
from typing import Optional
from nexus.config.config import get_config
from nexus.config.logger import get_logger

settings = get_config()
logger = get_logger(__name__)
SUCCESS_CODES = {0, 200}
CHECK_LOGIN_PATH = "/fastflow/api/v1/auth/checkLogin"


def _build_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": auth_token}


def _is_success(code: object) -> bool:
    return code in SUCCESS_CODES

def check_login(auth_token: Optional[str] = None) -> bool:
    """
    校验登录状态。
    """
    if not auth_token:
        logger.warning("Check login without Authorization, Skip check.")
        return False

    url = f"{settings.FASTFLOW_API_URL}{CHECK_LOGIN_PATH}"

    try:
        # 使用 httpx 校验登录状态，显式禁用代理（避免 VPN/系统代理干扰本地请求）
        with httpx.Client(trust_env=False) as client:
            response = client.post(
                url,
                headers=_build_headers(auth_token),
                timeout=5.0,
                follow_redirects=True,
            )
        response.raise_for_status()

        response_data = response.json()
        if _is_success(response_data.get("code")):
            return True

        logger.error("Check login failed: %s", response_data.get("message"))
        return False
    except httpx.HTTPStatusError as e:
        logger.error(
            "Check login failed with status=%s  body=%s headers=%s",
            e.response.status_code,
            e.response.text,
            dict(e.response.headers),
        )
        return False
    except Exception as e:
        logger.error("Error checking login: %s", e)
        return False
