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
