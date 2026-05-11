from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Role, UserProfile
from .functions import get_auto_id

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'auto_id')
    exclude = ('auto_id', 'creator', 'updater', 'is_deleted')

    def save_model(self, request, obj, form, change):
        if not obj.auto_id:
            obj.auto_id = get_auto_id(Role)
        if not change:
            obj.creator = request.user
        else:
            obj.updater = request.user
        super().save_model(request, obj, form, change)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profiles'
    fk_name = 'user'
    exclude = ('auto_id', 'creator', 'updater', 'is_deleted')

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline, )

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(CustomUserAdmin, self).get_inline_instances(request, obj)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if getattr(instance, 'auto_id', None) is None and hasattr(instance, 'auto_id'):
                instance.auto_id = get_auto_id(instance.__class__)
            if hasattr(instance, 'creator') and not change:
                instance.creator = request.user
            if hasattr(instance, 'updater') and change:
                instance.updater = request.user
            instance.save()
        formset.save_m2m()

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
