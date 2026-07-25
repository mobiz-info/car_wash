import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'car_wash.settings')
django.setup()

from master.models import ExpenseHead, Expense

print("=== ALL EXPENSE HEADS IN DB ===")
heads = ExpenseHead.objects.filter(is_deleted=False).order_by('name')
for h in heads:
    items = list(Expense.objects.filter(expense_head=h, is_deleted=False).values_list('name', flat=True))
    print(f"ID: {h.id} | Name: '{h.name}' | Company: {h.company_id} | Items Count: {len(items)}")
    if len(items) > 0:
        print(f"   Items: {items}")
