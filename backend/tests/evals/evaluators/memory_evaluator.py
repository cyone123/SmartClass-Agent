"""记忆检索与写入评估器"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from types import SimpleNamespace

from app.core.agent import create_agent_runtime
from app.core.evaluation import EvalCase, EvalCaseStatus, EvalResult
from app.core.memory import (
    delete_memory_item,
    experience_namespace,
    profile_namespace,
    put_memory_item,
    search_memory_items,
)
from app.core.memory_worker import MemoryReflectionWorker
from app.core.observability import ObservationEvent
from app.core.rag import create_rag_runtime
from app.core.skills import create_skill_registry
from app.core.speech import create_speech_runtime
from app.core.video_transcribe import create_video_transcription_runtime
from app.dependencies.db import AsyncSessionLocal
from app.services.memory_reflection_service import (
    build_reflection_job_candidates,
    register_reflection_candidates,
    wait_for_source_run_jobs,
)

from .base import BaseEvaluator


class _MemoryObservationSink:
    def __init__(self) -> None:
        self.events: list[ObservationEvent] = []

    def emit(self, event: ObservationEvent) -> None:
        self.events.append(event)


class MemoryEvaluator(BaseEvaluator):
    """记忆检索与写入评估器

    评估维度：
    - 是否正确加载用户 profile 记忆
    - 是否正确检索相关 experience 记忆
    - 是否避免加载不相关的记忆
    - 是否在适当时刻写入或更新记忆
    - 记忆内容是否避免保存完整隐私数据
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._runtime = None

    async def _get_runtime(self):
        """获取 Agent Runtime（延迟初始化）"""
        if self._runtime is None:
            # 初始化依赖
            rag_runtime = await create_rag_runtime()
            skill_registry = create_skill_registry()
            speech_runtime = create_speech_runtime()
            video_runtime = create_video_transcription_runtime(speech_runtime=speech_runtime)

            self._runtime = await create_agent_runtime(
                rag_runtime=rag_runtime,
                skill_registry=skill_registry,
                video_transcription_runtime=video_runtime,
            )
        return self._runtime

    async def evaluate(self, case: EvalCase) -> EvalResult:
        """执行记忆评估

        步骤：
        1. 获取 Agent Runtime
        2. 执行 LangGraph
        3. 提取记忆相关输出
        4. 执行所有断言
        5. 计算加权分数
        6. 返回 EvalResult
        """
        start_time = time.time()
        run_id = f"eval_{uuid.uuid4().hex[:8]}"

        try:
            # 获取 runtime
            runtime = await self._get_runtime()
            graph = runtime.streaming_graph

            # 准备配置
            thread_id, user_id = self._isolated_runtime_ids(case, run_id)
            await self._seed_case_memories(runtime.memory_store, user_id, case.context or {})
            before_profile = await search_memory_items(
                runtime.memory_store,
                profile_namespace(user_id),
                limit=100,
            )
            before_experience = await search_memory_items(
                runtime.memory_store,
                experience_namespace(user_id),
                limit=100,
            )

            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": user_id,
                }
            }

            # 走生产 SSE 同款流式边界，分别记录用户可感知的关键时延。
            stream_started = time.monotonic()
            observation_sink = _MemoryObservationSink()
            first_token_latency: float | None = None
            approval_latency: float | None = None
            stream_error: str | None = None
            pending_approval: dict | None = None

            async def run_stream(*, message: str | None = None, approval: dict | None = None) -> None:
                nonlocal first_token_latency, approval_latency, stream_error, pending_approval
                pending_approval = None
                async for event in runtime.stream_agent_events(
                    message if message is not None else str(case.input.get("message") or ""),
                    thread_id,
                    run_id=run_id,
                    user_id=user_id,
                    approval=approval,
                    observation_sink=observation_sink,
                ):
                    elapsed = time.monotonic() - stream_started
                    event_type = event.get("event")
                    if event_type == "token" and first_token_latency is None:
                        first_token_latency = elapsed
                    elif event_type == "approval":
                        if approval_latency is None:
                            approval_latency = elapsed
                        pending_approval = dict(event.get("data") or {})
                    elif event_type == "error":
                        stream_error = str((event.get("data") or {}).get("message") or "stream failed")

            await run_stream()
            for _ in range(3):
                interim_snapshot = await graph.aget_state(config)
                if "interrupt_for_userinput" not in tuple(getattr(interim_snapshot, "next", ()) or ()):
                    break
                await run_stream(
                    message=(
                        "核心内容是概念理解、规律探究和迁移应用；教学重点是通过现象归纳规律，"
                        "教学难点是用证据解释并迁移概念。教学流程包括5分钟导入、20分钟探究、"
                        "15分钟练习和5分钟总结，目标是学生能解释、应用并通过形成性评价。"
                    )
                )
            if pending_approval and pending_approval.get("stage") == "metadata_review":
                await run_stream(
                    approval={
                        "action": "approve",
                        "interrupt_id": pending_approval["interrupt_id"],
                    }
                )
            run_completion_latency = time.monotonic() - stream_started
            if stream_error:
                raise RuntimeError(stream_error)

            state_snapshot = await graph.aget_state(config)
            result = dict(getattr(state_snapshot, "values", {}) or {})
            boundary_status = "waiting_approval" if tuple(getattr(state_snapshot, "next", ()) or ()) else "succeeded"
            source_run_id = run_id
            candidates = build_reflection_job_candidates(
                run=SimpleNamespace(
                    run_id=source_run_id,
                    thread_id=thread_id,
                    user_id=user_id,
                    plan_id=None,
                    message=str(case.input.get("message") or ""),
                    approval=None,
                ),
                status=boundary_status,
                checkpoint_values=result,
            )
            reflection_started = time.monotonic()
            if candidates:
                async with AsyncSessionLocal() as db:
                    await register_reflection_candidates(db, candidates)
                    await db.commit()
                worker = MemoryReflectionWorker(runtime.memory_store)
                await worker.start()
                try:
                    await wait_for_source_run_jobs(AsyncSessionLocal, source_run_id)
                finally:
                    await worker.stop()
            background_processing_latency = time.monotonic() - reflection_started
            background_visible_latency = time.monotonic() - stream_started
            after_profile = await search_memory_items(
                runtime.memory_store,
                profile_namespace(user_id),
                limit=100,
            )
            after_experience = await search_memory_items(
                runtime.memory_store,
                experience_namespace(user_id),
                limit=100,
            )

            # 提取记忆相关输出
            profile_memory_context = result.get("profile_memory_context", "")
            experience_events = [
                event for event in observation_sink.events if event.event == "memory.experience_resolution"
            ]
            experience_snapshot_events = [
                event for event in observation_sink.events if event.event == "memory.experience_snapshot"
            ]
            experience_resolution_count = len(experience_events)
            experience_selected_count = max(
                (int(event.fields.get("selected_count") or 0) for event in experience_events),
                default=0,
            )
            experience_strategies = [str(event.fields.get("strategy") or "none") for event in experience_events]
            memory_operations = self._memory_operations(
                before_profile,
                after_profile,
                before_experience,
                after_experience,
            )
            profile_content = "\n".join(str(item.get("content") or item.get("summary") or "") for item in after_profile)

            actual_output = {
                "profile_memory_context": profile_memory_context,
                "experience_resolution_count": experience_resolution_count,
                "experience_snapshot_resolution_count": sum(
                    1 for event in experience_snapshot_events if bool(event.fields.get("refreshed"))
                ),
                "experience_snapshot_reuse_count": sum(
                    1 for event in experience_snapshot_events if bool(event.fields.get("reused"))
                ),
                "experience_selected_count": experience_selected_count,
                "experience_strategies": experience_strategies,
                "experience_truncated": any(bool(event.fields.get("truncated")) for event in experience_events),
                "experience_degraded": any(bool(event.fields.get("degraded")) for event in experience_events),
                "profile_memory_item_count": result.get("profile_memory_item_count", 0),
                "profile_memory_truncated": result.get("profile_memory_truncated", False),
                "memory_operations": memory_operations,
                "profile_memory_created": len(after_profile) > len(before_profile),
                "experience_memory_created": len(after_experience) > len(before_experience),
                "profile_memory_id": after_profile[0].get("id") if after_profile else None,
                "profile_memory_content": profile_content,
                "total_profile_memories": len(after_profile),
                "first_token_latency_seconds": first_token_latency,
                "approval_latency_seconds": approval_latency,
                "run_completion_latency_seconds": run_completion_latency,
                "background_processing_latency_seconds": background_processing_latency,
                "background_visible_latency_seconds": background_visible_latency,
                "input_message": case.input["message"],
                "response": (result.get("messages", [])[-1].content if result.get("messages") else ""),
                # 用于隐私检查
                "privacy_exposure": self._calculate_privacy_exposure(profile_memory_context, ""),
            }

            # 执行所有断言
            assertion_results = []
            for assertion in case.assertions:
                assertion_result = await self._check_assertion(assertion, actual_output)
                assertion_results.append(assertion_result)

            # 计算加权分数
            total_weight = sum(a.weight for a in case.assertions)
            weighted_score = (
                sum(r["score"] * r["weight"] for r in assertion_results) / total_weight if total_weight > 0 else 0.0
            )

            # 判断是否通过（所有权重 >= 0.5 的断言必须通过）
            all_critical_passed = all(r["passed"] for r in assertion_results if r["weight"] >= 0.5)
            status = EvalCaseStatus.PASSED if all_critical_passed else EvalCaseStatus.FAILED

            return EvalResult(
                case_id=case.case_id,
                run_id=run_id,
                status=status,
                score=weighted_score,
                assertion_results=assertion_results,
                actual_output=actual_output,
                execution_time=time.time() - start_time,
                run_mode="model-eval",
                timestamp=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            return EvalResult(
                case_id=case.case_id,
                run_id=run_id,
                status=EvalCaseStatus.ERROR,
                score=0.0,
                assertion_results=[],
                actual_output={},
                execution_time=time.time() - start_time,
                error_message=str(e),
                run_mode="model-eval",
                timestamp=datetime.utcnow().isoformat(),
            )

    async def _seed_case_memories(self, store, user_id: str, context: dict) -> None:
        """Reset the eval-only namespace and seed declared fixture memories."""
        for namespace in (profile_namespace(user_id), experience_namespace(user_id)):
            for item in await search_memory_items(store, namespace, limit=100):
                if item.get("id"):
                    await delete_memory_item(store, namespace, str(item["id"]))

        existing_profile = context.get("existing_profile_memory")
        if isinstance(existing_profile, dict):
            await put_memory_item(
                store,
                profile_namespace(user_id),
                key=str(existing_profile.get("id") or "profile_seed"),
                value={
                    "title": existing_profile.get("title") or "教师画像",
                    "summary": existing_profile.get("content") or "",
                    "content": existing_profile.get("content") or "",
                    "tags": ["eval-seed"],
                    "kind": "profile",
                },
            )

        for index, experience in enumerate(context.get("available_experiences") or []):
            if not isinstance(experience, dict):
                continue
            content = str(
                experience.get("content")
                or experience.get("strategy")
                or experience.get("summary")
                or experience.get("topic")
                or ""
            )
            await put_memory_item(
                store,
                experience_namespace(user_id),
                key=str(experience.get("id") or f"experience_seed_{index}"),
                value={
                    "title": experience.get("topic") or "教学经验",
                    "summary": content,
                    "content": content,
                    "tags": ["eval-seed"],
                    "kind": "experience",
                },
            )

    @staticmethod
    def _memory_operations(
        before_profile: list[dict],
        after_profile: list[dict],
        before_experience: list[dict],
        after_experience: list[dict],
    ) -> list[dict]:
        operations: list[dict] = []
        for kind, before, after in (
            ("profile", before_profile, after_profile),
            ("experience", before_experience, after_experience),
        ):
            before_by_id = {str(item.get("id")): item for item in before}
            after_by_id = {str(item.get("id")): item for item in after}
            for memory_id in sorted(after_by_id.keys() - before_by_id.keys()):
                operations.append({"operation": "create", "kind": kind, "id": memory_id})
            for memory_id in sorted(after_by_id.keys() & before_by_id.keys()):
                if after_by_id[memory_id] != before_by_id[memory_id]:
                    operations.append({"operation": "update", "kind": kind, "id": memory_id})
        return operations

    def _calculate_privacy_exposure(self, profile_context: str, experience_context: str) -> float:
        """计算隐私暴露程度 (0.0-1.0)

        评估记忆上下文中是否包含敏感个人信息。
        """
        combined = f"{profile_context} {experience_context}".lower()

        # 敏感关键词 - 表示可能泄露隐私
        privacy_keywords = [
            "电话",
            "邮箱",
            "地址",
            "身份证",
            "密码",
            "账户",
            "学号",
            "工号",
            "家庭地址",
            "手机号",
            "qq号",
            "微信号",
        ]

        found_keywords = [kw for kw in privacy_keywords if kw in combined]
        exposure = len(found_keywords) / len(privacy_keywords) if privacy_keywords else 0.0

        return min(1.0, exposure)
