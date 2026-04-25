from django.db import models
from core.models import BaseModel
from django.core.exceptions import ValidationError
from PIL import Image

def validate_png(image):
    if not image.name.lower().endswith('.png'):
        raise ValidationError("Only PNG images are allowed.")

def validate_image_dimensions(image):
    img = Image.open(image)
    width, height = img.size

    if width != 300 or height != 300:
        raise ValidationError("Image must be exactly 300x300 pixels.")
class Client(BaseModel):
    company_name = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    status = models.BooleanField(default=True)
    gst_number = models.CharField(max_length=100, blank=True, null=True)
    country = models.ForeignKey('master.Country', on_delete=models.SET_NULL, blank=True, null=True)
    state = models.ForeignKey('master.State', on_delete=models.SET_NULL, blank=True, null=True)
    area = models.ForeignKey('master.Area', on_delete=models.SET_NULL, blank=True, null=True)

    logo_color = models.ImageField(
        upload_to='client_logos/color/',
        validators=[validate_png, validate_image_dimensions],
        blank=True,
        null=True
    )

    logo_bw = models.ImageField(
        upload_to='client_logos/bw/',
        validators=[validate_png, validate_image_dimensions],
        blank=True,
        null=True
    )
    
    def __str__(self):
        return f"{self.company_name} ({self.owner_name})"


class Subscription(BaseModel):
    company = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='subscriptions')
    start_date = models.DateField()
    end_date = models.DateField()
    usage_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    no_of_licenses = models.PositiveIntegerField(default=1)

    # Feature flags
    whatsapp_integration = models.BooleanField(default=False)
    bulk_sms = models.BooleanField(default=False)
    email_integration = models.BooleanField(default=False)
    bluetooth_printing = models.BooleanField(default=False)
    tally_integration = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.company.company_name} ({self.start_date} → {self.end_date})"

    @property
    def is_active(self):
        from django.utils import timezone
        return self.start_date <= timezone.now().date() <= self.end_date

