from django.db import models
import uuid
# Create your models here.



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
        
        
class Country(BaseModel):
    name = models.CharField(max_length=100)

    def _str_(self):
        return self.name


class State(BaseModel):
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def _str_(self):
        return self.name


class District(BaseModel):
    state = models.ForeignKey(State, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)


class Area(BaseModel):
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

