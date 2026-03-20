from django.shortcuts import render
from django.db.models import Q, Count, Avg
from tasks.models import Task, ExecutionLog
import logging

logger = logging.getLogger(__name__)


def average_duration(task_id):
    """
    Calculate the average actual duration of a task across all executions.
    
    Args:
        task_id (int): The ID of the task
        
    Returns:
        dict: Contains 'success' status and either 'average_duration_seconds' or 'error'
    """
    try:
        task = Task.objects.get(id=task_id)
        
        # Get all completed executions (where actual_end is not null)
        executions = ExecutionLog.objects.filter(
            task_id=task,
            skipped=False
        ).exclude(actual_end__isnull=True)
        
        if not executions.exists():
            return {
                'success': True,
                'average_duration_seconds': 0,
                'execution_count': 0,
                'message': 'No completed executions found'
            }
        
        # Calculate duration for each execution and get average
        total_duration = 0
        for execution in executions:
            duration = (execution.actual_end - execution.actual_start).total_seconds()
            total_duration += duration
        
        average = total_duration / executions.count()
        
        logger.info(f'Calculated average duration for task {task_id}: {average:.2f}s over {executions.count()} executions')
        
        return {
            'success': True,
            'task_id': task_id,
            'task_title': task.title,
            'average_duration_seconds': round(average, 2),
            'execution_count': executions.count()
        }
    
    except Task.DoesNotExist:
        return {
            'success': False,
            'error': f'Task with id {task_id} not found'
        }
    except Exception as e:
        logger.error(f'Error calculating average duration for task {task_id}: {str(e)}')
        return {
            'success': False,
            'error': 'An error occurred while calculating average duration'
        }


def skip_rate(task_id):
    """
    Calculate the skip rate (percentage) of a task across all executions.
    
    Args:
        task_id (int): The ID of the task
        
    Returns:
        dict: Contains 'success' status and either 'skip_rate_percentage' or 'error'
    """
    try:
        task = Task.objects.get(id=task_id)
        
        # Get all executions for this task
        total_executions = ExecutionLog.objects.filter(task_id=task).count()
        
        if total_executions == 0:
            return {
                'success': True,
                'skip_rate_percentage': 0,
                'skipped_count': 0,
                'total_count': 0,
                'message': 'No executions found'
            }
        
        # Count skipped executions
        skipped_executions = ExecutionLog.objects.filter(
            task_id=task,
            skipped=True
        ).count()
        
        skip_rate_percentage = (skipped_executions / total_executions) * 100 if total_executions > 0 else 0
        
        logger.info(f'Calculated skip rate for task {task_id}: {skip_rate_percentage:.2f}% ({skipped_executions}/{total_executions})')
        
        return {
            'success': True,
            'task_id': task_id,
            'task_title': task.title,
            'skip_rate_percentage': round(skip_rate_percentage, 2),
            'skipped_count': skipped_executions,
            'total_count': total_executions
        }
    
    except Task.DoesNotExist:
        return {
            'success': False,
            'error': f'Task with id {task_id} not found'
        }
    except Exception as e:
        logger.error(f'Error calculating skip rate for task {task_id}: {str(e)}')
        return {
            'success': False,
            'error': 'An error occurred while calculating skip rate'
        }


def schedule_accuracy(task_id):
    """
    Calculate the schedule accuracy (how close actual_start is to scheduled_start).
    
    Args:
        task_id (int): The ID of the task
        
    Returns:
        dict: Contains 'success' status and either schedule accuracy metrics or 'error'
    """
    try:
        task = Task.objects.get(id=task_id)
        
        # Get all executions (including skipped ones, as they can still have scheduled vs actual times)
        executions = ExecutionLog.objects.filter(task_id=task)
        
        if not executions.exists():
            return {
                'success': True,
                'average_deviation_seconds': 0,
                'on_time_count': 0,
                'total_count': 0,
                'message': 'No executions found'
            }
        
        # Calculate deviation between scheduled_start and actual_start for each execution
        total_deviation = 0
        on_time_count = 0
        
        for execution in executions:
            # Calculate deviation (positive = late, negative = early)
            deviation = (execution.actual_start - execution.scheduled_start).total_seconds()
            total_deviation += abs(deviation)
            
            # Consider on-time if within 5 minutes (300 seconds)
            if abs(deviation) <= 300:
                on_time_count += 1
        
        average_deviation = total_deviation / executions.count()
        on_time_percentage = (on_time_count / executions.count()) * 100 if executions.count() > 0 else 0
        
        logger.info(
            f'Calculated schedule accuracy for task {task_id}: '
            f'Average deviation: {average_deviation:.2f}s, On-time: {on_time_percentage:.2f}% ({on_time_count}/{executions.count()})'
        )
        
        return {
            'success': True,
            'task_id': task_id,
            'task_title': task.title,
            'average_deviation_seconds': round(average_deviation, 2),
            'on_time_percentage': round(on_time_percentage, 2),
            'on_time_count': on_time_count,
            'total_count': executions.count()
        }
    
    except Task.DoesNotExist:
        return {
            'success': False,
            'error': f'Task with id {task_id} not found'
        }
    except Exception as e:
        logger.error(f'Error calculating schedule accuracy for task {task_id}: {str(e)}')
        return {
            'success': False,
            'error': 'An error occurred while calculating schedule accuracy'
        }
