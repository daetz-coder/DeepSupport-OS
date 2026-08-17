"""Configuration validation utilities."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from deepsupport_os.core.config import get_settings

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


def validate_configuration() -> dict[str, Any]:
    """Validate all configuration settings.
    
    Returns:
        dict with validation results
        
    Raises:
        ConfigurationError: If critical configuration is missing
    """
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    
    try:
        settings = get_settings()
    except Exception as e:
        raise ConfigurationError(f"无法加载配置: {e}")
    
    # Check critical environment variables
    if not settings.deepseek_api_key:
        errors.append("DEEPSEEK_API_KEY 未设置，LLM 功能将不可用")
    
    # Check database file permissions
    db_path = settings.resolve(settings.database_url.replace("sqlite:///", ""))
    if db_path.exists():
        if not os.access(db_path, os.R_OK | os.W_OK):
            errors.append(f"数据库文件 {db_path} 没有读写权限")
    else:
        db_dir = db_path.parent
        if db_dir.exists() and not os.access(db_dir, os.W_OK):
            errors.append(f"数据库目录 {db_dir} 没有写权限")
    
    # Check workspace directory
    workspace = settings.resolve(settings.workspace_dir)
    if not workspace.exists():
        warnings.append(f"工作区目录 {workspace} 不存在，将自动创建")
    elif not os.access(workspace, os.W_OK):
        errors.append(f"工作区目录 {workspace} 没有写权限")
    
    # Check memory directory
    memory_dir = settings.resolve(settings.memory_dir)
    if not memory_dir.exists():
        warnings.append(f"记忆目录 {memory_dir} 不存在，将自动创建")
    elif not os.access(memory_dir, os.W_OK):
        errors.append(f"记忆目录 {memory_dir} 没有写权限")
    
    # Check skills directory
    skills_dir = settings.resolve(settings.skills_dir)
    if not skills_dir.exists():
        warnings.append(f"Skills 目录 {skills_dir} 不存在")
    
    # Check RAGLab connection
    if settings.raglab_base_url:
        try:
            import httpx
            response = httpx.get(f"{settings.raglab_base_url}/health", timeout=5.0)
            if response.status_code != 200:
                warnings.append(f"RAGLab 服务返回非 200 状态: {response.status_code}")
        except Exception as e:
            warnings.append(f"无法连接到 RAGLab 服务: {e}")
    
    # Check Ollama connection if configured
    if settings.ollama_base_url:
        try:
            import httpx
            response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5.0)
            if response.status_code != 200:
                warnings.append(f"Ollama 服务返回非 200 状态: {response.status_code}")
        except Exception as e:
            warnings.append(f"无法连接到 Ollama 服务: {e}")
    
    # Check admin token
    if not settings.admin_token:
        warnings.append("ADMIN_TOKEN 未设置，管理端点将无保护")
    
    # Check sandbox configuration
    if settings.daytona_enabled and not settings.daytona_api_key:
        warnings.append("Daytona 已启用但 DAYTONA_API_KEY 未设置")
    
    # Check file sizes and limits
    if settings.max_file_size < 1024 * 1024:  # Less than 1MB
        warnings.append(f"max_file_size 设置过小: {settings.max_file_size} bytes")
    
    if settings.max_workspace_size < 10 * 1024 * 1024:  # Less than 10MB
        warnings.append(f"max_workspace_size 设置过小: {settings.max_workspace_size} bytes")
    
    # Log results
    if errors:
        for error in errors:
            logger.error(f"配置错误: {error}")
    
    if warnings:
        for warning in warnings:
            logger.warning(f"配置警告: {warning}")
    
    for msg in info:
        logger.info(f"配置信息: {msg}")
    
    # Raise if critical errors
    if errors:
        raise ConfigurationError(
            f"发现 {len(errors)} 个配置错误:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    
    return {
        "valid": True,
        "errors": errors,
        "warnings": warnings,
        "info": info,
    }


def check_required_files() -> dict[str, bool]:
    """Check if required files exist."""
    settings = get_settings()
    
    required = {
        "system_prompt": settings.resolve("memory/org.md"),
        "workspace": settings.resolve(settings.workspace_dir),
    }
    
    return {name: path.exists() for name, path in required.items()}


def get_configuration_summary() -> dict[str, Any]:
    """Get a summary of current configuration."""
    settings = get_settings()
    
    return {
        "llm": {
            "provider": "deepseek" if settings.deepseek_api_key else "none",
            "model": settings.llm_model,
            "ollama_available": bool(settings.ollama_base_url),
        },
        "rag": {
            "raglab_url": settings.raglab_base_url,
            "knowledge_base": settings.raglab_kb,
        },
        "storage": {
            "database": str(settings.database_url),
            "workspace": str(settings.workspace_dir),
            "memory": str(settings.memory_dir),
        },
        "features": {
            "sandbox_enabled": settings.daytona_enabled,
            "mcp_enabled": settings.mcp_enabled,
            "skills_enabled": True,
        },
        "limits": {
            "max_file_size": settings.max_file_size,
            "max_workspace_size": settings.max_workspace_size,
            "rate_limit": settings.rate_limit_per_minute,
        },
    }
