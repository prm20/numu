# numu/serializers.py

from rest_framework import serializers
from .models import Course, Disc, Lesson, Entry, Lexeme


class LexemeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lexeme
        fields = [
            'id',
            'paiute',
            'is_multi_sense',
            'needs_lexeme_review',
        ]


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'description',
            'dialect',
            'writing_system',
            'source',
            'total_pages',
            'notes',
            'sort_order',
        ]


# Kept for backwards compatibility during migration period
class DiscSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disc
        fields = ['id', 'title', 'dialect', 'writing_system', 'total_pages', 'notes']


class LessonSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id',
            'course',
            'lesson_number',
            'title',
            'category',
            'page',
            'section_title',
            'content_tier',
            'notes',
        ]


class EntrySerializer(serializers.ModelSerializer):
    lesson = LessonSerializer(read_only=True)

    class Meta:
        model = Entry
        fields = [
            'id',
            'lesson',
            'content_type',
            'paiute',
            'pronunciation',
            'english',
            'context_note',
            'source_notes',
            'sort_order',
            'metadata',
        ]


class EntryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Entry
        fields = ['id', 'content_type', 'paiute', 'english', 'lesson_id', 'sort_order']


class LexemeDetailSerializer(serializers.ModelSerializer):
    entries = EntryBriefSerializer(many=True, read_only=True)

    class Meta:
        model = Lexeme
        fields = [
            'id',
            'paiute',
            'is_multi_sense',
            'needs_lexeme_review',
            'entries',
        ]