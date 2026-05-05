#!/usr/bin/env python3
"""TaskRunner 接口 — 异步任务抽象层

默认实现使用 APScheduler 做定时调度，预留 Celery 分布式接口。
"""

from abc import ABC, abstractmethod
from concurrent.futures import Future
from typing import Any, Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class AbstractTaskRunner(ABC):
    """异步任务运行器抽象基类"""

    @abstractmethod
    def submit(self, func: Callable, *args, **kwargs) -> Any:
        """提交一次性任务，返回 job_id 或 Future"""

    @abstractmethod
    def schedule(self, cron_expr: str, func: Callable, *args, **kwargs) -> str:
        """按 cron 表达式定时执行，返回 job_id"""

    @abstractmethod
    def cancel(self, job_id: str) -> bool:
        """取消任务，返回是否成功"""


class APSchedulerRunner(AbstractTaskRunner):
    """默认实现：APScheduler + concurrent.futures

    适合单用户本地系统，零外部依赖（APScheduler 除外）。
    """

    def __init__(self):
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        from concurrent.futures import ThreadPoolExecutor
        self._executor = ThreadPoolExecutor(max_workers=2)

    def submit(self, func: Callable, *args, **kwargs) -> Future:
        return self._executor.submit(func, *args, **kwargs)

    def schedule(self, cron_expr: str, func: Callable, *args, **kwargs) -> str:
        """按 cron 表达式定时执行

        cron_expr 格式：'分 时 日 月 星期'，例如 '0 3 * * *' 表示每天 3:00
        """
        # 解析 cron 表达式为 trigger
        parts = cron_expr.split()
        trigger = CronTrigger(
            minute=parts[0], hour=parts[1],
            day=parts[2], month=parts[3],
            day_of_week=parts[4]
        )
        job = self._scheduler.add_job(func, trigger, args=args, kwargs=kwargs)
        return str(job.id)

    def cancel(self, job_id: str) -> bool:
        """取消定时任务"""
        try:
            self._scheduler.remove_job(job_id)
            return True
        except Exception:
            return False


class CeleryRunner(AbstractTaskRunner):
    """Celery 分布式任务运行器（预留）

    需要 Redis 作为 broker，适合多机分布式场景。
    """

    def submit(self, func: Callable, *args, **kwargs) -> Any:
        raise NotImplementedError("CeleryRunner 需要配置 Redis broker，暂不可用")

    def schedule(self, cron_expr: str, func: Callable, *args, **kwargs) -> str:
        raise NotImplementedError("CeleryRunner 需要配置 Redis broker，暂不可用")

    def cancel(self, job_id: str) -> bool:
        raise NotImplementedError("CeleryRunner 需要配置 Redis broker，暂不可用")
