# Submission admin interface

from django.contrib.admin import SimpleListFilter, ModelAdmin
from django.utils.translation import ugettext_lazy as _
from django import forms
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from opensubmit.models import inform_student, tutor_courses, Assignment, Submission, SubmissionFile, SubmissionTestResult

def authors(submission):
    ''' The list of authors als text, for submission list overview.'''
    return ",\n".join([author.get_full_name() for author in submission.authors.all()])

def course(obj):
    ''' The course name as string.'''
    return obj.assignment.course

def grading_notes(submission):
    ''' Determines if the submission has grading notes,
        leads to nice little icon in the submission overview.
    '''
    if submission.grading_notes is not None:
        return len(submission.grading_notes) > 0
    else:
        return False
grading_notes.boolean = True            # show nice little icon

def grading_file(submission):
    ''' Determines if the submission has a grading file,
        leads to nice little icon in the submission overview.
    '''
    if submission.grading_file.name:
        return True
    else:
        return False
grading_file.boolean = True            # show nice little icon

def test_results(submission):
    return "Foo"

class SubmissionStateFilter(SimpleListFilter):

    ''' This custom filter allows to filter the submissions according to their state.
        Additionally, only submissions the user is tutor for are shown.
    '''
    title = _('Submission Status')
    parameter_name = 'statefilter'

    def lookups(self, request, model_admin):
        return (
            ('tobegraded', _('To be graded')),
            ('graded', _('Grading finished')),
        )

    def queryset(self, request, qs):
        qs = qs.filter(assignment__course__in=tutor_courses(request.user))
        if self.value() == 'tobegraded':
            return qs.filter(state__in=[Submission.GRADING_IN_PROGRESS, Submission.SUBMITTED_TESTED, Submission.TEST_FULL_FAILED, Submission.SUBMITTED])
        elif self.value() == 'graded':
            return qs.filter(state__in=[Submission.GRADED])
        else:
            return qs


class SubmissionAssignmentFilter(SimpleListFilter):

    ''' This custom filter allows to filter the submissions according to their
        assignment. Only submissions from courses were the user is tutor are
        considered.
    '''
    title = _('Assignment')
    parameter_name = 'assignmentfilter'

    def lookups(self, request, model_admin):
        tutor_assignments = Assignment.objects.filter(course__in=tutor_courses(request.user))
        return ((ass.pk, ass.title) for ass in tutor_assignments)

    def queryset(self, request, qs):
        if self.value():
            return qs.filter(assignment__exact=self.value())
        else:
            return qs.filter(assignment__course__in=tutor_courses(request.user))


class SubmissionCourseFilter(SimpleListFilter):

    ''' This custom filter allows to filter the submissions according to
        the course they belong to. Additionally, only submission that the
        user is a tutor for are returned in any of the filter settings.
    '''
    title = _('Course')
    parameter_name = 'coursefilter'

    def lookups(self, request, model_admin):
        return ((c.pk, c.title) for c in tutor_courses(request.user))

    def queryset(self, request, qs):
        if self.value():
            return qs.filter(assignment__course__exact=self.value())
        else:
            return qs.filter(assignment__course__in=tutor_courses(request.user))

