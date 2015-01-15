from django.db import models
import ast
import json


class JsonListField(models.TextField):
    __metaclass__ = models.SubfieldBase
    description = "Stores a python list"

    def __init__(self, *args, **kwargs):
        super(JsonListField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if not value:
            value = []

        if isinstance(value, list):
            return value

        try:
            return json.loads(value)
        except ValueError:
            return []

    def validate(self, value, *args, **kwargs):
        pass
        if isinstance(value, list) or isinstance(value, unicode):
            return True

    def get_prep_value(self, value):
        if value is None:
            return value

        if not isinstance(value, list):
            value = []

        if any([isinstance(elem, unicode) for elem in value]):
            value = [unicode(elem) for elem in value]

        return json.dumps(value)

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_db_prep_value(value)
