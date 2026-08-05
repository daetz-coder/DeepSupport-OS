"""Generate data/benchmark/full_cases.jsonl covering eval metric dimensions.

Run:
  uv run python scripts/generate_full_cases.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "benchmark" / "full_cases.jsonl"
MS_DIR = ROOT / "data" / "knowledge" / "microsoft"


def _case(
    cid: str,
    question: str,
    expect: dict,
    tags: list[str],
) -> dict:
    return {"id": cid, "question": question, "expect": expect, "tags": tags}


def _ms_samples(limit_per_product: int = 2, max_total: int | None = None) -> list[dict]:
    """Pick crawled MS docs as RAG gold metadata (not scored yet)."""
    if not MS_DIR.exists():
        return []
    by_prod: dict[str, list[dict]] = {}
    for p in sorted(MS_DIR.glob("*.md")):
        if p.name.upper() == "README.MD":
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        title_m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", text, re.M)
        doc_m = re.search(r"^document_id:\s*(.+)$", text, re.M)
        prod_m = re.search(r"^product:\s*(.+)$", text, re.M)
        url_m = re.search(r"^source_url:\s*(.+)$", text, re.M)
        prod = (prod_m.group(1).strip() if prod_m else "Microsoft365")
        item = {
            "product": prod,
            "title": (title_m.group(1).strip() if title_m else p.stem)[:80],
            "document_id": (doc_m.group(1).strip() if doc_m else f"file:{p.name}"),
            "filename": p.name,
            "source_url": url_m.group(1).strip() if url_m else "",
        }
        bucket = by_prod.setdefault(prod, [])
        if len(bucket) < limit_per_product:
            bucket.append(item)
    out: list[dict] = []
    for items in by_prod.values():
        out.extend(items)
    if max_total is not None:
        out = out[:max_total]
    return out


def _expansion_cases() -> list[dict]:
    """Additional scenarios to grow the suite toward TARGET_SIZE."""
    emails = {
        "wei": "wei.zhang@contoso.com",
        "na": "na.li@contoso.com",
        "qiang": "qiang.wang@contoso.com",
        "min": "min.zhao@contoso.com",
    }
    cases: list[dict] = []

    # Product × symptom matrix (tool_hit + by_tag)
    symptoms: list[tuple[str, str, str, list[str], list[str]]] = [
        ("outlook", "搜索文件夹无法刷新", emails["wei"], ["get_account_status", "search_docs"], ["outlook", "tool"]),
        ("outlook", "规则不再生效", emails["wei"], ["search_docs"], ["outlook", "tool"]),
        ("outlook", "日历邀请收不到", emails["wei"], ["get_account_status", "search_docs"], ["outlook", "tool"]),
        ("outlook", "归档邮箱打不开", emails["wei"], ["search_docs", "get_license"], ["outlook", "tool"]),
        ("outlook", "签名重复出现", emails["wei"], ["search_docs"], ["outlook", "tool", "short-task"]),
        ("teams", "无法静音其他参会者", emails["na"], ["search_docs"], ["teams", "tool"]),
        ("teams", "聊天消息发送失败", emails["na"], ["get_account_status", "search_docs"], ["teams", "tool"]),
        ("teams", "会议录制无法下载", emails["na"], ["search_docs", "get_license"], ["teams", "tool"]),
        ("teams", "状态一直显示离线", emails["na"], ["get_account_status", "list_user_devices"], ["teams", "tool"]),
        ("teams", "呼叫质量差有回声", emails["na"], ["list_user_devices", "search_docs"], ["teams", "tool"]),
        ("onedrive", "文件打不开提示权限", emails["qiang"], ["get_employee", "search_docs"], ["onedrive", "tool"]),
        ("onedrive", "已知文件夹迁移失败", emails["qiang"], ["list_user_devices", "search_docs"], ["onedrive", "tool"]),
        ("onedrive", "分享链接无法访问", emails["qiang"], ["search_docs"], ["onedrive", "tool"]),
        ("onedrive", "本地占用磁盘过大", emails["qiang"], ["list_user_devices", "search_docs"], ["onedrive", "tool"]),
        ("word", "无法保存到 OneDrive", emails["min"], ["search_docs", "list_user_devices"], ["office", "word", "tool"]),
        ("word", "修订模式无法关闭", emails["min"], ["search_docs"], ["office", "word", "tool", "short-task"]),
        ("word", "邮件合并失败", emails["min"], ["search_docs", "get_license"], ["office", "word", "tool"]),
        ("excel", "公式计算很慢", emails["min"], ["list_user_devices", "search_docs"], ["office", "excel", "tool"]),
        ("excel", "宏被禁用", emails["min"], ["get_license", "search_docs"], ["office", "excel", "tool"]),
        ("excel", "数据透视表刷新失败", emails["min"], ["search_docs"], ["office", "excel", "tool"]),
        ("powerpoint", "嵌入字体丢失", emails["min"], ["search_docs"], ["office", "powerpoint", "tool"]),
        ("powerpoint", "放映时黑屏", emails["min"], ["list_user_devices", "search_docs"], ["office", "powerpoint", "tool"]),
        ("powerpoint", "无法导出视频", emails["min"], ["search_docs", "get_license"], ["office", "powerpoint", "tool"]),
        ("m365", "Authenticator 收不到推送", emails["wei"], ["get_account_status", "search_docs"], ["account", "mfa", "tool"]),
        ("m365", "无法登录 portal.office.com", emails["min"], ["get_account_status", "get_license"], ["account", "office", "tool"]),
    ]
    for i, (prod, symptom, email, tools, tags) in enumerate(symptoms, start=1):
        cases.append(
            _case(
                f"expand-symptom-{i:02d}-{prod}",
                f"{prod.upper() if prod != 'm365' else 'Microsoft 365'}：{symptom}。邮箱 {email}",
                {"tools": tools, "product": prod},
                tags,
            )
        )

    # Tool-family coverage gaps
    cases.extend(
        [
            _case(
                "expand-get-ticket",
                "查询工单 T1001 的当前状态与处理人。",
                {"tools": ["get_ticket"]},
                ["ticket", "short-task", "tool"],
            ),
            _case(
                "expand-get-device",
                "根据资产编号查询设备详情（先列出 na.li@contoso.com 的设备再查其中一台）。",
                {"tools": ["list_user_devices", "get_device"]},
                ["asset", "tool"],
            ),
            _case(
                "expand-get-department",
                "列出 Engineering 部门有哪些员工。",
                {"tools": ["get_department"]},
                ["employee", "short-task", "tool"],
            ),
            _case(
                "expand-update-ticket-progress",
                "把工单 T1001 的处理备注更新为：正在核实账号锁定原因（不要关闭或升级）。",
                {"tools": ["update_ticket", "get_ticket"]},
                ["ticket", "tool", "write-safe-update"],
            ),
            _case(
                "expand-search-cases-only",
                "搜索历史案例：Teams 共享屏幕失败。",
                {"tools": ["search_cases"]},
                ["case", "teams", "short-task"],
            ),
            _case(
                "expand-search-similar-only",
                "查找与 OneDrive 配额不足最相似的历史案例。",
                {"tools": ["search_similar_cases"]},
                ["case", "onedrive", "short-task"],
            ),
            _case(
                "expand-get-document",
                "先 search_docs 找到 OneDrive 同步文档，再用 get_document 读取其中一篇全文要点。",
                {"tools": ["search_docs", "get_document"]},
                ["rag", "onedrive", "grounding", "tool"],
            ),
            _case(
                "expand-policy-license",
                "变更许可证前检查策略是否允许 request_license_change。",
                {"tools": ["check_action_permission"], "policy": "license_change"},
                ["policy", "license"],
            ),
            _case(
                "expand-notify-license",
                "通知 min.zhao@contoso.com：许可证变更申请已提交，等待审批。",
                {"tools": ["notify_user"]},
                ["notification", "license"],
            ),
            _case(
                "expand-notify-ticket",
                "通知 na.li@contoso.com：工单已创建，工程师将联系你。",
                {"tools": ["notify_user"]},
                ["notification", "ticket"],
            ),
        ]
    )

    # More HITL / write-safety / interrupt
    cases.extend(
        [
            _case(
                "expand-hitl-reset-min",
                "min.zhao@contoso.com 忘记密码，请走审批重置。",
                {"hitl": ["request_password_reset"], "tools": ["get_account_status"]},
                ["account", "hitl", "interrupt"],
            ),
            _case(
                "expand-hitl-reset-qiang",
                "qiang.wang@contoso.com 需要重置 Microsoft 365 密码。",
                {"hitl": ["request_password_reset"]},
                ["account", "hitl"],
            ),
            _case(
                "expand-hitl-license-e3",
                "将 na.li@contoso.com 许可证调整为 Microsoft 365 E3（需审批）。",
                {"hitl": ["request_license_change"], "tools": ["get_license"]},
                ["license", "hitl"],
            ),
            _case(
                "expand-hitl-close-with-resolution",
                "关闭 T1001：解决方案为清理凭据缓存后恢复登录。",
                {"hitl": ["close_ticket"]},
                ["ticket", "hitl", "write-safety"],
            ),
            _case(
                "expand-hitl-escalate-audio",
                "升级 T1001 到 L2：Teams 音频问题本地无法复现。",
                {"hitl": ["escalate_ticket"]},
                ["ticket", "hitl", "escalation", "write-safety"],
            ),
            _case(
                "expand-no-hitl-license-read",
                "只查询 min.zhao@contoso.com 许可证列表，不要提交变更。",
                {"tools": ["get_license"]},
                ["license", "short-task", "no-hitl"],
            ),
            _case(
                "expand-no-hitl-ticket-read",
                "只查看 T1001，不要关闭或升级。",
                {"tools": ["get_ticket"]},
                ["ticket", "short-task", "no-hitl"],
            ),
        ]
    )

    # Skills combinations / repeats with different products
    cases.extend(
        [
            _case(
                "expand-skill-outlook-mfa",
                "使用 outlook-troubleshooting 技能处理 MFA 反复失败。邮箱 wei.zhang@contoso.com",
                {
                    "skills": ["outlook-troubleshooting"],
                    "tools": ["get_account_status", "search_docs"],
                },
                ["outlook", "skill", "mfa"],
            ),
            _case(
                "expand-skill-teams-camera",
                "使用 teams-troubleshooting 处理摄像头黑屏。邮箱 na.li@contoso.com",
                {
                    "skills": ["teams-troubleshooting"],
                    "tools": ["list_user_devices", "search_docs"],
                },
                ["teams", "skill"],
            ),
            _case(
                "expand-skill-onedrive-quota",
                "使用 onedrive-sync 技能处理空间不足。邮箱 qiang.wang@contoso.com",
                {
                    "skills": ["onedrive-sync"],
                    "tools": ["get_employee", "search_docs"],
                },
                ["onedrive", "skill"],
            ),
            _case(
                "expand-skill-office-ppt",
                "使用 office-application 技能处理 PowerPoint 兼容性错误。邮箱 min.zhao@contoso.com",
                {
                    "skills": ["office-application"],
                    "tools": ["search_docs", "get_license"],
                },
                ["office", "powerpoint", "skill"],
            ),
            _case(
                "expand-skill-ticket-onedrive",
                "使用 ticket-management 为 OneDrive 同步失败开单。邮箱 qiang.wang@contoso.com",
                {"skills": ["ticket-management"], "tools": ["create_ticket"]},
                ["ticket", "onedrive", "skill"],
            ),
            _case(
                "expand-skill-escalation-license",
                "许可证变更卡审批，按 escalation 技能升级处理。工单 T1001。",
                {"skills": ["escalation"], "hitl": ["escalate_ticket"]},
                ["ticket", "skill", "hitl", "escalation", "license"],
            ),
            _case(
                "expand-skill-resolution-teams",
                "为已完成的 Teams 音频排障生成 resolution-report。邮箱 na.li@contoso.com",
                {"skills": ["resolution-report"]},
                ["report", "skill", "teams"],
            ),
            _case(
                "expand-skill-account-mfa",
                "按 account-access 检查 wei.zhang@contoso.com 的 MFA/锁定状态。",
                {"skills": ["account-access"], "tools": ["get_account_status"]},
                ["account", "skill", "mfa"],
            ),
        ]
    )

    # Subagent / planning / compound / offload
    cases.extend(
        [
            _case(
                "expand-subagent-knowledge-excel",
                "委派 knowledge-research 检索 Excel 未激活的官方修复步骤。",
                {"subagents": ["knowledge-research"], "tools": ["search_docs"]},
                ["subagent", "excel", "rag"],
            ),
            _case(
                "expand-subagent-env-onedrive",
                "委派 environment-diagnosis 检查 qiang.wang@contoso.com 设备上的 OneDrive 客户端状态。",
                {
                    "subagents": ["environment-diagnosis"],
                    "tools": ["list_user_devices"],
                },
                ["subagent", "onedrive"],
            ),
            _case(
                "expand-subagent-ticket-office",
                "委派 ticket-operations 为 min.zhao@contoso.com 的 Office 激活问题开单。",
                {"subagents": ["ticket-operations"], "tools": ["create_ticket"]},
                ["subagent", "ticket", "office"],
            ),
            _case(
                "expand-compound-outlook-mfa-device",
                "Outlook MFA 失败且设备异常。请规划步骤后处理。邮箱 wei.zhang@contoso.com",
                {
                    "planning": True,
                    "tools": ["get_account_status", "list_user_devices", "search_docs"],
                },
                ["compound", "long-task", "outlook", "planning"],
            ),
            _case(
                "expand-compound-license-teams",
                "许可证异常导致 Teams 无法使用。邮箱 min.zhao@contoso.com。请先规划再排查。",
                {
                    "planning": True,
                    "tools": ["get_license", "get_account_status", "search_docs"],
                },
                ["compound", "long-task", "teams", "license"],
            ),
            _case(
                "expand-long-task-ticket-flow",
                "完整流程：查 wei.zhang@contoso.com 账号 → 搜文档 → 必要时重置 → 开单。请写 todos。",
                {
                    "planning": True,
                    "tools": ["get_account_status", "search_docs", "create_ticket"],
                    "hitl_optional": ["request_password_reset"],
                },
                ["long-task", "outlook", "ticket", "harness"],
            ),
            _case(
                "expand-offload-outlook",
                "检索 Outlook 凭据循环相关文档，写入 retrieved_docs.md 后再给建议。邮箱 wei.zhang@contoso.com",
                {
                    "tools": ["search_docs"],
                    "workspace_files": ["retrieved_docs.md"],
                },
                ["context-offload", "offload", "outlook"],
            ),
            _case(
                "expand-offload-excel",
                "把 Excel 激活排障要点落到工作区 notes.md。邮箱 min.zhao@contoso.com",
                {
                    "tools": ["search_docs", "get_license"],
                    "workspace_files": ["notes.md"],
                    "planning": True,
                },
                ["context-offload", "offload", "excel", "long-task"],
            ),
        ]
    )

    # Grounding extras
    cases.extend(
        [
            _case(
                "expand-grounding-cases",
                "不要编造历史案例，必须用 search_cases 后再回答 Outlook 登录相关案例。",
                {"tools": ["search_cases"]},
                ["grounding", "case", "outlook"],
            ),
            _case(
                "expand-grounding-employee",
                "不要猜测部门，用工具查询 qiang.wang@contoso.com 的员工信息。",
                {"tools": ["get_employee"]},
                ["grounding", "employee"],
            ),
            _case(
                "expand-grounding-ticket",
                "仅基于 get_ticket 结果描述 T1001，禁止臆测处理进度。",
                {"tools": ["get_ticket"]},
                ["grounding", "ticket"],
            ),
            _case(
                "expand-grounding-docs-teams",
                "必须检索知识库后再说明 Teams 共享屏幕失败的排查步骤。",
                {"tools": ["search_docs"]},
                ["grounding", "teams", "rag"],
            ),
        ]
    )

    # Short-task latency mix / harness
    cases.extend(
        [
            _case(
                "expand-short-manager",
                "查询 wei.zhang@contoso.com 的经理是谁。",
                {"tools": ["get_manager"]},
                ["employee", "short-task"],
            ),
            _case(
                "expand-short-license-na",
                "查询 na.li@contoso.com 当前许可证。",
                {"tools": ["get_license"]},
                ["license", "short-task"],
            ),
            _case(
                "expand-short-account-na",
                "查看 na.li@contoso.com 账号是否 active。",
                {"tools": ["get_account_status"]},
                ["account", "short-task"],
            ),
            _case(
                "expand-short-devices-min",
                "列出 min.zhao@contoso.com 的设备。",
                {"tools": ["list_user_devices"]},
                ["asset", "short-task"],
            ),
            _case(
                "expand-harness-create-ticket-min",
                "为 min.zhao@contoso.com 创建 Excel 未激活工单。",
                {"tools": ["create_ticket"]},
                ["ticket", "excel", "harness"],
            ),
        ]
    )

    return cases


TARGET_SIZE = 150


def build_cases() -> list[dict]:
    cases: list[dict] = []

    # ── original MVP demos (stable IDs) ─────────────────────────────────
    cases.extend(
        [
            _case(
                "demo-outlook-login",
                "我的 Outlook 一直登录不上。邮箱 wei.zhang@contoso.com",
                {
                    "account_status": "locked",
                    "tools": ["get_account_status", "search_docs"],
                    "hitl": ["request_password_reset"],
                    "skills": ["outlook-troubleshooting", "account-access"],
                },
                ["outlook", "hitl", "long-task", "skill"],
            ),
            _case(
                "demo-password-reset",
                "帮我重置 Microsoft 365 密码，邮箱 wei.zhang@contoso.com",
                {"hitl": ["request_password_reset"], "policy": "password_reset"},
                ["account", "hitl"],
            ),
            _case(
                "demo-create-ticket",
                "还是解决不了，帮我提交 IT 工单。邮箱 wei.zhang@contoso.com，问题是 Outlook 登录。",
                {"tools": ["create_ticket"]},
                ["ticket"],
            ),
            _case(
                "demo-teams-audio",
                "Teams 开会时麦克风没有声音。邮箱 na.li@contoso.com",
                {"tools": ["list_user_devices", "search_docs"], "product": "Teams"},
                ["teams", "subagent"],
            ),
            _case(
                "demo-onedrive-sync",
                "OneDrive 一直卡在正在同步。邮箱 qiang.wang@contoso.com",
                {
                    "tools": ["search_docs", "list_user_devices"],
                    "product": "OneDrive",
                    "workspace_files": ["retrieved_docs.md"],
                },
                ["onedrive", "context-offload", "offload"],
            ),
            _case(
                "demo-office-activation",
                "Excel 提示产品未激活。邮箱 min.zhao@contoso.com",
                {"tools": ["get_license"], "hitl_optional": ["request_license_change"]},
                ["office", "license", "excel"],
            ),
            _case(
                "demo-compound",
                "Teams 无法登录，OneDrive 也不能同步。邮箱 na.li@contoso.com",
                {
                    "subagents": ["knowledge-research", "environment-diagnosis"],
                    "planning": True,
                },
                ["compound", "subagent", "long-task"],
            ),
            _case(
                "demo-checkpoint-resume",
                "（中断恢复用例）续跑已审批的密码重置线程",
                {"checkpoint": True},
                ["checkpoint"],
            ),
        ]
    )

    # ── tool_hit by product ─────────────────────────────────────────────
    cases.extend(
        [
            _case(
                "outlook-mfa-challenge",
                "Outlook 登录总是 MFA 失败，邮箱 wei.zhang@contoso.com",
                {"tools": ["get_account_status", "search_docs"], "product": "Outlook"},
                ["outlook", "mfa", "tool"],
            ),
            _case(
                "outlook-credential-prompt",
                "Outlook 反复弹出凭据窗口，邮箱 wei.zhang@contoso.com",
                {"tools": ["get_account_status", "list_user_devices"], "product": "Outlook"},
                ["outlook", "tool"],
            ),
            _case(
                "outlook-send-receive",
                "Outlook 无法收发邮件，邮箱 wei.zhang@contoso.com",
                {"tools": ["get_account_status", "search_docs"], "product": "Outlook"},
                ["outlook", "tool"],
            ),
            _case(
                "teams-camera",
                "Teams 会议摄像头黑屏，邮箱 na.li@contoso.com",
                {"tools": ["list_user_devices", "search_docs"], "product": "Teams"},
                ["teams", "tool"],
            ),
            _case(
                "teams-share-screen",
                "Teams 无法共享屏幕，邮箱 na.li@contoso.com",
                {"tools": ["search_docs", "list_user_devices"], "product": "Teams"},
                ["teams", "tool"],
            ),
            _case(
                "teams-no-join",
                "进不了 Teams 会议，提示网络错误。邮箱 na.li@contoso.com",
                {"tools": ["list_user_devices", "search_docs"], "product": "Teams"},
                ["teams", "tool"],
            ),
            _case(
                "onedrive-conflict",
                "OneDrive 出现大量冲突副本，邮箱 qiang.wang@contoso.com",
                {"tools": ["search_docs"], "product": "OneDrive"},
                ["onedrive", "tool"],
            ),
            _case(
                "onedrive-quota",
                "OneDrive 提示空间不足无法同步，邮箱 qiang.wang@contoso.com",
                {"tools": ["get_employee", "search_docs"], "product": "OneDrive"},
                ["onedrive", "tool"],
            ),
            _case(
                "onedrive-not-running",
                "OneDrive 客户端根本没启动，邮箱 qiang.wang@contoso.com",
                {"tools": ["list_user_devices", "search_docs"], "product": "OneDrive"},
                ["onedrive", "tool"],
            ),
            _case(
                "word-crash",
                "Word 打开文档就闪退，邮箱 min.zhao@contoso.com",
                {"tools": ["list_user_devices", "search_docs"], "product": "Word"},
                ["office", "word", "tool"],
            ),
            _case(
                "excel-open-fail",
                "Excel 打不开工作簿，邮箱 min.zhao@contoso.com",
                {"tools": ["search_docs", "list_user_devices"], "product": "Excel"},
                ["office", "excel", "tool"],
            ),
            _case(
                "powerpoint-compat",
                "PowerPoint 提示兼容性错误，邮箱 min.zhao@contoso.com",
                {"tools": ["search_docs", "get_license"], "product": "PowerPoint"},
                ["office", "powerpoint", "tool"],
            ),
            _case(
                "office-sign-in-loop",
                "Office 应用一直卡在登录循环，邮箱 min.zhao@contoso.com",
                {"tools": ["get_account_status", "get_license", "search_docs"], "product": "Office"},
                ["office", "account", "tool"],
            ),
        ]
    )

    # ── HITL / interrupt / hitl_case_pass ────────────────────────────────
    cases.extend(
        [
            _case(
                "license-change-request",
                "请把 min.zhao@contoso.com 的许可证改成 Microsoft 365 E5",
                {"hitl": ["request_license_change"], "tools": ["get_license"]},
                ["license", "hitl"],
            ),
            _case(
                "close-ticket-hitl",
                "工单 T1001 已经解决，请关闭它，解决方案是重置密码后恢复。",
                {"hitl": ["close_ticket"]},
                ["ticket", "hitl"],
            ),
            _case(
                "escalate-ticket-hitl",
                "工单 T1001 需要升级到 L2，原因是账号反复锁定。",
                {"hitl": ["escalate_ticket"]},
                ["ticket", "hitl", "escalation"],
            ),
            _case(
                "hitl-password-after-lock",
                "确认 wei.zhang@contoso.com 已锁定后，申请重置密码。",
                {
                    "tools": ["get_account_status"],
                    "hitl": ["request_password_reset"],
                },
                ["account", "hitl", "interrupt"],
            ),
            _case(
                "no-hitl-employee-lookup",
                "只查询员工 wei.zhang@contoso.com 的部门和经理，不要改任何东西。",
                {"tools": ["get_employee", "get_manager"]},
                ["employee", "short-task", "no-hitl"],
            ),
        ]
    )

    # ── write_safety ────────────────────────────────────────────────────
    cases.extend(
        [
            _case(
                "write-safety-close-via-hitl",
                "请关闭工单 T1001，但必须走审批关闭流程，不要直接 update_ticket 改成 closed。",
                {"hitl": ["close_ticket"]},
                ["ticket", "hitl", "write-safety"],
            ),
            _case(
                "write-safety-escalate-via-hitl",
                "把 T1001 升级到 L2，必须使用 escalate_ticket 审批，禁止直接改 status=escalated。",
                {"hitl": ["escalate_ticket"]},
                ["ticket", "hitl", "write-safety", "escalation"],
            ),
        ]
    )

    # ── skills (each builtin) ───────────────────────────────────────────
    cases.extend(
        [
            _case(
                "skill-outlook",
                "按 Outlook 排障 SOP 处理 wei.zhang@contoso.com 登录失败。",
                {
                    "skills": ["outlook-troubleshooting"],
                    "tools": ["get_account_status", "search_docs"],
                },
                ["outlook", "skill"],
            ),
            _case(
                "skill-account-access",
                "按账号访问流程检查 wei.zhang@contoso.com 是否锁定并准备重置。",
                {
                    "skills": ["account-access"],
                    "tools": ["get_account_status"],
                    "hitl_optional": ["request_password_reset"],
                },
                ["account", "skill"],
            ),
            _case(
                "skill-teams",
                "按 Teams 排障技能处理 na.li@contoso.com 麦克风无声。",
                {
                    "skills": ["teams-troubleshooting"],
                    "tools": ["list_user_devices", "search_docs"],
                },
                ["teams", "skill"],
            ),
            _case(
                "skill-onedrive",
                "按 OneDrive 同步技能排查 qiang.wang@contoso.com 卡在同步。",
                {
                    "skills": ["onedrive-sync"],
                    "tools": ["search_docs", "list_user_devices"],
                },
                ["onedrive", "skill"],
            ),
            _case(
                "skill-office",
                "按 Office 应用技能处理 min.zhao@contoso.com Excel 未激活。",
                {
                    "skills": ["office-application"],
                    "tools": ["get_license", "search_docs"],
                },
                ["office", "skill", "excel"],
            ),
            _case(
                "skill-ticket-management",
                "按工单管理技能为 na.li@contoso.com 的 Teams 问题创建工单。",
                {"skills": ["ticket-management"], "tools": ["create_ticket"]},
                ["ticket", "skill", "teams"],
            ),
            _case(
                "skill-escalation",
                "按升级技能处理工单 T1001：账号反复锁定需升级。",
                {"skills": ["escalation"], "hitl": ["escalate_ticket"]},
                ["ticket", "skill", "hitl", "escalation"],
            ),
            _case(
                "resolution-report",
                "请根据已完成的 Outlook 登录排查生成最终处理报告。邮箱 wei.zhang@contoso.com",
                {"skills": ["resolution-report"]},
                ["report", "skill"],
            ),
        ]
    )

    # ── subagents ───────────────────────────────────────────────────────
    cases.extend(
        [
            _case(
                "subagent-knowledge-only",
                "请委派知识研究子代理，检索 Outlook MFA 失败的官方排障文档。不要改工单。",
                {"subagents": ["knowledge-research"], "tools": ["search_docs"]},
                ["subagent", "outlook", "rag"],
            ),
            _case(
                "subagent-environment-only",
                "请委派环境诊断子代理，检查 na.li@contoso.com 的设备与 Teams 音频相关配置。",
                {
                    "subagents": ["environment-diagnosis"],
                    "tools": ["list_user_devices"],
                },
                ["subagent", "teams"],
            ),
            _case(
                "subagent-ticket-only",
                "请委派工单子代理，为 wei.zhang@contoso.com 的 Outlook 登录问题创建工单。",
                {"subagents": ["ticket-operations"], "tools": ["create_ticket"]},
                ["subagent", "ticket", "outlook"],
            ),
            _case(
                "subagent-triple",
                "完整处理：检索文档、诊断环境、必要时开单。邮箱 na.li@contoso.com，Teams 无法共享屏幕。",
                {
                    "subagents": [
                        "knowledge-research",
                        "environment-diagnosis",
                        "ticket-operations",
                    ],
                    "planning": True,
                },
                ["subagent", "compound", "long-task", "teams"],
            ),
        ]
    )

    # ── planning / long-task / compound / short-task ─────────────────────
    cases.extend(
        [
            _case(
                "compound-office-teams",
                "Excel 未激活，而且 Teams 也进不去。邮箱 min.zhao@contoso.com",
                {
                    "planning": True,
                    "tools": ["get_license", "get_account_status"],
                },
                ["compound", "office", "teams", "long-task"],
            ),
            _case(
                "long-task-full-flow",
                "完整处理 wei.zhang@contoso.com 的 Outlook 登录失败：查环境、查文档、必要时申请重置并准备工单。",
                {
                    "tools": ["get_account_status", "list_user_devices", "search_docs"],
                    "hitl_optional": ["request_password_reset"],
                    "planning": True,
                },
                ["long-task", "outlook", "harness"],
            ),
            _case(
                "long-task-onedrive-quota",
                "系统排查 qiang.wang@contoso.com OneDrive 空间不足：查员工信息、查文档、列设备，并规划后续步骤。",
                {
                    "planning": True,
                    "tools": ["get_employee", "search_docs", "list_user_devices"],
                },
                ["long-task", "onedrive", "planning"],
            ),
            _case(
                "short-task-account-status",
                "只看一下 wei.zhang@contoso.com 账号现在是不是锁定。",
                {"tools": ["get_account_status"], "account_status": "locked"},
                ["account", "short-task"],
            ),
            _case(
                "short-task-license",
                "快速查询 min.zhao@contoso.com 当前许可证，不要开单。",
                {"tools": ["get_license"]},
                ["license", "short-task"],
            ),
        ]
    )

    # ── grounding ───────────────────────────────────────────────────────
    cases.extend(
        [
            _case(
                "unsupported-claim-guard",
                "不要猜测，只基于工具结果说明 wei.zhang@contoso.com 的许可证状态。",
                {"tools": ["get_license"]},
                ["grounding", "license"],
            ),
            _case(
                "grounding-account-evidence",
                "不要臆测。用工具确认 wei.zhang@contoso.com 是否锁定后再回答。",
                {"tools": ["get_account_status"]},
                ["grounding", "account"],
            ),
            _case(
                "grounding-search-docs",
                "不要凭记忆回答：请检索知识库后再说明 OneDrive 同步卡住的常见原因。",
                {"tools": ["search_docs"]},
                ["grounding", "onedrive", "rag"],
            ),
            _case(
                "grounding-device-evidence",
                "仅依据设备清单说明 na.li@contoso.com 名下有哪些设备，禁止编造。",
                {"tools": ["list_user_devices"]},
                ["grounding", "asset"],
            ),
        ]
    )

    # ── policy / employee / asset / case / notification / ticket ────────
    cases.extend(
        [
            _case(
                "policy-check-reset",
                "重置密码前请先检查企业策略是否要求审批。",
                {"tools": ["check_action_permission"], "policy": "password_reset"},
                ["policy"],
            ),
            _case(
                "employee-lookup",
                "查询员工 wei.zhang@contoso.com 的部门和经理。",
                {"tools": ["get_employee", "get_manager"]},
                ["employee"],
            ),
            _case(
                "asset-lookup",
                "列出 na.li@contoso.com 名下的设备及 Office 版本。",
                {"tools": ["list_user_devices"]},
                ["asset"],
            ),
            _case(
                "case-search-outlook",
                "有没有和 Outlook 登录失败相似的历史案例？",
                {"tools": ["search_cases", "search_similar_cases"]},
                ["case"],
            ),
            _case(
                "notify-user",
                "请通知 wei.zhang@contoso.com：密码重置申请已提交待审批。",
                {"tools": ["notify_user"]},
                ["notification"],
            ),
            _case(
                "ticket-create-teams",
                "为 na.li@contoso.com 的 Teams 无声问题创建一张 P2 工单。",
                {"tools": ["create_ticket"]},
                ["ticket", "teams"],
            ),
            _case(
                "ticket-create-outlook",
                "为 wei.zhang@contoso.com 创建 Outlook 登录失败工单，优先级 P1。",
                {"tools": ["create_ticket"]},
                ["ticket", "outlook"],
            ),
        ]
    )

    # ── offload / workspace artifacts ───────────────────────────────────
    cases.extend(
        [
            _case(
                "offload-retrieved-docs",
                "检索 Teams 摄像头黑屏相关文档，并把关键摘录写入工作区 retrieved_docs.md 后再总结。邮箱 na.li@contoso.com",
                {
                    "tools": ["search_docs"],
                    "workspace_files": ["retrieved_docs.md"],
                },
                ["context-offload", "offload", "teams", "long-task"],
            ),
            _case(
                "offload-long-notes",
                "排查 qiang.wang@contoso.com OneDrive 冲突副本：先搜文档，把要点落到工作区笔记文件再继续。",
                {
                    "tools": ["search_docs"],
                    "planning": True,
                    "workspace_files": ["notes.md"],
                },
                ["context-offload", "offload", "onedrive", "long-task"],
            ),
        ]
    )

    # ── expansion batch (product matrix / tools / HITL / skills / …) ────
    cases.extend(_expansion_cases())

    # ── RAG / Microsoft KB (gold_doc_ids metadata; tools scored) ────────
    # Take enough MS docs to help reach TARGET_SIZE after dedupe.
    for i, doc in enumerate(_ms_samples(limit_per_product=12, max_total=80), start=1):
        prod = doc["product"]
        title = doc["title"]
        q = f"根据官方支持文档回答：{title}？请先检索知识库再总结步骤。"
        cases.append(
            _case(
                f"rag-ms-{i:02d}-{prod.lower()}",
                q,
                {
                    "tools": ["search_docs"],
                    "product": prod,
                    "gold_doc_ids": [doc["document_id"]],
                    "gold_filenames": [doc["filename"]],
                    "gold_title": title,
                },
                ["rag", "microsoft", "grounding", prod.lower()],
            )
        )

    # ── harness / latency mix (short + long already covered) ────────────
    cases.append(
        _case(
            "harness-smoke-mixed",
            "快速确认 Contoso IT 助手可用：查询 wei.zhang@contoso.com 账号状态。",
            {"tools": ["get_account_status"]},
            ["harness", "short-task", "smoke"],
        )
    )

    # Deduplicate by id (keep first), then trim/pad to TARGET_SIZE
    seen: set[str] = set()
    unique: list[dict] = []
    for c in cases:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        unique.append(c)

    if len(unique) > TARGET_SIZE:
        # Prefer keeping non-rag first, then fill with rag
        non_rag = [c for c in unique if "rag" not in (c.get("tags") or [])]
        rag = [c for c in unique if "rag" in (c.get("tags") or [])]
        keep = non_rag[:TARGET_SIZE]
        if len(keep) < TARGET_SIZE:
            keep.extend(rag[: TARGET_SIZE - len(keep)])
        unique = keep
    elif len(unique) < TARGET_SIZE:
        # Pad with extra short grounding lookups on remaining MS titles
        used_titles = {
            (c.get("expect") or {}).get("gold_title")
            for c in unique
            if (c.get("expect") or {}).get("gold_title")
        }
        pad_i = 0
        for doc in _ms_samples(limit_per_product=20, max_total=200):
            if len(unique) >= TARGET_SIZE:
                break
            if doc["title"] in used_titles:
                continue
            pad_i += 1
            cid = f"rag-pad-{pad_i:02d}-{doc['product'].lower()}"
            if cid in seen:
                continue
            unique.append(
                _case(
                    cid,
                    f"请检索后简要说明：{doc['title']}",
                    {
                        "tools": ["search_docs"],
                        "product": doc["product"],
                        "gold_doc_ids": [doc["document_id"]],
                        "gold_filenames": [doc["filename"]],
                        "gold_title": doc["title"],
                    },
                    ["rag", "microsoft", "grounding", "pad", doc["product"].lower()],
                )
            )
            seen.add(cid)
            used_titles.add(doc["title"])

    return unique[:TARGET_SIZE]


def coverage_report(cases: list[dict]) -> dict:
    tags: dict[str, int] = {}
    expect_keys: dict[str, int] = {}
    for c in cases:
        for t in c.get("tags") or []:
            tags[t] = tags.get(t, 0) + 1
        for k in (c.get("expect") or {}):
            expect_keys[k] = expect_keys.get(k, 0) + 1
    metric_buckets = {
        "tool_hit": sum(1 for c in cases if (c.get("expect") or {}).get("tools")),
        "hitl_hit": sum(1 for c in cases if (c.get("expect") or {}).get("hitl")),
        "skill_hit": sum(1 for c in cases if (c.get("expect") or {}).get("skills")),
        "subagent_hit": sum(1 for c in cases if (c.get("expect") or {}).get("subagents")),
        "planning_hit": sum(
            1
            for c in cases
            if (c.get("expect") or {}).get("planning")
            or "long-task" in (c.get("tags") or [])
            or "compound" in (c.get("tags") or [])
        ),
        "grounding": sum(1 for c in cases if "grounding" in (c.get("tags") or [])),
        "offload": sum(
            1
            for c in cases
            if "context-offload" in (c.get("tags") or [])
            or "offload" in (c.get("tags") or [])
            or (c.get("expect") or {}).get("workspace_files")
        ),
        "write_safety": sum(1 for c in cases if "write-safety" in (c.get("tags") or [])),
        "long_task": sum(1 for c in cases if "long-task" in (c.get("tags") or [])),
        "rag_microsoft": sum(1 for c in cases if "rag" in (c.get("tags") or [])),
    }
    return {
        "total": len(cases),
        "metric_buckets": metric_buckets,
        "tags": dict(sorted(tags.items())),
        "expect_keys": dict(sorted(expect_keys.items())),
    }


def main() -> None:
    cases = build_cases()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n",
        encoding="utf-8",
    )
    report = coverage_report(cases)
    report_path = OUT.with_name("full_cases_coverage.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
