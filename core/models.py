from django.db import models
from django.contrib.auth.models import User
import uuid

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auto_id = models.PositiveIntegerField(db_index=True, unique=True)
    creator = models.ForeignKey(
        "auth.User", blank=True, null=True,related_name="creator_%(class)s_objects", on_delete=models.CASCADE)
    updater = models.ForeignKey("auth.User", blank=True, null=True,
                                related_name="updater_%(class)s_objects", on_delete=models.CASCADE)
    date_added = models.DateTimeField(db_index=True, auto_now_add=True)
    date_updated = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True

class Role(BaseModel):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class UserProfile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=50, blank=True, null=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, blank=True, null=True)
    company = models.ForeignKey('client_management.Client', on_delete=models.SET_NULL, blank=True, null=True)
    
    def __str__(self):
        return self.user.username



class Processing_Log(models.Model):
    created_by = models.CharField(max_length=20,  blank=True)
    created_date = models.DateTimeField(auto_now_add=True,blank=True, null=True)
   
    description = models.CharField(null=True,max_length=1024)
    
    class Meta:
        ordering = ('-created_date',)

    def __str__(self):
        return f"Processing Log - {self.created_date}"
    