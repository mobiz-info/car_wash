import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wash_pilot.settings')
django.setup()

from master.models import ExpenseHead, Expense
from client_management.models import Stock
from core.functions import get_auto_id

DEFAULT_EXPENSE_HEADS_ITEMS = {
    "Purchase": [
        "Cleaning Consumables",
        "Polish & Wax Materials",
        "Tyres",
        "Tubes",
        "Rims",
        "Wheels",
        "Tyre Polish",
        "Protection films",
        "Machinery and Tools",
        "Steam Cleaning Materials",
        "Equipment Spare Parts",
        "Paper Mats",
        "Air Freshener Supplies",
        "Protective Coatings & Sealants",
        "Uniforms and gears",
        "Interior Cleaning Products",
    ],
    "Salary & Wages": [
        "Salary",
        "Wage",
        "Commission",
        "Settlement",
        "Salary advance",
    ],
    "Stationery & Office Supplies": [
        "Paper Rolls",
        "Printer",
        "Perfumes",
        "Mats",
    ],
    "Operational Expenses": [
        "Tissue Papers",
        "Cleaning Towels",
        "Cleaning Solutions",
        "Uniforms",
        "Vehicle",
        "Vehicle Fuel",
        "Rent",
        "Uniform Cleaning & Laundry",
        "Pest Control & Hygiene",
        "Toiletries",
        "Customer Waiting Area Expenses",
        "Software",
        "Server",
        "Sms and Whats app",
    ],
    "Utilities (Water & Electricity)": [
        "Electricity & Water",
    ],
    "Advertisement & Marketing": [
        "Social Media",
        "Print Media",
        "Radio",
    ],
    "Licenses & Permits": [
        "Business License",
        "Establishment Card",
        "Visa",
        "Entry Permit",
        "Health Cards",
        "Vehicle permit",
    ],
    "Renewals & Subscriptions": [
        "License",
        "Establishment card",
        "Insurance",
    ],
    "Travel & Transportation": [
        "Air Ticket",
        "Taxi",
        "Bus",
    ],
    "Refreshments": [
        "Drinking Water",
        "Food and Beverages",
    ],
    "Visa & Staff Processing": [
        "Staff visa",
        "Staff Accommodation",
        "Staff insurance",
        "Medicines",
    ],
    "Audit & Accounting": [
        "Tax Filing",
        "Audit",
    ],
    "Machinery & Tools": [
        "Spanners",
        "Pressure washer",
        "Brush",
        "Sponge",
    ],
    "Maintenance Services": [
        "Equipment Maintenance",
        "AC Service",
        "Plumbing",
        "Electrical works",
        "Painting",
    ],
    "Waste Water Treatment / Disposal": [
        "Waste Disposal",
        "Waste packing materials",
    ],
}

def clean_and_seed_expense_masters():
    print("Cleaning duplicate ExpenseHeads and seeding master ExpenseItems...")
    
    # 1. Ensure Global ExpenseHeads (company=None) exist for all master names
    global_heads = {}
    for head_name in DEFAULT_EXPENSE_HEADS_ITEMS.keys():
        head, _ = ExpenseHead.objects.get_or_create(
            name=head_name,
            company=None,
            is_deleted=False,
            defaults={'auto_id': get_auto_id(ExpenseHead)}
        )
        global_heads[head_name.strip().lower()] = head

    # 2. Re-point Expenses and Stocks attached to duplicate company-specific heads to the global head, then mark duplicates deleted
    for head_name_lower, global_head in global_heads.items():
        duplicate_heads = ExpenseHead.objects.filter(
            name__iexact=global_head.name,
            is_deleted=False
        ).exclude(id=global_head.id)
        
        for dup in duplicate_heads:
            Expense.objects.filter(expense_head=dup).update(expense_head=global_head)
            Stock.objects.filter(expense_head=dup).update(expense_head=global_head)
            ExpenseHead.objects.filter(id=dup.id).update(is_deleted=True)
            print(f"Merged duplicate head '{dup.name}' (ID: {dup.id}) into global head (ID: {global_head.id})")

    # 3. Seed and deduplicate ExpenseItems under the global heads
    item_count = 0
    for head_name, items in DEFAULT_EXPENSE_HEADS_ITEMS.items():
        head = global_heads[head_name.strip().lower()]
        for item_name in items:
            existing = Expense.objects.filter(expense_head=head, name__iexact=item_name, is_deleted=False)
            if existing.exists():
                keep = existing.first()
                for extra in existing.exclude(id=keep.id):
                    extra.is_deleted = True
                    extra.save()
            else:
                Expense.objects.create(
                    expense_head=head,
                    name=item_name,
                    auto_id=get_auto_id(Expense)
                )
                item_count += 1

    print(f"SUCCESS: Cleaned duplicates and ensured unique Expense Items under global Expense Heads!")

if __name__ == '__main__':
    clean_and_seed_expense_masters()
