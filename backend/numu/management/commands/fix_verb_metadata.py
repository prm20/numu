# numu/management/commands/fix_verb_metadata.py

import json
import os
from django.core.management.base import BaseCommand
from numu.models import Entry, Lesson


class Command(BaseCommand):
    help = 'Update verb form entries with metadata from JSON source'

    def handle(self, *args, **options):
        json_dir = os.path.join(os.path.dirname(__file__), '../../..', 'json')
        
        stats = {
            'verb_forms_updated': 0,
            'verb_phrases_updated': 0,
        }
        
        for disc_num in [1, 2, 3, 4]:
            json_path = os.path.join(json_dir, f'numu_disc{disc_num}.json')
            
            if not os.path.exists(json_path):
                self.stdout.write(self.style.WARNING(f'Skipping {json_path} (not found)'))
                continue
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for lesson_data in data['lessons']:
                lesson_num = lesson_data['lesson_number']
                
                try:
                    lesson = Lesson.objects.get(lesson_number=lesson_num)
                except Lesson.DoesNotExist:
                    continue
                
                # Update verb_forms
                for vf in lesson_data.get('verb_forms', []):
                    paiute = vf['paiute']
                    
                    # Find the Entry row
                    try:
                        entry = Entry.objects.get(
                            lesson=lesson,
                            paiute=paiute,
                            content_type='verb_form'
                        )
                        
                        # Update fields
                        entry.english = vf.get('gloss', '')
                        
                        metadata = {}
                        if vf.get('grammatical_note'):
                            metadata['grammatical_note'] = vf['grammatical_note']
                        if vf.get('example_sentence'):
                            metadata['example_sentence'] = vf['example_sentence']
                        
                        entry.metadata = metadata
                        entry.save(update_fields=['english', 'metadata'])
                        stats['verb_forms_updated'] += 1
                        
                    except Entry.DoesNotExist:
                        self.stdout.write(
                            self.style.WARNING(f'Entry not found: L{lesson_num} {paiute}')
                        )
                    except Entry.MultipleObjectsReturned:
                        self.stdout.write(
                            self.style.ERROR(f'Multiple entries found: L{lesson_num} {paiute}')
                        )
                
                # Update phrase_forms if they exist
                for pf in lesson_data.get('phrase_forms', []):
                    paiute = pf['paiute']
                    
                    try:
                        entry = Entry.objects.get(
                            lesson=lesson,
                            paiute=paiute,
                            content_type='verb_phrase'
                        )
                        
                        # phrase_forms just have paiute and english
                        entry.english = pf.get('english', '')
                        entry.save(update_fields=['english'])
                        stats['verb_phrases_updated'] += 1
                        
                    except Entry.DoesNotExist:
                        pass
                    except Entry.MultipleObjectsReturned:
                        self.stdout.write(
                            self.style.ERROR(f'Multiple entries found: L{lesson_num} {paiute}')
                        )
        
        self.stdout.write(self.style.SUCCESS(f"\nFixed verb metadata:"))
        self.stdout.write(f"  verb_forms: {stats['verb_forms_updated']}")
        self.stdout.write(f"  verb_phrases: {stats['verb_phrases_updated']}")