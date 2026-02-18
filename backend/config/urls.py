# config/urls.py

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from numu.views_api import CourseViewSet, LessonViewSet, EntryViewSet, LexemeViewSet

router = DefaultRouter()
router.register(r'courses',  CourseViewSet,  basename='course')
router.register(r'lessons',  LessonViewSet,  basename='lesson')
router.register(r'entries',  EntryViewSet,   basename='entry')
router.register(r'lexemes',  LexemeViewSet,  basename='lexeme')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
]