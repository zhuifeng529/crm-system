"""Seed default tenant, admin user, permissions, pipeline, and dictionaries."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.core.security import hash_password
from app.database import SessionLocal, engine
from app.models import (
    Department,
    Permission,
    Pipeline,
    PipelineStage,
    Role,
    RolePermission,
    SysDict,
    SysDictItem,
    Tenant,
    UserAccount,
    UserRole,
)

PERMISSIONS = [
    ("admin:*", "admin", "*", "超级管理员"),
    ("org:write", "org", "write", "组织写"),
    ("lead:read", "lead", "read", "线索读"),
    ("lead:write", "lead", "write", "线索写"),
    ("lead:import", "lead", "import", "线索导入"),
    ("lead:assign", "lead", "assign", "线索分配"),
    ("lead:claim", "lead", "claim", "线索认领"),
    ("account:write", "account", "write", "客户写"),
    ("account:claim", "account", "claim", "客户认领"),
    ("activity:write", "activity", "write", "跟进写"),
    ("opportunity:write", "opportunity", "write", "商机写"),
    ("pipeline:write", "pipeline", "write", "管道配置"),
    ("pool:write", "pool", "write", "公海配置"),
    ("pool:force_assign", "pool", "force_assign", "强制分配"),
    ("target:write", "target", "write", "目标写"),
    ("report:export", "report", "export", "报表导出"),
    ("dict:write", "dict", "write", "字典写"),
    ("field:write", "field", "write", "自定义字段"),
    ("layout:write", "layout", "write", "布局写"),
    ("approval:write", "approval", "write", "审批流写"),
    ("audit:read", "audit", "read", "审计读"),
]

DICTS = {
    "lead_source": [("网站", "website"), ("展会", "exhibition"), ("转介绍", "referral"), ("导入", "import")],
    "lead_status": [
        ("新建", "new"),
        ("已分配", "assigned"),
        ("跟进中", "following"),
        ("已转化", "converted"),
        ("无效", "invalid"),
        ("公海", "pooled"),
    ],
    "account_level": [("A", "A"), ("B", "B"), ("C", "C")],
    "opp_stage": [
        ("资质", "qualify"),
        ("需求", "needs"),
        ("方案", "proposal"),
        ("谈判", "negotiation"),
        ("赢单", "won"),
        ("输单", "lost"),
    ],
    "activity_type": [
        ("拜访", "visit"),
        ("电话", "call"),
        ("邮件", "email"),
        ("微信", "wechat"),
        ("其他", "other"),
    ],
}


def main() -> None:
    # Ensure schema exists when seed runs after alembic
    from app.database import Base
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        tenant = db.scalar(select(Tenant).where(Tenant.name == "Default"))
        if not tenant:
            tenant = Tenant(name="Default", status="active", timezone="Asia/Shanghai", settings=json.dumps({}))
            db.add(tenant)
            db.flush()

        perm_ids: dict[str, int] = {}
        for code, resource, action, name in PERMISSIONS:
            perm = db.scalar(select(Permission).where(Permission.code == code))
            if not perm:
                perm = Permission(code=code, resource=resource, action=action, name=name)
                db.add(perm)
                db.flush()
            perm_ids[code] = perm.id

        role = db.scalar(select(Role).where(Role.tenant_id == tenant.id, Role.code == "admin"))
        if not role:
            role = Role(tenant_id=tenant.id, code="admin", name="系统管理员", data_scope="company")
            db.add(role)
            db.flush()
            for pid in perm_ids.values():
                db.add(RolePermission(role_id=role.id, permission_id=pid))

        sales_role = db.scalar(select(Role).where(Role.tenant_id == tenant.id, Role.code == "sales"))
        if not sales_role:
            sales_role = Role(tenant_id=tenant.id, code="sales", name="销售代表", data_scope="self")
            db.add(sales_role)
            db.flush()
            for code in (
                "lead:read",
                "lead:write",
                "lead:claim",
                "account:write",
                "account:claim",
                "activity:write",
                "opportunity:write",
            ):
                db.add(RolePermission(role_id=sales_role.id, permission_id=perm_ids[code]))

        dept = db.scalar(select(Department).where(Department.tenant_id == tenant.id, Department.name == "总部"))
        if not dept:
            dept = Department(tenant_id=tenant.id, name="总部", path="/", sort_order=0)
            db.add(dept)
            db.flush()
            dept.path = f"/{dept.id}/"

        admin = db.scalar(select(UserAccount).where(UserAccount.tenant_id == tenant.id, UserAccount.username == "admin"))
        if not admin:
            admin = UserAccount(
                tenant_id=tenant.id,
                dept_id=dept.id,
                username="admin",
                password_hash=hash_password("admin123"),
                display_name="系统管理员",
                email="admin@example.com",
                status="active",
            )
            db.add(admin)
            db.flush()
            db.add(UserRole(user_id=admin.id, role_id=role.id))

        pipe = db.scalar(select(Pipeline).where(Pipeline.tenant_id == tenant.id, Pipeline.is_default == 1))
        if not pipe:
            pipe = Pipeline(tenant_id=tenant.id, name="默认销售管道", is_default=1, created_by=admin.id if admin else None)
            db.add(pipe)
            db.flush()
            stages = [
                ("qualify", "资质确认", 0, 10),
                ("needs", "需求调研", 1, 30),
                ("proposal", "方案报价", 2, 50),
                ("negotiation", "商务谈判", 3, 70),
                ("won", "赢单", 4, 100),
                ("lost", "输单", 5, 0),
            ]
            for code, name, order, prob in stages:
                db.add(
                    PipelineStage(
                        tenant_id=tenant.id,
                        pipeline_id=pipe.id,
                        code=code,
                        name=name,
                        sort_order=order,
                        win_probability=prob,
                        enter_required_fields=json.dumps(["amount"] if code in ("proposal", "negotiation") else []),
                        need_approval=0,
                    )
                )

        for dict_type, items in DICTS.items():
            d = db.scalar(select(SysDict).where(SysDict.tenant_id == tenant.id, SysDict.dict_type == dict_type))
            if not d:
                d = SysDict(tenant_id=tenant.id, dict_type=dict_type, name=dict_type)
                db.add(d)
                db.flush()
                for idx, (label, value) in enumerate(items):
                    db.add(
                        SysDictItem(
                            tenant_id=tenant.id,
                            dict_id=d.id,
                            label=label,
                            value=value,
                            sort_order=idx,
                            enabled=1,
                        )
                    )

        db.commit()
        print("Seed complete. Login: admin / admin123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
