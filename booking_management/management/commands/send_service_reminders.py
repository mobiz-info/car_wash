from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import re

from booking_management.models import ServiceReminder, SentServiceReminder
from finance_management.models import Invoice
from client_management.models import WhatsAppSetting
from booking_management.api_views import send_whatsapp_simple


class Command(BaseCommand):
    help = 'Send automatic service top-up reminders to customers via WhatsApp'

    def handle(self, *args, **kwargs):
        self.stdout.write("Scanning for service reminders to send...")
        
        today = timezone.now().date()
        reminders = ServiceReminder.objects.filter(is_deleted=False).select_related('service')
        
        sent_count = 0
        
        for reminder in reminders:
            # Target date is X days ago
            target_date = today - timedelta(days=reminder.days_after)
            
            # Find all invoices on the target date for this branch and service
            invoices = Invoice.objects.filter(
                branch=reminder.branch,
                date=target_date,
                items__service=reminder.service,
                is_deleted=False
            ).distinct()
            
            for invoice in invoices:
                # 1. Check if reminder already sent for this invoice-reminder pair
                already_sent = SentServiceReminder.objects.filter(
                    reminder=reminder,
                    invoice=invoice
                ).exists()
                
                if already_sent:
                    continue
                    
                # 2. Check if customer got the same service *after* the target invoice date
                has_newer = Invoice.objects.filter(
                    customer=invoice.customer,
                    date__gt=invoice.date,
                    items__service=reminder.service,
                    is_deleted=False
                ).exists()
                
                if has_newer:
                    # Silence the older reminder since they came back for the service
                    continue
                    
                # 3. Fetch branch/company WhatsApp settings
                company = reminder.branch.company if reminder.branch else None
                setting = None
                if company:
                    setting = WhatsAppSetting.objects.filter(company=company, is_deleted=False).first()
                    
                if not setting or not setting.username or not setting.password:
                    continue
                    
                # 4. Clean phone number
                phone_to_send = invoice.customer.phone or invoice.customer.whatsapp_number
                if not phone_to_send:
                    continue
                    
                cleaned_phone = re.sub(r'\D', '', str(phone_to_send))
                if cleaned_phone.startswith('0'):
                    cleaned_phone = cleaned_phone[1:]
                    
                # 5. Format message text (fallback/unofficial)
                customer_name = invoice.customer.name or "Customer"
                vehicle_no = invoice.vehicle.vehicle_number if invoice.vehicle else "your vehicle"
                service_name = reminder.service.name
                
                message = reminder.reminder_message.replace('{customer_name}', customer_name) \
                                                    .replace('{vehicle_number}', vehicle_no) \
                                                    .replace('{service_name}', service_name)
                
                # 6. Send the message
                try:
                    # Send custom text using the company's WhatsApp setting
                    send_whatsapp_simple(
                        to_number=cleaned_phone,
                        message=message,
                        setting=setting
                    )
                        
                    # 7. Record that reminder was successfully dispatched
                    SentServiceReminder.objects.create(
                        reminder=reminder,
                        invoice=invoice
                    )
                    sent_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Successfully sent service reminder to {customer_name} ({cleaned_phone}) for {service_name}"
                    ))
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"Failed to send reminder for invoice {invoice.id}: {str(e)}"
                    ))
                    
        self.stdout.write(self.style.SUCCESS(f"Finished sending service reminders. Sent count: {sent_count}"))
