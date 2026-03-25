from django.urls import path
from . import views

urlpatterns = [
    path('', views.schedule_view, name='schedule_view'),
    path('blocks/', views.block_list, name='block_list'),
    path('blocks/new/', views.block_create, name='block_create'),
    path('blocks/<int:block_id>/edit/', views.block_edit, name='block_edit'),
    path('blocks/<int:block_id>/delete/', views.block_delete, name='block_delete'),
    path('run/', views.run_scheduler, name='run_scheduler'),
    path('clear/', views.clear_schedule, name='clear_schedule'),
    path('sync/', views.sync_calendar, name='sync_calendar'),
    path('calendars/', views.calendar_list, name='calendar_list'),
    path('calendars/set/', views.set_calendar, name='set_calendar'),
    path('calendars/set-event/', views.set_event_calendar, name='set_event_calendar'),
]
