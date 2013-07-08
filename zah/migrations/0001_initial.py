# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Source'
        db.create_table(u'zah_source', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('title', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('document_name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=200)),
            ('document_number', self.gf('django.db.models.fields.IntegerField')(unique=True)),
            ('date', self.gf('django.db.models.fields.DateField')()),
            ('url', self.gf('django.db.models.fields.URLField')(max_length=1000)),
            ('house', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('language', self.gf('django.db.models.fields.CharField')(max_length=200)),
            ('last_processing_attempt', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('last_processing_success', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'zah', ['Source'])


    def backwards(self, orm):
        # Deleting model 'Source'
        db.delete_table(u'zah_source')


    models = {
        u'zah.source': {
            'Meta': {'ordering': "['-date', 'document_name']", 'object_name': 'Source'},
            'date': ('django.db.models.fields.DateField', [], {}),
            'document_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '200'}),
            'document_number': ('django.db.models.fields.IntegerField', [], {'unique': 'True'}),
            'house': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'language': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'last_processing_attempt': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'last_processing_success': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '1000'})
        }
    }

    complete_apps = ['zah']