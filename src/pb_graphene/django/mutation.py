import django.db.models, django.forms

from graphene_django.forms.mutation import DjangoModelFormMutation
from graphene_django.forms.converter import convert_form_field, get_form_field_description
from graphene_file_upload.scalars import Upload
from graphene import Scalar, Boolean, Field
from graphene.types.mutation import MutationOptions, Mutation

from pb_graphene import GlobalID

@convert_form_field.register(django.forms.FileField)
def convert_form_field_to_upload(field):
    return Upload(description=get_form_field_description(field), required=field.required)

def _replace_global_ids_with_model_ids(model, data):    
    for field, value in data.items():
        if not hasattr(model, field):
            continue

        model_field = model._meta.get_field(field)

        if isinstance(model_field, (django.db.models.AutoField, django.db.models.ForeignKey)):
            _, data[field] = from_global_id(value)

    return data


def _extract_files(model, data, files=None):
    files = files or {}
    for field, value in dict(data).items():
        if not hasattr(model, field):
            continue

        model_field = model._meta.get_field(field)

        if isinstance(model_field, (django.db.models.FileField,)):
            files[field] = value
            del data[field]

    return data, files

class PlusDjangoModelFormMutation(DjangoModelFormMutation):                
    class Meta:
        abstract = True

    @classmethod
    def get_form_kwargs(cls, root, info, **data):
        data = replace_global_ids_with_model_ids(cls._meta.model, data)
        data, files = _extract_files(cls._meta.model, data)
        kwargs = {"data": data, "files": files}
        
        pk = data.pop("id", None)
        
        if pk:
            instance = cls._meta.model._default_manager.get(pk=pk)
            kwargs["instance"] = instance

        return kwargs


class DeleteDjangoModelOptions(MutationOptions):
    model = None  # type: Type[Model]

class DeleteDjangoModelMutation(Mutation):
    ok = Boolean()

    @classmethod
    def __init_subclass_with_meta__(cls, model=None, **kwargs):
        if "_meta" not in kwargs:
            _meta = DeleteDjangoModelOptions(cls)

        else:
            _meta = kwargs["_meta"]

        _meta.model = model

        super().__init_subclass_with_meta__(
            _meta=_meta, **kwargs
        )


    class Meta:
        abstract = True

    class Arguments:
        id = GlobalID()
    
    @classmethod
    def mutate(cls, root, info, id):
        model = cls._meta.model.objects.get(pk=from_global_id(id)[1])
        model.delete()
        return cls(ok=True)
    