# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'Question.type'
        db.delete_column('za_hansard_question', 'type')

        # Deleting field 'Question.title'
        db.delete_column('za_hansard_question', 'title')

        # Deleting field 'Question.translated'
        db.delete_column('za_hansard_question', 'translated')

        # Deleting field 'Question.number2'
        db.delete_column('za_hansard_question', 'number2')

        # Deleting field 'Question.number1'
        db.delete_column('za_hansard_question', 'number1')

        # Deleting field 'Question.document'
        db.delete_column('za_hansard_question', 'document')

        # Adding field 'Question.written_number'
        db.add_column('za_hansard_question', 'written_number',
                      self.gf('django.db.models.fields.IntegerField')(null=True),
                      keep_default=False)

        # Adding field 'Question.oral_number'
        db.add_column('za_hansard_question', 'oral_number',
                      self.gf('django.db.models.fields.IntegerField')(null=True),
                      keep_default=False)

        # Adding field 'Question.identifier'
        db.add_column('za_hansard_question', 'identifier',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=10),
                      keep_default=False)

        # Adding field 'Question.id_number'
        db.add_column('za_hansard_question', 'id_number',
                      self.gf('django.db.models.fields.IntegerField')(default=0),
                      keep_default=False)

        # Adding field 'Question.house'
        db.add_column('za_hansard_question', 'house',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=1),
                      keep_default=False)

        # Adding field 'Question.answer_type'
        db.add_column('za_hansard_question', 'answer_type',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=1),
                      keep_default=False)

        # Adding field 'Question.year'
        db.add_column('za_hansard_question', 'year',
                      self.gf('django.db.models.fields.IntegerField')(default=0),
                      keep_default=False)

        # Adding field 'Question.date_transferred'
        db.add_column('za_hansard_question', 'date_transferred',
                      self.gf('django.db.models.fields.DateField')(null=True),
                      keep_default=False)

        # Adding unique constraint on 'Question', fields ['id_number', 'house', 'year']
        db.create_unique('za_hansard_question', ['id_number', 'house', 'year'])


    def backwards(self, orm):
        # Removing unique constraint on 'Question', fields ['id_number', 'house', 'year']
        db.delete_unique('za_hansard_question', ['id_number', 'house', 'year'])


        # User chose to not deal with backwards NULL issues for 'Question.type'
        raise RuntimeError("Cannot reverse this migration. 'Question.type' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Question.type'
        db.add_column('za_hansard_question', 'type',
                      self.gf('django.db.models.fields.TextField')(),
                      keep_default=False)


        # User chose to not deal with backwards NULL issues for 'Question.title'
        raise RuntimeError("Cannot reverse this migration. 'Question.title' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Question.title'
        db.add_column('za_hansard_question', 'title',
                      self.gf('django.db.models.fields.TextField')(),
                      keep_default=False)


        # User chose to not deal with backwards NULL issues for 'Question.translated'
        raise RuntimeError("Cannot reverse this migration. 'Question.translated' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Question.translated'
        db.add_column('za_hansard_question', 'translated',
                      self.gf('django.db.models.fields.IntegerField')(),
                      keep_default=False)


        # User chose to not deal with backwards NULL issues for 'Question.number2'
        raise RuntimeError("Cannot reverse this migration. 'Question.number2' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Question.number2'
        db.add_column('za_hansard_question', 'number2',
                      self.gf('django.db.models.fields.TextField')(),
                      keep_default=False)


        # User chose to not deal with backwards NULL issues for 'Question.number1'
        raise RuntimeError("Cannot reverse this migration. 'Question.number1' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Question.number1'
        db.add_column('za_hansard_question', 'number1',
                      self.gf('django.db.models.fields.TextField')(),
                      keep_default=False)


        # User chose to not deal with backwards NULL issues for 'Question.document'
        raise RuntimeError("Cannot reverse this migration. 'Question.document' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'Question.document'
        db.add_column('za_hansard_question', 'document',
                      self.gf('django.db.models.fields.TextField')(),
                      keep_default=False)

        # Deleting field 'Question.written_number'
        db.delete_column('za_hansard_question', 'written_number')

        # Deleting field 'Question.oral_number'
        db.delete_column('za_hansard_question', 'oral_number')

        # Deleting field 'Question.identifier'
        db.delete_column('za_hansard_question', 'identifier')

        # Deleting field 'Question.id_number'
        db.delete_column('za_hansard_question', 'id_number')

        # Deleting field 'Question.house'
        db.delete_column('za_hansard_question', 'house')

        # Deleting field 'Question.answer_type'
        db.delete_column('za_hansard_question', 'answer_type')

        # Deleting field 'Question.year'
        db.delete_column('za_hansard_question', 'year')

        # Deleting field 'Question.date_transferred'
        db.delete_column('za_hansard_question', 'date_transferred')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'instances.instance': {
            'Meta': {'object_name': 'Instance'},
            'created_by': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'created_instances'", 'null': 'True', 'to': "orm['auth.User']"}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('instances.fields.DNSLabelField', [], {'unique': 'True', 'max_length': '63', 'db_index': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'users': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "'instances'", 'blank': 'True', 'to': "orm['auth.User']"})
        },
        'speeches.section': {
            'Meta': {'ordering': "('id',)", 'object_name': 'Section'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'instance': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['instances.Instance']"}),
            'modified': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'parent': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'children'", 'null': 'True', 'to': "orm['speeches.Section']"}),
            'title': ('django.db.models.fields.TextField', [], {})
        },
        'za_hansard.answer': {
            'Meta': {'object_name': 'Answer'},
            'date': ('django.db.models.fields.DateField', [], {}),
            'house': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.TextField', [], {}),
            'name': ('django.db.models.fields.TextField', [], {}),
            'number_oral': ('django.db.models.fields.TextField', [], {}),
            'number_written': ('django.db.models.fields.TextField', [], {}),
            'processed_code': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'type': ('django.db.models.fields.TextField', [], {}),
            'url': ('django.db.models.fields.TextField', [], {})
        },
        'za_hansard.pmgcommitteeappearance': {
            'Meta': {'object_name': 'PMGCommitteeAppearance'},
            'committee': ('django.db.models.fields.TextField', [], {}),
            'committee_url': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'meeting': ('django.db.models.fields.TextField', [], {}),
            'meeting_date': ('django.db.models.fields.DateField', [], {}),
            'meeting_url': ('django.db.models.fields.TextField', [], {}),
            'party': ('django.db.models.fields.TextField', [], {}),
            'person': ('django.db.models.fields.TextField', [], {}),
            'report': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'appearances'", 'null': 'True', 'to': "orm['za_hansard.PMGCommitteeReport']"}),
            'text': ('django.db.models.fields.TextField', [], {})
        },
        'za_hansard.pmgcommitteereport': {
            'Meta': {'object_name': 'PMGCommitteeReport'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_sayit_import': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'meeting_url': ('django.db.models.fields.TextField', [], {}),
            'premium': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'processed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'sayit_section': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['speeches.Section']", 'null': 'True', 'on_delete': 'models.PROTECT', 'blank': 'True'})
        },
        'za_hansard.question': {
            'Meta': {'unique_together': "(('id_number', 'house', 'year'),)", 'object_name': 'Question'},
            'answer': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'question'", 'null': 'True', 'to': "orm['za_hansard.Answer']"}),
            'answer_type': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'askedby': ('django.db.models.fields.TextField', [], {}),
            'date': ('django.db.models.fields.DateField', [], {}),
            'date_transferred': ('django.db.models.fields.DateField', [], {'null': 'True'}),
            'house': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'id_number': ('django.db.models.fields.IntegerField', [], {}),
            'identifier': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'intro': ('django.db.models.fields.TextField', [], {}),
            'last_sayit_import': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'oral_number': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'paper': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['za_hansard.QuestionPaper']", 'null': 'True', 'on_delete': 'models.SET_NULL'}),
            'question': ('django.db.models.fields.TextField', [], {}),
            'questionto': ('django.db.models.fields.TextField', [], {}),
            'sayit_section': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['speeches.Section']", 'null': 'True', 'on_delete': 'models.PROTECT', 'blank': 'True'}),
            'written_number': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'year': ('django.db.models.fields.IntegerField', [], {})
        },
        'za_hansard.questionpaper': {
            'Meta': {'unique_together': "(('year', 'issue_number', 'house', 'parliament_number'),)", 'object_name': 'QuestionPaper'},
            'date_published': ('django.db.models.fields.DateField', [], {}),
            'document_name': ('django.db.models.fields.TextField', [], {'max_length': '32'}),
            'document_number': ('django.db.models.fields.IntegerField', [], {}),
            'house': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'issue_number': ('django.db.models.fields.IntegerField', [], {}),
            'language': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
            'parliament_number': ('django.db.models.fields.IntegerField', [], {}),
            'session_number': ('django.db.models.fields.IntegerField', [], {}),
            'source_url': ('django.db.models.fields.URLField', [], {'max_length': '1000'}),
            'text': ('django.db.models.fields.TextField', [], {}),
            'year': ('django.db.models.fields.IntegerField', [], {})
        },
        'za_hansard.source': {
            'Meta': {'ordering': "['-date', 'document_name']", 'object_name': 'Source'},
            'date': ('django.db.models.fields.DateField', [], {}),
            'document_name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'document_number': ('django.db.models.fields.IntegerField', [], {'unique': 'True'}),
            'house': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is404': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'language': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'last_processing_attempt': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'last_processing_success': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'last_sayit_import': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'sayit_section': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['speeches.Section']", 'null': 'True', 'on_delete': 'models.PROTECT', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '1000'})
        }
    }

    complete_apps = ['za_hansard']