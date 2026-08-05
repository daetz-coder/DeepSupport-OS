"""Deterministic Faker seed for mock enterprise IT data."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from faker import Faker
from sqlalchemy import select

from deepsupport_os.db.models import (
    Account,
    Asset,
    Case,
    Employee,
    License,
    Policy,
    Ticket,
    get_session_factory,
    init_db,
)

SEED = 20260804

DEPARTMENTS = [
    ("Engineering", "工程师"),
    ("Finance", "财务专员"),
    ("HR", "HRBP"),
    ("Sales", "销售经理"),
    ("IT", "IT 支持"),
]

PRODUCTS = ["Outlook", "Teams", "OneDrive", "Word", "Excel", "PowerPoint", "Microsoft 365"]

DEMO_EMPLOYEES = [
    {
        "employee_id": "E001",
        "name": "张伟",
        "email": "wei.zhang@contoso.com",
        "department": "Engineering",
        "role": "软件工程师",
        "manager_id": "E010",
        "status": "locked",
        "mfa_status": "enabled",
        "license_type": "Microsoft 365 E3",
        "device_type": "Windows Laptop",
        "os_version": "Windows 11 23H2",
        "office_version": "Microsoft 365 Apps 2406",
        "issue": "outlook_login",
    },
    {
        "employee_id": "E002",
        "name": "李娜",
        "email": "na.li@contoso.com",
        "department": "Sales",
        "role": "销售经理",
        "manager_id": "E010",
        "status": "active",
        "mfa_status": "enabled",
        "license_type": "Microsoft 365 E3",
        "device_type": "Windows Laptop",
        "os_version": "Windows 11 22H2",
        "office_version": "Microsoft 365 Apps 2402",
        "issue": "teams_audio",
    },
    {
        "employee_id": "E003",
        "name": "王强",
        "email": "qiang.wang@contoso.com",
        "department": "Finance",
        "role": "财务专员",
        "manager_id": "E010",
        "status": "active",
        "mfa_status": "disabled",
        "license_type": "Microsoft 365 E3",
        "device_type": "Windows Desktop",
        "os_version": "Windows 10 22H2",
        "office_version": "Office 2021",
        "issue": "onedrive_sync",
    },
    {
        "employee_id": "E004",
        "name": "赵敏",
        "email": "min.zhao@contoso.com",
        "department": "HR",
        "role": "HRBP",
        "manager_id": "E010",
        "status": "active",
        "mfa_status": "enabled",
        "license_type": "Microsoft 365 E3",
        "device_type": "Windows Laptop",
        "os_version": "Windows 11 23H2",
        "office_version": "Microsoft 365 Apps 2308",
        "issue": "office_activation",
    },
]


def seed_database(*, force: bool = False, extra_employees: int = 20) -> dict:
    init_db()
    Session = get_session_factory()
    fake = Faker("zh_CN")
    Faker.seed(SEED)
    fake.seed_instance(SEED)

    with Session() as session:
        existing = session.scalar(select(Employee).limit(1))
        if existing and not force:
            out = {"status": "skipped", "reason": "already seeded"}
            try:
                from deepsupport_os.db.eval_store import sync_eval_cases

                out["eval_cases"] = sync_eval_cases()
            except Exception as exc:  # noqa: BLE001
                out["eval_cases"] = {"error": str(exc)}
            return out

        if force:
            for model in (Ticket, Case, License, Account, Asset, Policy, Employee):
                session.execute(model.__table__.delete())
            session.commit()

        # Manager
        manager = Employee(
            employee_id="E010",
            name="陈总监",
            email="director.chen@contoso.com",
            department="IT",
            role="IT 总监",
            manager_id=None,
        )
        session.add(manager)

        for demo in DEMO_EMPLOYEES:
            emp = Employee(
                employee_id=demo["employee_id"],
                name=demo["name"],
                email=demo["email"],
                department=demo["department"],
                role=demo["role"],
                manager_id=demo["manager_id"],
            )
            session.add(emp)
            session.add(
                Asset(
                    asset_id=f"A{demo['employee_id'][1:]}",
                    employee_id=demo["employee_id"],
                    device_type=demo["device_type"],
                    os_version=demo["os_version"],
                    office_version=demo["office_version"],
                    hostname=f"PC-{demo['employee_id']}",
                )
            )
            acct = Account(
                account_id=f"ACC{demo['employee_id'][1:]}",
                employee_id=demo["employee_id"],
                email=demo["email"],
                status=demo["status"],
                mfa_status=demo["mfa_status"],
                license_type=demo["license_type"],
            )
            session.add(acct)
            license_status = "expired" if demo["issue"] == "office_activation" else "active"
            expire = (datetime.now(UTC) + timedelta(days=30 if license_status == "active" else -10)).date().isoformat()
            session.add(
                License(
                    license_id=f"LIC{demo['employee_id'][1:]}",
                    account_id=acct.account_id,
                    product="Microsoft 365 Apps for enterprise",
                    status=license_status,
                    expire_at=expire,
                )
            )

        # Extra random employees
        for i in range(extra_employees):
            eid = f"E1{i:02d}"
            dept, role = DEPARTMENTS[i % len(DEPARTMENTS)]
            email = f"user{i:02d}@contoso.com"
            session.add(
                Employee(
                    employee_id=eid,
                    name=fake.name(),
                    email=email,
                    department=dept,
                    role=role,
                    manager_id="E010",
                )
            )
            session.add(
                Asset(
                    asset_id=f"A1{i:02d}",
                    employee_id=eid,
                    device_type="Windows Laptop",
                    os_version="Windows 11 23H2",
                    office_version="Microsoft 365 Apps 2406",
                    hostname=f"PC-{eid}",
                )
            )
            session.add(
                Account(
                    account_id=f"ACC1{i:02d}",
                    employee_id=eid,
                    email=email,
                    status="active",
                    mfa_status="enabled",
                    license_type="Microsoft 365 E3",
                )
            )
            session.add(
                License(
                    license_id=f"LIC1{i:02d}",
                    account_id=f"ACC1{i:02d}",
                    product="Microsoft 365 Apps for enterprise",
                    status="active",
                    expire_at=(datetime.now(UTC) + timedelta(days=180)).date().isoformat(),
                )
            )

        policies = [
            ("password_reset", True, 4, "重置 Microsoft 365 密码需人工审批"),
            ("license_change", True, 8, "变更许可证需人工审批"),
            ("close_ticket", True, 24, "关闭工单需确认"),
            ("escalate_ticket", True, 2, "升级工单需审批"),
            ("read_employee", False, 1, "查询员工只读"),
            ("read_asset", False, 1, "查询资产只读"),
        ]
        for idx, (action, approval, sla, desc) in enumerate(policies, start=1):
            session.add(
                Policy(
                    policy_id=f"P{idx:03d}",
                    action=action,
                    approval_required=approval,
                    sla_hours=sla,
                    description=desc,
                )
            )

        cases = [
            (
                "C001",
                "Outlook 提示无法登录或密码错误",
                "账号被锁定或 MFA 挑战失败",
                "检查账号状态；必要时走审批重置密码；确认 MFA 设备可用",
                "Outlook",
                "login,mfa,lock",
            ),
            (
                "C002",
                "Teams 会议中对方听不到我的声音",
                "系统默认麦克风错误或权限未授予",
                "检查设备麦克风权限、Teams 设备设置与驱动",
                "Teams",
                "audio,microphone",
            ),
            (
                "C003",
                "OneDrive 一直显示正在同步",
                "客户端版本过旧或文件冲突",
                "更新 OneDrive 客户端，暂停后重置同步，处理冲突文件",
                "OneDrive",
                "sync",
            ),
            (
                "C004",
                "Excel 提示产品未激活",
                "许可证过期或未正确分配",
                "核对许可证状态，必要时申请许可证变更并重新登录激活",
                "Excel",
                "activation,license",
            ),
        ]
        for case_id, symptom, root, solution, product, tags in cases:
            session.add(
                Case(
                    case_id=case_id,
                    symptom=symptom,
                    root_cause=root,
                    solution=solution,
                    related_product=product,
                    tags=tags,
                )
            )

        session.add(
            Ticket(
                ticket_id="T1001",
                employee_id="E001",
                category="Account",
                priority="P2",
                status="open",
                assignee="IT Help Desk",
                title="Outlook 无法登录",
                description="用户反馈 Outlook 持续无法登录 Contoso 账号。",
                resolution=None,
            )
        )

        session.commit()
        result = {
            "status": "ok",
            "employees": 1 + len(DEMO_EMPLOYEES) + extra_employees,
            "demo_emails": [d["email"] for d in DEMO_EMPLOYEES],
            "seed": SEED,
        }
        try:
            from deepsupport_os.db.eval_store import sync_eval_cases

            result["eval_cases"] = sync_eval_cases()
        except Exception as exc:  # noqa: BLE001
            result["eval_cases"] = {"error": str(exc)}
        return result


def main() -> None:
    result = seed_database(force=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
