# numu/views_api.py

from rest_framework import viewsets
from .models import Disc, Lesson, Entry, Lexeme
from .serializers import DiscSerializer, LessonSerializer, EntrySerializer, LexemeSerializer, LexemeDetailSerializer
from rest_framework import viewsets
from django.db.models import Q

class LexemeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for canonical Paiute words.
    Optional filters:
      - ?q=<text>   (search paiute or english gloss via entries)
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
        # For list: use the simple serializer (no nested entries)
        if self.action == 'list':
            return LexemeSerializer
        # For retrieve: include related entries (dictionary-style detail view)
        if self.action == 'retrieve':
            return LexemeDetailSerializer
        return super().get_serializer_class()



class DiscViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for discs.
    """
    queryset = Disc.objects.all().order_by('id')
    serializer_class = DiscSerializer


class LessonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for lessons.
    Optional filter by disc: /api/lessons/?disc=1
    """
    serializer_class = LessonSerializer

    def get_queryset(self):
        qs = Lesson.objects.all().order_by('lesson_number')
        disc_id = self.request.query_params.get('disc')
        if disc_id is not None:
            qs = qs.filter(disc_id=disc_id)
        return qs


class EntryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API for entries.
    Optional filters:
      - by lesson: /api/entries/?lesson=10
      - by disc:   /api/entries/?disc=1
    """
    serializer_class = EntrySerializer

    def get_queryset(self):
        qs = Entry.objects.all().order_by('lesson', 'sort_order')
        lesson_id = self.request.query_params.get('lesson')
        disc_id = self.request.query_params.get('disc')

        if lesson_id is not None:
            qs = qs.filter(lesson_id=lesson_id)

        if disc_id is not None:
            qs = qs.filter(lesson__disc_id=disc_id)

        return qs
