# numu/views_api.py

from rest_framework import viewsets
from django.db.models import Q
from .models import Course, Lesson, Entry, Lexeme
from .serializers import (
    CourseSerializer,
    LessonSerializer,
    EntrySerializer,
    LexemeSerializer,
    LexemeDetailSerializer,
)


class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for courses (top-level curriculum groupings).
    Replaces /api/discs/ — curriculum-agnostic.

    GET /api/courses/
    GET /api/courses/{id}/
    """
    queryset = Course.objects.all().order_by('sort_order', 'id')
    serializer_class = CourseSerializer


class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for lessons.

    Filters:
      ?course=<id>     filter by course
      ?q=<text>        search lesson titles
    """
    serializer_class = LessonSerializer

    def get_queryset(self):
        qs = Lesson.objects.select_related('course').order_by('lesson_number')

        course_id = self.request.query_params.get('course')
        if course_id is not None:
            qs = qs.filter(course_id=course_id)

        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(title__icontains=q)

        return qs


class EntryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for entries.

    Filters:
      ?lesson=<id>           filter by lesson
      ?course=<id>           filter by course
      ?content_type=<type>   filter by content type (vocabulary, verb_form, etc.)
      ?q=<text>              search paiute or english
    """
    serializer_class = EntrySerializer

    def get_queryset(self):
        qs = Entry.objects.select_related(
            'lesson', 'lesson__course'
        ).order_by('lesson', 'sort_order')

        lesson_id    = self.request.query_params.get('lesson')
        course_id    = self.request.query_params.get('course')
        content_type = self.request.query_params.get('content_type')
        q            = self.request.query_params.get('q')

        if lesson_id is not None:
            qs = qs.filter(lesson_id=lesson_id)

        if course_id is not None:
            qs = qs.filter(lesson__course_id=course_id)

        if content_type is not None:
            qs = qs.filter(content_type=content_type)

        if q:
            qs = qs.filter(
                Q(paiute__icontains=q) | Q(english__icontains=q)
            )

        return qs


class LexemeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for canonical Paiute words.

    Filters:
      ?q=<text>   search paiute or english gloss via entries
    """
    queryset = Lexeme.objects.all().order_by('paiute')
    serializer_class = LexemeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(
                Q(paiute__icontains=q)
                | Q(entries__paiute__icontains=q)
                | Q(entries__english__icontains=q)
            ).distinct()
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LexemeDetailSerializer
        return LexemeSerializer