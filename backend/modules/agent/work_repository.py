from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from modules.agent.models import (
    AgentGoal,
    AgentNotification,
    AgentRun,
    AgentTask,
    ApprovalRequest,
    ApprovalStatus,
    CasePriority,
    CaseStatus,
    Commitment,
    CustomerCase,
    GoalSource,
    GoalStatus,
    NotificationStatus,
    PolicyMode,
    RunStatus,
    ShopSchedule,
    ShopSoul,
    ShopPolicy,
    SoulLearning,
    TaskStatus,
)


def _apply_model_updates(target: object, **changes: object) -> None:
    for field_name, value in changes.items():
        setattr(target, field_name, value)


class AgentWorkRepository:
    """Concrete persistence layer for durable agent work objects."""

    def __init__(self, db: Session):
        self.db = db

    def create_goal(
        self,
        *,
        shop_id: int,
        goal_type: str,
        title: str,
        created_by_user_id: Optional[int] = None,
        description: Optional[str] = None,
        source: GoalSource = GoalSource.CHAT,
        priority: str = "normal",
        autonomy_policy: Optional[str] = None,
        context: Optional[dict] = None,
        due_at: Optional[datetime] = None,
    ) -> AgentGoal:
        goal = AgentGoal(
            shop_id=shop_id,
            created_by_user_id=created_by_user_id,
            goal_type=goal_type,
            title=title,
            description=description,
            source=source,
            priority=priority,
            autonomy_policy=autonomy_policy,
            context=context,
            due_at=due_at,
        )
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def get_goal(self, goal_id: int) -> Optional[AgentGoal]:
        return self.db.query(AgentGoal).filter(AgentGoal.id == goal_id).first()

    def list_active_goals(self, shop_id: int, limit: int = 25) -> list[AgentGoal]:
        terminal = [GoalStatus.COMPLETED, GoalStatus.CANCELLED, GoalStatus.FAILED]
        return (
            self.db.query(AgentGoal)
            .filter(AgentGoal.shop_id == shop_id, ~AgentGoal.status.in_(terminal))
            .order_by(AgentGoal.created_at.desc())
            .limit(limit)
            .all()
        )

    def update_goal_status(
        self,
        goal_id: int,
        status: GoalStatus,
        *,
        summary: Optional[str] = None,
    ) -> Optional[AgentGoal]:
        goal = self.get_goal(goal_id)
        if goal is None:
            return None
        _apply_model_updates(goal, status=status)
        if status == GoalStatus.IN_PROGRESS and goal.started_at is None:
            _apply_model_updates(goal, started_at=datetime.utcnow())
        if status in {GoalStatus.COMPLETED, GoalStatus.CANCELLED, GoalStatus.FAILED}:
            _apply_model_updates(goal, completed_at=datetime.utcnow())
        if summary is not None:
            _apply_model_updates(goal, summary=summary)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def create_task(
        self,
        *,
        goal_id: int,
        shop_id: int,
        assigned_agent: str,
        task_type: str,
        title: str,
        description: Optional[str] = None,
        sequence_index: int = 0,
        requires_approval: bool = False,
        input_payload: Optional[dict] = None,
    ) -> AgentTask:
        task = AgentTask(
            goal_id=goal_id,
            shop_id=shop_id,
            assigned_agent=assigned_agent,
            task_type=task_type,
            title=title,
            description=description,
            sequence_index=sequence_index,
            requires_approval=requires_approval,
            input_payload=input_payload,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def list_tasks_for_goal(self, goal_id: int) -> list[AgentTask]:
        return (
            self.db.query(AgentTask)
            .filter(AgentTask.goal_id == goal_id)
            .order_by(AgentTask.sequence_index.asc(), AgentTask.created_at.asc())
            .all()
        )

    def update_task_status(
        self,
        task_id: int,
        status: TaskStatus,
        *,
        output_payload: Optional[dict] = None,
    ) -> Optional[AgentTask]:
        task = self.db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if task is None:
            return None
        _apply_model_updates(task, status=status)
        if status == TaskStatus.IN_PROGRESS and task.started_at is None:
            _apply_model_updates(task, started_at=datetime.utcnow())
        if status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED}:
            _apply_model_updates(task, completed_at=datetime.utcnow())
        if output_payload is not None:
            _apply_model_updates(task, output_payload=output_payload)
        self.db.commit()
        self.db.refresh(task)
        return task

    def create_run(
        self,
        *,
        shop_id: int,
        run_type: str,
        trigger_source: str,
        execution_mode: str,
        goal_id: Optional[int] = None,
        task_id: Optional[int] = None,
        triggered_by_user_id: Optional[int] = None,
        graph_thread_id: Optional[str] = None,
        current_agent: Optional[str] = None,
        input_payload: Optional[dict] = None,
        event_context: Optional[dict] = None,
    ) -> AgentRun:
        run = AgentRun(
            shop_id=shop_id,
            goal_id=goal_id,
            task_id=task_id,
            triggered_by_user_id=triggered_by_user_id,
            run_type=run_type,
            trigger_source=trigger_source,
            execution_mode=execution_mode,
            graph_thread_id=graph_thread_id,
            current_agent=current_agent,
            status=RunStatus.RUNNING,
            input_payload=input_payload,
            event_context=event_context,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_run_status(
        self,
        run_id: int,
        status: RunStatus,
        *,
        output_payload: Optional[dict] = None,
        error_message: Optional[str] = None,
        current_agent: Optional[str] = None,
    ) -> Optional[AgentRun]:
        run = self.db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if run is None:
            return None
        _apply_model_updates(run, status=status)
        if output_payload is not None:
            _apply_model_updates(run, output_payload=output_payload)
        if error_message is not None:
            _apply_model_updates(run, error_message=error_message)
        if current_agent is not None:
            _apply_model_updates(run, current_agent=current_agent)
        if status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
            _apply_model_updates(run, completed_at=datetime.utcnow())
        self.db.commit()
        self.db.refresh(run)
        return run

    def create_approval_request(
        self,
        *,
        shop_id: int,
        requested_by_agent: str,
        action_type: str,
        title: str,
        external_action_id: Optional[str] = None,
        goal_id: Optional[int] = None,
        task_id: Optional[int] = None,
        run_id: Optional[int] = None,
        requested_by_user_id: Optional[int] = None,
        rationale: Optional[str] = None,
        expected_impact: Optional[str] = None,
        urgency: str = "normal",
        request_payload: Optional[dict] = None,
        expires_at: Optional[datetime] = None,
    ) -> ApprovalRequest:
        approval = ApprovalRequest(
            external_action_id=external_action_id,
            shop_id=shop_id,
            goal_id=goal_id,
            task_id=task_id,
            run_id=run_id,
            requested_by_user_id=requested_by_user_id,
            requested_by_agent=requested_by_agent,
            action_type=action_type,
            title=title,
            rationale=rationale,
            expected_impact=expected_impact,
            urgency=urgency,
            request_payload=request_payload,
            expires_at=expires_at,
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def get_pending_approval_by_action_id(self, shop_id: int, action_id: str) -> Optional[ApprovalRequest]:
        return (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.shop_id == shop_id,
                ApprovalRequest.external_action_id == action_id,
                ApprovalRequest.status == ApprovalStatus.PENDING,
            )
            .first()
        )

    def list_pending_approval_requests(self, shop_id: int, limit: int = 25) -> list[ApprovalRequest]:
        return (
            self.db.query(ApprovalRequest)
            .filter(
                ApprovalRequest.shop_id == shop_id,
                ApprovalRequest.status == ApprovalStatus.PENDING,
            )
            .order_by(ApprovalRequest.requested_at.asc())
            .limit(limit)
            .all()
        )

    def decide_approval_request(
        self,
        approval_request_id: int,
        *,
        status: ApprovalStatus,
        decided_by_user_id: int,
        decision_reason: Optional[str] = None,
        decision_payload: Optional[dict] = None,
    ) -> Optional[ApprovalRequest]:
        approval = (
            self.db.query(ApprovalRequest)
            .filter(ApprovalRequest.id == approval_request_id)
            .first()
        )
        if approval is None:
            return None
        _apply_model_updates(
            approval,
            status=status,
            decided_by_user_id=decided_by_user_id,
            decision_reason=decision_reason,
            decision_payload=decision_payload,
            decided_at=datetime.utcnow(),
        )
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def upsert_shop_policy(
        self,
        *,
        shop_id: int,
        policy_key: str,
        mode: PolicyMode,
        category: str = "operations",
        enabled: bool = True,
        policy_value: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> ShopPolicy:
        policy = (
            self.db.query(ShopPolicy)
            .filter(ShopPolicy.shop_id == shop_id, ShopPolicy.policy_key == policy_key)
            .first()
        )
        if policy is None:
            policy = ShopPolicy(
                shop_id=shop_id,
                policy_key=policy_key,
                category=category,
                mode=mode,
                enabled=enabled,
                policy_value=policy_value,
                config=config,
            )
            self.db.add(policy)
        else:
            _apply_model_updates(
                policy,
                category=category,
                mode=mode,
                enabled=enabled,
                policy_value=policy_value,
                config=config,
            )
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def get_shop_policies(self, shop_id: int) -> list[ShopPolicy]:
        return (
            self.db.query(ShopPolicy)
            .filter(ShopPolicy.shop_id == shop_id, ShopPolicy.enabled.is_(True))
            .order_by(ShopPolicy.category.asc(), ShopPolicy.policy_key.asc())
            .all()
        )

    def create_notification(
        self,
        *,
        shop_id: int,
        notification_type: str,
        title: str,
        message: str,
        goal_id: Optional[int] = None,
        task_id: Optional[int] = None,
        run_id: Optional[int] = None,
        severity: str = "info",
        payload: Optional[dict] = None,
    ) -> AgentNotification:
        notification = AgentNotification(
            shop_id=shop_id,
            goal_id=goal_id,
            task_id=task_id,
            run_id=run_id,
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
            payload=payload,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_notification_read(self, notification_id: int) -> Optional[AgentNotification]:
        notification = (
            self.db.query(AgentNotification)
            .filter(AgentNotification.id == notification_id)
            .first()
        )
        if notification is None:
            return None
        if notification.status == NotificationStatus.READ:
            return notification
        _apply_model_updates(notification, status=NotificationStatus.READ, read_at=datetime.utcnow())
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_notification_read_for_shop(
        self,
        notification_id: int,
        shop_id: int,
    ) -> Optional[AgentNotification]:
        notification = (
            self.db.query(AgentNotification)
            .filter(
                AgentNotification.id == notification_id,
                AgentNotification.shop_id == shop_id,
            )
            .first()
        )
        if notification is None:
            return None
        if notification.status == NotificationStatus.READ:
            return notification
        _apply_model_updates(notification, status=NotificationStatus.READ, read_at=datetime.utcnow())
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def mark_all_notifications_read(self, shop_id: int) -> int:
        updated = (
            self.db.query(AgentNotification)
            .filter(
                AgentNotification.shop_id == shop_id,
                AgentNotification.status == NotificationStatus.UNREAD,
            )
            .update(
                {
                    AgentNotification.status: NotificationStatus.READ,
                    AgentNotification.read_at: datetime.utcnow(),
                    AgentNotification.updated_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return int(updated or 0)

    def list_recent_notifications(self, shop_id: int, limit: int = 25) -> list[AgentNotification]:
        return (
            self.db.query(AgentNotification)
            .filter(AgentNotification.shop_id == shop_id)
            .order_by(AgentNotification.created_at.desc(), AgentNotification.id.desc())
            .limit(limit)
            .all()
        )

    def get_or_create_shop_soul(self, shop_id: int) -> ShopSoul:
        soul = self.db.query(ShopSoul).filter(ShopSoul.shop_id == shop_id).first()
        if soul is None:
            soul = ShopSoul(
                shop_id=shop_id,
                personality={},
                learned_patterns=[],
                recent_decisions=[],
                open_items=[],
            )
            self.db.add(soul)
            self.db.commit()
            self.db.refresh(soul)
        return soul

    def update_shop_soul(self, shop_id: int, **changes: object) -> ShopSoul:
        soul = self.get_or_create_shop_soul(shop_id)
        allowed = {
            "tone",
            "upsell_style",
            "owner_communication",
            "personality",
            "learned_patterns",
            "recent_decisions",
            "open_items",
            "summary",
            "tier_scope",
            "rolling_window_days",
            "last_evolved_at",
        }
        _apply_model_updates(soul, **{key: value for key, value in changes.items() if key in allowed})
        self.db.commit()
        self.db.refresh(soul)
        return soul

    def create_soul_learning(
        self,
        *,
        shop_id: int,
        content: str,
        run_id: Optional[int] = None,
        source: str = "conversation",
        category: str = "pattern",
        confidence_score: float = 0.5,
        evidence: Optional[dict] = None,
    ) -> SoulLearning:
        learning = SoulLearning(
            shop_id=shop_id,
            run_id=run_id,
            source=source,
            category=category,
            content=content,
            confidence_score=confidence_score,
            evidence=evidence,
        )
        self.db.add(learning)
        self.db.commit()
        self.db.refresh(learning)
        return learning

    def create_commitment(
        self,
        *,
        shop_id: int,
        made_by: str,
        commitment: str,
        run_id: Optional[int] = None,
        due_at: Optional[datetime] = None,
        trigger_if_missed: Optional[str] = None,
        action_payload: Optional[dict] = None,
        detected_from: Optional[dict] = None,
    ) -> Commitment:
        record = Commitment(
            shop_id=shop_id,
            run_id=run_id,
            made_by=made_by,
            commitment=commitment,
            due_at=due_at,
            trigger_if_missed=trigger_if_missed,
            action_payload=action_payload,
            detected_from=detected_from,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_pending_commitments(self, shop_id: int, limit: int = 25) -> list[Commitment]:
        return (
            self.db.query(Commitment)
            .filter(Commitment.shop_id == shop_id, Commitment.status == "pending")
            .order_by(Commitment.due_at.asc().nulls_last(), Commitment.created_at.asc())
            .limit(limit)
            .all()
        )

    def upsert_shop_schedule(
        self,
        *,
        shop_id: int,
        schedule_key: str,
        temporal_schedule_id: str,
        title: str,
        cron_expression: str,
        created_by_user_id: Optional[int] = None,
        schedule_type: str = "custom",
        description: Optional[str] = None,
        natural_language: Optional[str] = None,
        timezone: str = "UTC",
        target_agent: str = "supervisor",
        action_payload: Optional[dict] = None,
        condition_payload: Optional[dict] = None,
        tier_scope: str = "free",
        status: str = "active",
    ) -> ShopSchedule:
        schedule = (
            self.db.query(ShopSchedule)
            .filter(ShopSchedule.shop_id == shop_id, ShopSchedule.schedule_key == schedule_key)
            .first()
        )
        payload = {
            "created_by_user_id": created_by_user_id,
            "temporal_schedule_id": temporal_schedule_id,
            "schedule_type": schedule_type,
            "title": title,
            "description": description,
            "natural_language": natural_language,
            "cron_expression": cron_expression,
            "timezone": timezone,
            "target_agent": target_agent,
            "action_payload": action_payload,
            "condition_payload": condition_payload,
            "tier_scope": tier_scope,
            "status": status,
        }
        if schedule is None:
            schedule = ShopSchedule(shop_id=shop_id, schedule_key=schedule_key, **payload)
            self.db.add(schedule)
        else:
            _apply_model_updates(schedule, **payload)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def list_active_shop_schedules(self, shop_id: int, limit: int = 50) -> list[ShopSchedule]:
        return (
            self.db.query(ShopSchedule)
            .filter(ShopSchedule.shop_id == shop_id, ShopSchedule.status == "active")
            .order_by(ShopSchedule.created_at.desc())
            .limit(limit)
            .all()
        )

    def create_customer_case(
        self,
        *,
        shop_id: int,
        case_type: str,
        title: str,
        source: str = "customer_chat",
        customer_user_id: Optional[int] = None,
        current_goal_id: Optional[int] = None,
        summary: Optional[str] = None,
        details: Optional[dict] = None,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
        priority: CasePriority = CasePriority.NORMAL,
    ) -> CustomerCase:
        customer_case = CustomerCase(
            shop_id=shop_id,
            customer_user_id=customer_user_id,
            current_goal_id=current_goal_id,
            case_type=case_type,
            title=title,
            source=source,
            summary=summary,
            details=details,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            priority=priority,
            last_customer_message_at=datetime.utcnow(),
        )
        self.db.add(customer_case)
        self.db.commit()
        self.db.refresh(customer_case)
        return customer_case

    def update_customer_case_status(
        self,
        case_id: int,
        *,
        status: CaseStatus,
        summary: Optional[str] = None,
        owner_notification_sent: Optional[bool] = None,
    ) -> Optional[CustomerCase]:
        customer_case = self.db.query(CustomerCase).filter(CustomerCase.id == case_id).first()
        if customer_case is None:
            return None
        _apply_model_updates(customer_case, status=status)
        if summary is not None:
            _apply_model_updates(customer_case, summary=summary)
        if owner_notification_sent is not None:
            _apply_model_updates(customer_case, owner_notification_sent=owner_notification_sent)
        if status in {CaseStatus.RESOLVED, CaseStatus.CLOSED}:
            _apply_model_updates(customer_case, resolved_at=datetime.utcnow())
        self.db.commit()
        self.db.refresh(customer_case)
        return customer_case