# Assignment admin interface
from opensubmit.settings import NOVA

from django.contrib.admin import ModelAdmin
from django.forms import ModelForm, MultipleChoiceField, ChoiceField, Select, CheckboxSelectMultiple
from django.db.models.query import EmptyQuerySet
from django.db.models import Q
from opensubmit.models import Course, Assignment


def course(obj):
	''' Course name as string.'''
	return str(obj.course)


class AssignmentForm(ModelForm):
	class Meta:
		model = Assignment
	
	def __init__(self, *args, **kwargs):
		super(ModelForm, self).__init__(*args, **kwargs)
		self.fields['nova_flavor'] = ChoiceField(widget=Select, choices=self.get_flavors(), required=False)
		self.fields['nova_image'] = ChoiceField(widget=Select, choices=self.get_images(), required=False)
		self.fields['nova_network'] = ChoiceField(widget=Select, choices=self.get_networks(), required=False)
		self.fields['nova_security_groups'] = MultipleChoiceField(widget=CheckboxSelectMultiple, choices=self.get_security_groups(), required=False)

	def get_flavors(self):
		return [(None, '-')] + [(f.id, f.name) for f in NOVA.flavors.list()]
	
	def get_images(self):
		return [(None, '-')] + [(f.id, f.name) for f in NOVA.images.list()]
	
	def get_networks(self):
		return [(None, '-')] + [(f.id, f.label) for f in NOVA.networks.list()]
	
	def get_security_groups(self):
		return [(f.name, u"<{}> ({})".format(f.name, f.description)) for f in NOVA.security_groups.list()]


class AssignmentAdmin(ModelAdmin):
	list_display = ['__unicode__', course, 'has_attachment', 'soft_deadline', 'hard_deadline', 'gradingScheme', 'nova_flavor', 'nova_image', 'nova_network', 'nova_security_groups', ]
	form = AssignmentForm

	def get_queryset(self, request):
		''' Restrict the listed assignments for the current user.'''
		qs = super(AssignmentAdmin, self).get_queryset(request)
		if request.user.is_superuser:
			return qs
		else:
			return qs.filter(Q(course__tutors__pk=request.user.pk) | Q(course__owner=request.user)).distinct()

	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		if db_field.name == "course":
			kwargs["queryset"] = Course.objects.filter(active=True)
		return super(AssignmentAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)
	
