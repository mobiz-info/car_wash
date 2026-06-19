from .models import *
from django.utils import timezone

def get_auto_id(model):
    from django.db.models import Max
    try:
        max_val = model.objects.all().aggregate(Max('auto_id'))['auto_id__max']
        return (max_val or 0) + 1
    except Exception:
        auto_id = 1
        try:
            latest_auto_id =  model.objects.all().order_by("-date_added")[:1]
            if latest_auto_id:
                for auto in latest_auto_id:
                    auto_id = auto.auto_id + 1
        except Exception:
            pass
        return auto_id

def log_activity(created_by, description, created_date=None):
    
    if created_date is None:
        created_date = timezone.now()

    Processing_Log.objects.create(
        created_by=created_by,
        description=description,
        created_date=created_date
    )