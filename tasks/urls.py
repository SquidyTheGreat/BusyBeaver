from django.urls import path
from . import views

urlpatterns = [
    path('tasks/<int:task_id>/start/', views.start_task, name='start_task'),
    path('tasks/<int:task_id>/complete/', views.complete_task, name='complete_task'),
    path('tasks/<int:task_id>/skip/', views.skip_task, name='skip_task'),
]
