from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tasks.urls')),
    path('schedule/', include('scheduling.urls')),
    path('analytics/', include('analytics.urls')),
    path('auth/', include('scheduling.auth_urls')),
]