class SubmissionAdmin(ModelAdmin):

    ''' This is our version of the admin view for a single submission.
    '''
    list_display = ['__unicode__', 'created', 'submitter', authors, course, 'assignment', 'state', 'grading', grading_notes, grading_file]
    list_filter = (SubmissionStateFilter, SubmissionCourseFilter, SubmissionAssignmentFilter)
    filter_horizontal = ('authors',)
    actions = ['setInitialStateAction', 'setFullPendingStateAction', 'closeAndNotifyAction', 'notifyAction', 'getPerformanceResultsAction']

    fieldsets = (
            ('', 
                {'fields': ('assignment',),}),
            ('Authors', 
                {   'fields': ('authors','submitter'),
                    'classes': ('grp-collapse grp-closed',)
                }),
            ('Submission and test results',
                {   'fields': ('notes',('file_link','file_upload'),'compile_result','validation_result','fulltest_result'),
                }),
            ('Grading',
                {'fields': ('grading_status', 'grading', 'grading_notes', 'grading_file',),}),
    )

    def file_link(self, instance):
        sfile = instance.file_upload
        if not sfile:
            return mark_safe(u'No file submitted by student.')
        else:
            return mark_safe(u'<a href="%s">%s</a>' % (sfile.get_absolute_url(), sfile.basename()))
    file_link.short_description = "Stored upload"


    def _render_test_result(self, result_obj, enabled):
        if not result_obj:
            if enabled:
                return mark_safe(u'Enabled, no results.')
            else:
                return mark_safe(u'Not enabled.')                
        else:
            return format_html("Test output from {0}:<br/><pre>{1}</pre>", result_obj.machine, result_obj.result)

    def compile_result(self, instance):
        result_obj = instance.get_compile_result()
        return self._render_test_result(result_obj, instance.assignment.attachment_test_compile)
    compile_result.short_description = "Compilation test"
    compile_result.allow_tags = True

    def validation_result(self, instance):
        result_obj = instance.get_validation_result()
        return self._render_test_result(result_obj, instance.assignment.attachment_test_validity)
    validation_result.short_description = "Validation test"
    validation_result.allow_tags = True

    def fulltest_result(self, instance):
        result_obj = instance.get_fulltest_result()
        return self._render_test_result(result_obj, instance.assignment.attachment_test_full)
    fulltest_result.short_description = "Full test"
    fulltest_result.allow_tags = True

    def grading_status(self, instance):
        return mark_safe(u'''<input type="radio" name="newstate" value="unfinished">Grading not finished</input>
                        <input type="radio" name="newstate" value="finished">Grading finished</input>
        ''')
    grading_status.short_description = "Status"


    def get_queryset(self, request):
        ''' Restrict the listed submission for the current user.'''
        qs = super(SubmissionAdmin, self).get_queryset(request)
        if request.user.is_superuser:
            return qs
        else:
            return qs.filter(Q(assignment__course__tutors__pk=request.user.pk) | Q(assignment__course__owner=request.user)).distinct()

    def get_readonly_fields(self, request, obj=None):
        ''' Make some of the form fields read-only, but only if the view used to
            modify an existing submission. Overriding the ModelAdmin getter
            is the documented way to do that.
        '''
        # Pseudo-fields generated by functions always must show up in the readonly list
        pseudo_fields = ('file_link', 'compile_result', 'validation_result','fulltest_result', 'grading_status')
        if obj:
            return ('assignment', 'submitter', 'notes')+pseudo_fields
        else:
            # New manual submission
            return pseudo_fields

    def formfield_for_dbfield(self, db_field, **kwargs):
        ''' Offer grading choices from the assignment definition as potential form
            field values for 'grading'.
            When no object is given in the form, the this is a new manual submission
        '''
        if hasattr(self, 'obj'):
            if self.obj and db_field.name == "grading":
                kwargs['queryset'] = self.obj.assignment.gradingScheme.gradings

        return super(SubmissionAdmin, self).formfield_for_dbfield(db_field, **kwargs)

    def save_model(self, request, obj, form, change):
        ''' Our custom addition to the view HTML in templates/admin/opensubmit/submission/change_form.HTML
            adds an easy radio button choice for the new state. This is meant to be for tutors.
            We need to peel this choice from the form data and set the state accordingly.
            The radio buttons have no default, so that we can keep the existing state
            if the user makes no explicit choice.
            Everything else can be managed as prepared by the framework.
        '''
        if 'newstate' in request.POST:
            if request.POST['newstate'] == 'finished':
                obj.state = Submission.GRADED
            elif request.POST['newstate'] == 'unfinished':
                obj.state = Submission.GRADING_IN_PROGRESS
        obj.save()

    def setInitialStateAction(self, request, queryset):
        for subm in queryset:
            subm.state = subm.get_initial_state()
            subm.save()
    setInitialStateAction.short_description = "Mark as new incoming submission"

    def setFullPendingStateAction(self, request, queryset):
        # do not restart tests for withdrawn solutions, or for solutions in the middle of grading
        qs = queryset.filter(Q(state=Submission.SUBMITTED_TESTED) | Q(state=Submission.TEST_FULL_FAILED) | Q(state=Submission.CLOSED))
        numchanged = 0
        for subm in qs:
            if subm.assignment.has_full_test():
                if subm.state == Submission.CLOSED:
                    subm.state = Submission.CLOSED_TEST_FULL_PENDING
                else:
                    subm.state = Submission.TEST_FULL_PENDING
                subm.save()
                numchanged += 1
        if numchanged == 0:
            self.message_user(request, "Nothing changed, no testable submission found.")
        else:
            self.message_user(request, "Changed status of %u submissions." % numchanged)
    setFullPendingStateAction.short_description = "Restart full test without notification"

    def closeAndNotifyAction(self, request, queryset):
        ''' Close all submissions were the tutor sayed that the grading is finished,
            and inform the student. CLosing only graded submissions is a safeguard,
            since backend users tend to checkbox-mark all submissions without thinking.
        '''
        mails = []
        qs = queryset.filter(Q(state=Submission.GRADED))
        for subm in qs:
            inform_student(subm, Submission.CLOSED)
            mails.append(str(subm.pk))
        qs.update(state=Submission.CLOSED)      # works in bulk because inform_student never fails
        if len(mails) == 0:
            self.message_user(request, "Nothing closed, no mails sent.")
        else:
            self.message_user(request, "Mail sent for submissions: " + ",".join(mails))
    closeAndNotifyAction.short_description = "Close graded submissions + send notification"

    # ToDo: Must be refactored to consider new performance data storage model
    # def getPerformanceResultsAction(self, request, queryset):
    #     qs = queryset.exclude(state=Submission.WITHDRAWN)  # avoid accidental addition of withdrawn solutions
    #     response = HttpResponse(content_type="text/csv")
    #     response.write("Submission ID;Course;Assignment;Authors;Performance Data\n")
    #     for subm in qs:
    #         if subm.file_upload and subm.file_upload.perf_data is not None:
    #             auth = ", ".join([author.get_full_name() for author in subm.authors.all()])
    #             response.write("%u;%s;%s;%s;" % (subm.pk, course(subm), subm.assignment, auth))
    #             response.write(subm.file_upload.perf_data)
    #             response.write("\n")
    #     return response
    # getPerformanceResultsAction.short_description = "Download performance data as CSV"

