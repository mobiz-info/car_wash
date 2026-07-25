import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wash_pilot.settings')
django.setup()

from master.models import ExpenseHead, Expense
from client_management.models import Client
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

def seed_expense_masters():
    print("Seeding default Expense Heads and Expense Items for ALL branches...")
    head_count = 0
    item_count = 0

    companies = list(Client.objects.filter(is_deleted=False))

    for head_name, items in DEFAULT_EXPENSE_HEADS_ITEMS.items():
        # Create global master (company=None)
        global_head, created = ExpenseHead.objects.get_or_create(
            name=head_name,
            company=None,
            is_deleted=False,
            defaults={'auto_id': get_auto_id(ExpenseHead)}
        )
        if created:
            head_count += 1

        # Also ensure company-specific heads exist if any exist
        heads_to_attach = [global_head]
        for comp in companies:
            comp_head, c_created = ExpenseHead.objects.get_or_create(
                name=head_name,
                company=comp,
                is_deleted=False,
                defaults={'auto_id': get_auto_id(ExpenseHead)}
            )
            if c_created:
                head_count += 1
            heads_to_attach.append(comp_head)

        for item_name in items:
            for h in heads_to_attach:
                item, i_created = Expense.objects.get_or_create(
                    expense_head=h,
                    name=item_name,
                    is_deleted=False,
                    defaults={'auto_id': get_auto_id(Expense)}
                )
                if i_created:
                    item_count += 1

    print(f"SUCCESS: Created {head_count} Expense Heads and {item_count} Expense Items across all branches!")

if __name__ == '__main__':
    seed_expense_masters()
