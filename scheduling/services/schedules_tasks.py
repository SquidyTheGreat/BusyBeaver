from tasks.models import Task, ScheduleBlock
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class ScheduleTask:

    @staticmethod
    @transaction.atomic
    def create_schedule(tasks, available_time_blocks):
        """
        Create schedule by assigning tasks to available time blocks.
        Algorithm:
        1. Sort tasks by priority (ascending), then by duration (descending)
        2. For each task, find the best available time block that fits it
        3. Create ScheduleBlock entries for scheduled tasks
        4. Respect time blocks > priority (time blocks are immutable)
        
        Args:
            tasks (list): List of Task objects to be scheduled
            available_time_blocks (list): List of time block dicts with 'start_time' and 'end_time'
            
        Returns:
            dict: Contains scheduling results with created blocks, unscheduled tasks, and metrics
        """
        try:
            if not tasks or not available_time_blocks:
                return {
                    'success': True,
                    'created_blocks': [],
                    'scheduled_count': 0,
                    'unscheduled_tasks': [],
                    'message': 'No tasks or time blocks provided'
                }
            
            # Sort tasks: by priority (ascending), then by duration (descending)
            sorted_tasks = sorted(
                tasks,
                key=lambda t: (t.priority, -t.estimated_duration)
            )
            
            # Track availability in time blocks (we'll mark used portions)
            time_blocks_availability = []
            for block in available_time_blocks:
                time_blocks_availability.append({
                    'start_time': block.get('start_time') or block.start_time,
                    'end_time': block.get('end_time') or block.end_time,
                    'remaining_time': (block.get('end_time') or block.end_time) - (block.get('start_time') or block.start_time),
                    'original_block': block,
                    'scheduled_tasks': []
                })
            
            created_schedule_blocks = []
            unscheduled_tasks = []
            
            # Try to schedule each task
            for task in sorted_tasks:
                # Convert estimated_duration from hours to seconds
                task_duration_seconds = task.estimated_duration * 3600
                scheduled = False
                
                # Find the best available time block for this task
                for block_availability in time_blocks_availability:
                    # Check if task fits in this block's remaining time
                    if block_availability['remaining_time'].total_seconds() >= task_duration_seconds:
                        # Schedule the task
                        schedule_start = block_availability['start_time']
                        
                        # Adjust start time based on already scheduled tasks in this block
                        for scheduled_task in block_availability['scheduled_tasks']:
                            schedule_start = max(schedule_start, scheduled_task['end_time'])
                        
                        schedule_end = schedule_start + timezone.timedelta(seconds=task_duration_seconds)
                        
                        # Verify it still fits in the block
                        if schedule_end <= block_availability['end_time']:
                            # Create ScheduleBlock
                            schedule_block = ScheduleBlock(
                                task_id=task,
                                start_time=schedule_start,
                                end_time=schedule_end,
                                calender_event_id=f'task_{task.id}_{schedule_start.timestamp()}'
                            )
                            schedule_block.save()
                            created_schedule_blocks.append(schedule_block)
                            
                            # Update availability
                            block_availability['remaining_time'] = block_availability['end_time'] - schedule_end
                            block_availability['scheduled_tasks'].append({
                                'task_id': task.id,
                                'start_time': schedule_start,
                                'end_time': schedule_end
                            })
                            
                            scheduled = True
                            logger.info(
                                f'Scheduled task {task.id} ({task.title}) from {schedule_start} to {schedule_end}'
                            )
                            break
                
                if not scheduled:
                    unscheduled_tasks.append({
                        'task_id': task.id,
                        'task_title': task.title,
                        'priority': task.priority,
                        'estimated_duration_hours': task.estimated_duration,
                        'reason': 'Insufficient available time in time blocks'
                    })
                    logger.warning(f'Could not schedule task {task.id} ({task.title})')
            
            logger.info(
                f'Schedule creation completed: {len(created_schedule_blocks)} tasks scheduled, '
                f'{len(unscheduled_tasks)} tasks unscheduled'
            )
            
            return {
                'success': True,
                'created_blocks': created_schedule_blocks,
                'scheduled_count': len(created_schedule_blocks),
                'unscheduled_tasks': unscheduled_tasks,
                'unscheduled_count': len(unscheduled_tasks),
                'total_tasks': len(tasks),
                'scheduling_percentage': round((len(created_schedule_blocks) / len(tasks) * 100), 2) if tasks else 0
            }
        
        except Exception as e:
            logger.error(f'Error creating schedule: {str(e)}')
            return {
                'success': False,
                'error': 'An error occurred while creating the schedule',
                'details': str(e)
            }