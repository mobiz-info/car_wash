from decimal import Decimal
from django.db.models import Sum
from core.functions import get_auto_id

def process_purchase_invoice_save(purchase_invoice, creator_user=None):
    """Executes the senior's 4-way system sync upon saving a PurchaseInvoice:
    1. Stock Inventory: Increments Stock.quantity in base units (quantity * conversion_count).
    2. Expense Entry: Automatically creates/updates ExpenseEntry under 'Purchase' ExpenseHead.
    3. Supplier Payables: Recalculates and updates Supplier's total outstanding balance.
    4. Payments: Tracks amount paid.
    """
    from master.models import ExpenseHead, Expense, ExpenseEntry, Supplier
    from client_management.models import Stock

    # 1. Increment Stock Quantities
    for item in purchase_invoice.items.filter(is_deleted=False):
        if item.stock_item:
            qty = Decimal(str(item.quantity or 0))
            conv = Decimal(str(item.conversion_count or 1))
            added_qty = qty * conv
            
            stock = item.stock_item
            stock.quantity = (stock.quantity or Decimal('0.00')) + added_qty
            stock.save()

    # 2. Sync Expense Entry
    company = purchase_invoice.company
    head, _ = ExpenseHead.objects.get_or_create(
        company=company,
        name='Purchase',
        defaults={'auto_id': get_auto_id(ExpenseHead), 'creator': creator_user}
    )
    if head.is_deleted:
        head.is_deleted = False
        head.save()

    exp_name = f"Purchase Inv #{purchase_invoice.purchase_inv_number}"
    expense, _ = Expense.objects.get_or_create(
        expense_head=head,
        name=exp_name,
        defaults={'auto_id': get_auto_id(Expense), 'creator': creator_user}
    )
    if expense.is_deleted:
        expense.is_deleted = False
        expense.save()

    # Create ExpenseEntry for financial reports
    ExpenseEntry.objects.create(
        auto_id=get_auto_id(ExpenseEntry),
        creator=creator_user,
        company=company,
        branch=purchase_invoice.branch,
        expense=expense,
        amount=purchase_invoice.grand_total,
        paid_amount=purchase_invoice.amount_paid,
        supplier=purchase_invoice.supplier,
        expense_date=purchase_invoice.invoice_date,
        remarks=f"Auto-created from Purchase Invoice #{purchase_invoice.purchase_inv_number}. {purchase_invoice.remarks or ''}".strip()
    )

    # 3. Update Supplier Outstanding Payables
    update_supplier_payables(purchase_invoice.supplier)


def update_supplier_payables(supplier):
    """Recalculates total outstanding payables balance for a supplier."""
    from master.models import PurchaseInvoice
    if not supplier:
        return

    invoices = PurchaseInvoice.objects.filter(supplier=supplier, is_deleted=False)
    total_balance = invoices.aggregate(total=Sum('balance_to_pay'))['total'] or Decimal('0.00')
    supplier.payables = total_balance
    supplier.save()
