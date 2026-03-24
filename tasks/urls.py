from django.urls import path
from . import views

urlpatterns = [
    path('', views.task_list, name='task_list'),
    path('tasks/new/', views.task_create, name='task_create'),
    path('tasks/<int:task_id>/', views.task_detail, name='task_detail'),
    path('tasks/<int:task_id>/edit/', views.task_edit, name='task_edit'),
    path('tasks/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('tasks/<int:task_id>/start/', views.task_start, name='task_start'),
    path('tasks/<int:task_id>/complete/', views.task_complete, name='task_complete'),
    path('tasks/<int:task_id>/skip/', views.task_skip, name='task_skip'),
    path('tasks/<int:task_id>/cancel/', views.task_cancel, name='task_cancel'),
    path('labels/', views.label_list, name='label_list'),
    path('labels/new/', views.label_create, name='label_create'),
    path('labels/<int:label_id>/edit/', views.label_edit, name='label_edit'),
    path('labels/<int:label_id>/delete/', views.label_delete, name='label_delete'),
    path('health/', views.health_list, name='health_list'),
    path('health/new/', views.health_create, name='health_create'),
    path('feedback/<uuid:token>/', views.feedback_form, name='feedback_form'),
    path('feedback/<uuid:token>/thanks/', views.feedback_thanks, name='feedback_thanks'),
]
