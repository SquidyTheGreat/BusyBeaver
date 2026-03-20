from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Task, ExecutionLog
import logging

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
def start_task(request, task_id):
    """
    Start a task by creating an ExecutionLog entry with actual_start timestamp.
    """
    try:
        task = Task.objects.get(id=task_id)
        
        execution_log = ExecutionLog(
            task_id=task,
            scheduled_start=timezone.now(),
            actual_start=timezone.now(),
            skipped=False
        )
        execution_log.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Task "{task.title}" started',
            'execution_id': execution_log.id,
            'task_id': task_id
        }, status=200)
    
    except Task.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Task with id {task_id} not found'
        }, status=404)
    
    except Exception as e:
        logger.error(f'Error starting task {task_id}: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while starting the task'
        }, status=500)


@require_http_methods(["POST"])
def complete_task(request, task_id):
    """
    Complete a task by updating its ExecutionLog with actual_end timestamp.
    Logs actual duration and deviation from estimated duration.
    """
    try:
        task = Task.objects.get(id=task_id)
        
        # Get the most recent execution log for this task
        execution_log = ExecutionLog.objects.filter(task_id=task).latest('actual_start')
        execution_log.actual_end = timezone.now()
        execution_log.skipped = False
        execution_log.save()
        
        # Calculate actual duration in seconds
        actual_duration = (execution_log.actual_end - execution_log.actual_start).total_seconds()
        
        # Calculate deviation from estimate (estimated_duration is in some unit, converting to seconds for comparison)
        # Assuming estimated_duration is in hours
        estimated_duration_seconds = task.estimated_duration * 3600
        deviation = actual_duration - estimated_duration_seconds
        deviation_percentage = (deviation / estimated_duration_seconds * 100) if estimated_duration_seconds > 0 else 0
        
        # Log the metrics
        logger.info(
            f'Task "{task.title}" (ID: {task_id}) completed | '
            f'Actual Duration: {actual_duration:.2f}s ({actual_duration/60:.2f}m) | '
            f'Estimated Duration: {estimated_duration_seconds:.2f}s ({estimated_duration_seconds/60:.2f}m) | '
            f'Deviation: {deviation:.2f}s ({deviation_percentage:.2f}%)'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Task "{task.title}" completed',
            'execution_id': execution_log.id,
            'task_id': task_id,
            'actual_duration_seconds': round(actual_duration, 2),
            'estimated_duration_seconds': round(estimated_duration_seconds, 2),
            'deviation_seconds': round(deviation, 2),
            'deviation_percentage': round(deviation_percentage, 2)
        }, status=200)
    
    except Task.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Task with id {task_id} not found'
        }, status=404)
    
    except ExecutionLog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'No execution log found for task {task_id}'
        }, status=404)
    
    except Exception as e:
        logger.error(f'Error completing task {task_id}: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while completing the task'
        }, status=500)


@require_http_methods(["POST"])
def skip_task(request, task_id):
    """
    Skip a task by marking its ExecutionLog as skipped.
    """
    try:
        task = Task.objects.get(id=task_id)
        
        # Get the most recent execution log for this task
        execution_log = ExecutionLog.objects.filter(task_id=task).latest('actual_start')
        execution_log.skipped = True
        execution_log.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Task "{task.title}" skipped',
            'execution_id': execution_log.id,
            'task_id': task_id
        }, status=200)
    
    except Task.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Task with id {task_id} not found'
        }, status=404)
    
    except ExecutionLog.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'No execution log found for task {task_id}'
        }, status=404)
    
    except Exception as e:
        logger.error(f'Error skipping task {task_id}: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while skipping the task'
        }, status=500)
