import tempfile

from django.contrib import admin, messages
from django.core import urlresolvers
from django.conf.urls import patterns, url
from django.shortcuts import redirect
from django import forms

from za_hansard.models import Question
from za_hansard import question_scraper


class CustomQuestionForm(forms.ModelForm):
    answer_text = forms.CharField(required=False, widget=forms.widgets.Textarea(attrs={
        'class': 'vLargeTextField',
    }))

    def __init__(self, *args, **kwargs):
        super(CustomQuestionForm, self).__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance:
            if instance.answer:
                self.initial['answer_text'] = instance.answer.text
            else:
                self.fields['answer_text'].widget.attrs['disabled'] = True

    def save(self, commit=True):
        instance = super(CustomQuestionForm, self).save(commit)
        if instance.answer:
            instance.answer.text = self.cleaned_data['answer_text']
            instance.answer.save()

        return instance


class QuestionAdmin(admin.ModelAdmin):
    date_hierarchy = 'date'
    list_display = ('date', 'house', 'written_number', 'oral_number', 'president_number', 'dp_number', 'answered')
    list_filter = ('house',)
    form = CustomQuestionForm

    fieldsets = (
        (None, {
            'fields': (('date', 'year'), 'house', 'written_number', 'oral_number', 'president_number', 'dp_number',
                       ('identifier', 'id_number')),
        }),
        ('Question', {
            'fields': ('intro', 'askedby', 'questionto', 'question', ),
        }),
        ('Answer', {
            'fields': ('answer_text', 'answer_type', 'answer'),
        }),
        ('Advanced', {
            'classes': ('collapse',),
            'fields': ('date_transferred', 'translated', 'paper', 'last_sayit_import', 'sayit_section',)
        }),
    )

    change_list_template = 'admin/za_hansard/question/change_list.html'

    def answered(self, obj):
        return bool(obj.answer)
    answered.short_description = 'Answered?'

    def get_urls(self):
        urls = super(QuestionAdmin, self).get_urls()
        return patterns('', url(r'upload/$', self.upload)) + urls

    def upload(self, request):
        """ Allow the user to upload a new answer file, and process it.
        """
        if 'file' in request.FILES:
            file = request.FILES['file']

            # save the file to disk
            with tempfile.NamedTemporaryFile() as tmp:
                for chunk in file.chunks():
                    tmp.write(chunk)
                tmp.flush()

                # parse the uploaded file
                scraper = question_scraper.AnswerScraper()
                try:
                    answer = scraper.import_question_answer_from_file(tmp.name, name=file.name)
                    return redirect(urlresolvers.reverse('admin:za_hansard_question_change', args=(answer.question.id,)))
                except Exception as e:
                    messages.error(request, "Couldn't process the uploaded file: %s" % e.message)

        return redirect(urlresolvers.reverse('admin:za_hansard_question_changelist'))


admin.site.register(Question, QuestionAdmin)
