"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# config/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from numu.views_api import DiscViewSet, LessonViewSet, EntryViewSet, LexemeViewSet


router = DefaultRouter()
router.register(r'discs', DiscViewSet, basename='disc')
router.register(r'lessons', LessonViewSet, basename='lesson')
router.register(r'entries', EntryViewSet, basename='entry')
router.register(r'lexemes', LexemeViewSet, basename='lexeme')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),  # all API endpoints under /api/
]

