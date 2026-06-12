# -*- coding: utf-8 -*-
"""
定时任务调度服务
使用APScheduler实现定时清理数据库
"""

import logging
import asyncio
from datetime import datetime, time
from typing import Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from app.services.cleanup_service import run_database_cleanup
from app.config import settings


logger = logging.getLogger(__name__)


class SchedulerService:
    """定时任务调度服务"""
    
    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False
        
        # 清理任务配置
        self.cleanup_config = {
            'hour': getattr(settings, 'cleanup_hour', 2),  # 默认凌晨2点执行
            'minute': getattr(settings, 'cleanup_minute', 0),  # 默认0分
            'timezone': getattr(settings, 'timezone', 'Asia/Shanghai'),  # 默认上海时区
            'enabled': getattr(settings, 'cleanup_enabled', True),  # 是否启用清理
        }
    
    def _setup_scheduler(self):
        """设置调度器"""
        if self.scheduler is None:
            self.scheduler = AsyncIOScheduler(
                timezone=self.cleanup_config['timezone']
            )
            
            # 添加事件监听器
            self.scheduler.add_listener(
                self._job_executed_listener,
                EVENT_JOB_EXECUTED
            )
            self.scheduler.add_listener(
                self._job_error_listener,
                EVENT_JOB_ERROR
            )
    
    def _job_executed_listener(self, event):
        """任务执行成功监听器"""
        logger.info(f"定时任务执行成功: {event.job_id} at {datetime.now()}")
    
    def _job_error_listener(self, event):
        """任务执行失败监听器"""
        logger.error(f"定时任务执行失败: {event.job_id}, 错误: {event.exception}")
    
    async def _cleanup_job_wrapper(self):
        """清理任务包装器，用于异常处理和日志记录"""
        try:
            logger.info("开始执行定时数据库清理任务")
            result = await run_database_cleanup()
            
            # 记录清理结果
            total_deleted = result.get('total_records_deleted', 0)
            duration = result.get('duration_seconds', 0)
            failed_cleanups = result.get('failed_cleanups', 0)
            
            if failed_cleanups == 0:
                logger.info(
                    f"定时数据库清理任务完成：删除{total_deleted}条记录，耗时{duration:.2f}秒"
                )
            else:
                logger.warning(
                    f"定时数据库清理任务完成：删除{total_deleted}条记录，{failed_cleanups}个表清理失败，耗时{duration:.2f}秒"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"定时数据库清理任务执行异常: {str(e)}")
            raise
    
    def add_cleanup_job(self, 
                       hour: Optional[int] = None, 
                       minute: Optional[int] = None,
                       job_id: str = 'database_cleanup') -> bool:
        """添加数据库清理定时任务
        
        Args:
            hour: 执行小时，默认使用配置值
            minute: 执行分钟，默认使用配置值
            job_id: 任务ID
            
        Returns:
            是否添加成功
        """
        try:
            # 检查是否启用清理功能
            if not self.cleanup_config['enabled']:
                logger.info("数据库清理功能已禁用，跳过添加清理任务")
                return False
            
            self._setup_scheduler()
            
            # 使用传入参数或配置默认值
            exec_hour = hour if hour is not None else self.cleanup_config['hour']
            exec_minute = minute if minute is not None else self.cleanup_config['minute']
            
            # 创建cron触发器：每天指定时间执行
            trigger = CronTrigger(
                hour=exec_hour,
                minute=exec_minute,
                timezone=self.cleanup_config['timezone']
            )
            
            # 添加任务
            self.scheduler.add_job(
                func=self._cleanup_job_wrapper,
                trigger=trigger,
                id=job_id,
                name='数据库清理任务',
                replace_existing=True,  # 如果任务已存在则替换
                max_instances=1,  # 最多同时运行1个实例
                coalesce=True,  # 合并错过的任务
                misfire_grace_time=3600  # 错过任务的宽限时间（1小时）
            )
            
            logger.info(
                f"数据库清理定时任务已添加：每天{exec_hour:02d}:{exec_minute:02d}执行"
            )
            return True
            
        except Exception as e:
            logger.error(f"添加数据库清理定时任务失败: {str(e)}")
            return False
    
    def remove_cleanup_job(self, job_id: str = 'database_cleanup') -> bool:
        """移除数据库清理定时任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            是否移除成功
        """
        try:
            if self.scheduler and self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"数据库清理定时任务已移除: {job_id}")
                return True
            else:
                logger.warning(f"未找到要移除的定时任务: {job_id}")
                return False
                
        except Exception as e:
            logger.error(f"移除数据库清理定时任务失败: {str(e)}")
            return False
    
    async def run_cleanup_now(self) -> Dict[str, Any]:
        """立即执行一次数据库清理
        
        Returns:
            清理结果
        """
        logger.info("手动触发数据库清理任务")
        return await self._cleanup_job_wrapper()
    
    def start(self) -> bool:
        """启动调度器
        
        Returns:
            是否启动成功
        """
        try:
            if self.scheduler is None:
                self._setup_scheduler()
            
            if not self.is_running:
                self.scheduler.start()
                self.is_running = True
                logger.info("定时任务调度器已启动")
                
                # 显示已添加的任务
                jobs = self.scheduler.get_jobs()
                if jobs:
                    logger.info(f"当前已添加{len(jobs)}个定时任务:")
                    for job in jobs:
                        logger.info(f"  - {job.name} ({job.id}): {job.next_run_time}")
                else:
                    logger.info("当前没有定时任务")
                
                return True
            else:
                logger.warning("定时任务调度器已经在运行")
                return True
                
        except Exception as e:
            logger.error(f"启动定时任务调度器失败: {str(e)}")
            return False
    
    def stop(self) -> bool:
        """停止调度器
        
        Returns:
            是否停止成功
        """
        try:
            if self.scheduler and self.is_running:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                logger.info("定时任务调度器已停止")
                return True
            else:
                logger.warning("定时任务调度器未在运行")
                return True
                
        except Exception as e:
            logger.error(f"停止定时任务调度器失败: {str(e)}")
            return False
    
    def get_job_status(self, job_id: str = 'database_cleanup') -> Optional[Dict[str, Any]]:
        """获取任务状态
        
        Args:
            job_id: 任务ID
            
        Returns:
            任务状态信息
        """
        if not self.scheduler:
            return None
        
        job = self.scheduler.get_job(job_id)
        if job:
            return {
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger),
                'max_instances': job.max_instances,
                'coalesce': job.coalesce
            }
        return None
    
    def list_jobs(self) -> list:
        """列出所有任务
        
        Returns:
            任务列表
        """
        if not self.scheduler:
            return []
        
        jobs = self.scheduler.get_jobs()
        return [
            {
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            }
            for job in jobs
        ]


# 全局调度器实例
_scheduler_instance: Optional[SchedulerService] = None


def get_scheduler() -> SchedulerService:
    """获取全局调度器实例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService()
    return _scheduler_instance


async def init_scheduler() -> bool:
    """初始化调度器并添加清理任务"""
    scheduler = get_scheduler()
    
    # 添加数据库清理任务
    if scheduler.add_cleanup_job():
        # 启动调度器
        return scheduler.start()
    return False


async def shutdown_scheduler() -> bool:
    """关闭调度器"""
    global _scheduler_instance
    if _scheduler_instance:
        result = _scheduler_instance.stop()
        _scheduler_instance = None
        return result
    return True


if __name__ == "__main__":
    async def main():
        """测试调度器"""
        # 初始化调度器
        await init_scheduler()
        
        # 立即执行一次清理
        scheduler = get_scheduler()
        result = await scheduler.run_cleanup_now()
        print(f"清理结果: {result['total_records_deleted']}条记录")
        
        # 显示任务状态
        status = scheduler.get_job_status()
        if status:
            print(f"下次执行时间: {status['next_run_time']}")
        
        # 关闭调度器
        await shutdown_scheduler()
    
    asyncio.run(main())