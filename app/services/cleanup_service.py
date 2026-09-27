# -*- coding: utf-8 -*-
"""
数据库清理服务
定期清理过期数据，保持数据库性能
"""

import os
import glob
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database import AsyncSessionLocal
from app.models.api_call_log import ApiCallLog
from app.models.speak_task import SpeakTask
from app.models.user_activity import UserActivity
from app.models.notification_log import NotificationLog
from app.config import get_settings


class DatabaseCleanupService:
    """数据库清理服务"""
    
    def __init__(self):
        self.session: AsyncSession = None
        self.settings = get_settings()
        
        # 从配置文件获取数据保留天数
        self.retention_days = {
            'api_call_logs': self.settings.api_logs_retention_days,
            'speak_tasks': self.settings.speak_tasks_retention_days,
            'user_activities': self.settings.user_activities_retention_days,
            'notification_logs': getattr(self.settings, 'notification_logs_retention_days', 30),
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = AsyncSessionLocal()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def cleanup_api_call_logs(self, retention_days: int = None) -> Dict[str, Any]:
        """
        清理API调用记录
        
        Args:
            retention_days: 保留天数，默认90天
            
        Returns:
            清理结果统计
        """
        if retention_days is None:
            retention_days = self.retention_days['api_call_logs']
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        try:
            # 统计要删除的记录数
            count_stmt = select(func.count(ApiCallLog.id)).where(ApiCallLog.created_at < cutoff_date)
            count_result = await self.session.execute(count_stmt)
            records_to_delete = count_result.scalar() or 0
            
            if records_to_delete == 0:
                logger.info(f"API调用记录清理：没有超过{retention_days}天的记录需要清理")
                return {
                    'table': 'api_call_logs',
                    'retention_days': retention_days,
                    'records_deleted': 0,
                    'cutoff_date': cutoff_date.isoformat(),
                    'status': 'success'
                }
            
            # 执行删除
            delete_stmt = delete(ApiCallLog).where(ApiCallLog.created_at < cutoff_date)
            result = await self.session.execute(delete_stmt)
            await self.session.commit()
            
            deleted_count = result.rowcount
            logger.info(f"API调用记录清理完成：删除了{deleted_count}条超过{retention_days}天的记录")
            
            return {
                'table': 'api_call_logs',
                'retention_days': retention_days,
                'records_deleted': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'success'
            }
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"API调用记录清理失败: {str(e)}")
            return {
                'table': 'api_call_logs',
                'retention_days': retention_days,
                'records_deleted': 0,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'error',
                'error': str(e)
            }
    
    async def cleanup_speak_tasks(self, retention_days: int = None) -> Dict[str, Any]:
        """
        清理播放任务记录
        
        Args:
            retention_days: 保留天数，默认7天
            
        Returns:
            清理结果统计
        """
        if retention_days is None:
            retention_days = self.retention_days['speak_tasks']
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        try:
            # 统计要删除的记录数
            count_stmt = select(func.count(SpeakTask.id)).where(SpeakTask.created_at < cutoff_date)
            count_result = await self.session.execute(count_stmt)
            records_to_delete = count_result.scalar() or 0
            
            if records_to_delete == 0:
                logger.info(f"播放任务清理：没有超过{retention_days}天的记录需要清理")
                return {
                    'table': 'speak_tasks',
                    'retention_days': retention_days,
                    'records_deleted': 0,
                    'cutoff_date': cutoff_date.isoformat(),
                    'status': 'success'
                }
            
            # 执行删除
            delete_stmt = delete(SpeakTask).where(SpeakTask.created_at < cutoff_date)
            result = await self.session.execute(delete_stmt)
            await self.session.commit()
            
            deleted_count = result.rowcount
            logger.info(f"播放任务清理完成：删除了{deleted_count}条超过{retention_days}天的记录")
            
            return {
                'table': 'speak_tasks',
                'retention_days': retention_days,
                'records_deleted': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'success'
            }
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"播放任务清理失败: {str(e)}")
            return {
                'table': 'speak_tasks',
                'retention_days': retention_days,
                'records_deleted': 0,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'error',
                'error': str(e)
            }
    
    async def cleanup_user_activities(self, retention_days: int = None) -> Dict[str, Any]:
        """
        清理用户活动记录
        
        Args:
            retention_days: 保留天数，默认30天
            
        Returns:
            清理结果统计
        """
        if retention_days is None:
            retention_days = self.retention_days['user_activities']
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        
        try:
            # 统计要删除的记录数
            count_stmt = select(func.count(UserActivity.id)).where(UserActivity.created_at < cutoff_date)
            count_result = await self.session.execute(count_stmt)
            records_to_delete = count_result.scalar() or 0
            
            if records_to_delete == 0:
                logger.info(f"用户活动记录清理：没有超过{retention_days}天的记录需要清理")
                return {
                    'table': 'user_activities',
                    'retention_days': retention_days,
                    'records_deleted': 0,
                    'cutoff_date': cutoff_date.isoformat(),
                    'status': 'success'
                }
            
            # 执行删除
            delete_stmt = delete(UserActivity).where(UserActivity.created_at < cutoff_date)
            result = await self.session.execute(delete_stmt)
            await self.session.commit()
            
            deleted_count = result.rowcount
            logger.info(f"用户活动记录清理完成：删除了{deleted_count}条超过{retention_days}天的记录")
            
            return {
                'table': 'user_activities',
                'retention_days': retention_days,
                'records_deleted': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'success'
            }
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"用户活动记录清理失败: {str(e)}")
            return {
                'table': 'user_activities',
                'retention_days': retention_days,
                'records_deleted': 0,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'error',
                'error': str(e)
            }
    
    async def cleanup_notification_logs(self, retention_days: int = None) -> Dict[str, Any]:
        """
        清理通知发送历史记录

        Args:
            retention_days: 保留天数，默认由配置 notification_logs_retention_days 决定

        Returns:
            清理结果统计
        """
        if retention_days is None:
            retention_days = self.retention_days['notification_logs']

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        try:
            # 统计要删除的记录数
            count_stmt = select(func.count(NotificationLog.id)).where(NotificationLog.created_at < cutoff_date)
            count_result = await self.session.execute(count_stmt)
            records_to_delete = count_result.scalar() or 0

            if records_to_delete == 0:
                logger.info(f"通知日志清理：没有超过{retention_days}天的记录需要清理")
                return {
                    'table': 'notification_logs',
                    'retention_days': retention_days,
                    'records_deleted': 0,
                    'cutoff_date': cutoff_date.isoformat(),
                    'status': 'success'
                }

            # 执行删除
            delete_stmt = delete(NotificationLog).where(NotificationLog.created_at < cutoff_date)
            result = await self.session.execute(delete_stmt)
            await self.session.commit()

            deleted_count = result.rowcount
            logger.info(f"通知日志清理完成：删除了{deleted_count}条超过{retention_days}天的记录")

            return {
                'table': 'notification_logs',
                'retention_days': retention_days,
                'records_deleted': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'success'
            }

        except Exception as e:
            await self.session.rollback()
            logger.error(f"通知日志清理失败: {str(e)}")
            return {
                'table': 'notification_logs',
                'retention_days': retention_days,
                'records_deleted': 0,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'error',
                'error': str(e)
            }

    def cleanup_log_files(self) -> Dict[str, Any]:
        """
        清理过期的日志文件
        
        Returns:
            Dict[str, Any]: 清理结果
        """
        try:
            retention_days = getattr(self.settings, 'log_files_retention_days', 30)
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            # 获取logs目录路径
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
            
            if not os.path.exists(logs_dir):
                logger.warning(f"日志目录不存在: {logs_dir}")
                return {
                    'table': 'log_files',
                    'retention_days': retention_days,
                    'records_deleted': 0,
                    'cutoff_date': cutoff_date.isoformat(),
                    'status': 'error',
                    'error': '日志目录不存在'
                }
            
            # 查找所有日志文件（包括压缩文件）
            log_patterns = [
                os.path.join(logs_dir, "*.log"),
                os.path.join(logs_dir, "*.log.zip"),
                os.path.join(logs_dir, "*.log.gz")
            ]
            
            deleted_count = 0
            deleted_files = []
            
            for pattern in log_patterns:
                for file_path in glob.glob(pattern):
                    try:
                        # 获取文件修改时间（带 UTC 时区，与 cutoff_date 保持 aware 比较）
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
                        
                        # 如果文件超过保留期限，则删除
                        if file_mtime < cutoff_date:
                            # 跳过当前正在使用的日志文件
                            if os.path.basename(file_path) == "miapi.log":
                                continue
                                
                            os.remove(file_path)
                            deleted_count += 1
                            deleted_files.append(os.path.basename(file_path))
                            logger.info(f"删除过期日志文件: {file_path}")
                            
                    except Exception as e:
                        logger.error(f"删除日志文件失败 {file_path}: {e}")
            
            logger.info(f"日志文件清理完成，删除了 {deleted_count} 个文件")
            return {
                'table': 'log_files',
                'retention_days': retention_days,
                'records_deleted': deleted_count,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'success',
                'deleted_files': deleted_files
            }
            
        except Exception as e:
            logger.error(f"日志文件清理失败: {e}")
            return {
                'table': 'log_files',
                'retention_days': retention_days,
                'records_deleted': 0,
                'cutoff_date': cutoff_date.isoformat(),
                'status': 'error',
                'error': str(e)
            }
    
    async def cleanup_all_tables(self) -> Dict[str, Any]:
        """
        清理所有表的过期数据
        
        Returns:
            所有表的清理结果统计
        """
        start_time = datetime.now(timezone.utc)
        results = []
        
        logger.info("开始执行数据库清理任务")
        
        # 清理API调用记录
        api_result = await self.cleanup_api_call_logs()
        results.append(api_result)
        
        # 清理播放任务
        task_result = await self.cleanup_speak_tasks()
        results.append(task_result)
        
        # 清理用户活动记录
        activity_result = await self.cleanup_user_activities()
        results.append(activity_result)
        
        # 清理通知日志
        notification_result = await self.cleanup_notification_logs()
        results.append(notification_result)
        
        # 清理日志文件
        log_result = self.cleanup_log_files()
        results.append(log_result)
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        # 统计总结果
        total_deleted = sum(r['records_deleted'] for r in results)
        success_count = sum(1 for r in results if r['status'] == 'success')
        error_count = len(results) - success_count
        
        summary = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'total_tables_processed': len(results),
            'successful_cleanups': success_count,
            'failed_cleanups': error_count,
            'total_records_deleted': total_deleted,
            'table_results': results
        }
        
        if error_count == 0:
            logger.info(f"数据库清理任务完成：共删除{total_deleted}条记录，耗时{duration:.2f}秒")
        else:
            logger.warning(f"数据库清理任务完成：共删除{total_deleted}条记录，{error_count}个表清理失败，耗时{duration:.2f}秒")
        
        return summary


async def run_database_cleanup() -> Dict[str, Any]:
    """
    运行数据库清理任务的便捷函数
    
    Returns:
        清理结果统计
    """
    async with DatabaseCleanupService() as cleanup_service:
        return await cleanup_service.cleanup_all_tables()


if __name__ == "__main__":
    import asyncio
    
    async def main():
        """测试清理服务"""
        result = await run_database_cleanup()
        print("清理结果:")
        print(f"总删除记录数: {result['total_records_deleted']}")
        print(f"成功清理表数: {result['successful_cleanups']}")
        print(f"失败清理表数: {result['failed_cleanups']}")
        print(f"耗时: {result['duration_seconds']:.2f}秒")
    
    asyncio.run(main())