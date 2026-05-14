from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from your_app.models import Subscription, SubscriptionNotification


class Command(BaseCommand):
    help = 'Check subscription renewal dates'

    def handle(self, *args, **kwargs):

        today = timezone.now().date()

        reminder_days = [7, 3, 1, 0]

        for days in reminder_days:

            target_date = today + timedelta(days=days)

            subscriptions = Subscription.objects.filter(
                end_date=target_date
            )

            for subscription in subscriptions:

                if days == 0:
                    message = (
                        f"{subscription.company.company_name} "
                        f"subscription expired today."
                    )

                elif days == 1:
                    message = (
                        f"{subscription.company.company_name} "
                        f"subscription will expire tomorrow."
                    )

                else:
                    message = (
                        f"{subscription.company.company_name} "
                        f"subscription will expire in {days} days."
                    )

                already_exists = SubscriptionNotification.objects.filter(
                    subscription=subscription,
                    message=message
                ).exists()

                if not already_exists:

                    SubscriptionNotification.objects.create(
                        subscription=subscription,
                        message=message,
                        is_sent=True
                    )

                    self.stdout.write(
                        self.style.SUCCESS(message)
                    )